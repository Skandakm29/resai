import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.schemas.assistant import ChatRequest, ChatResponse, SearchFilters, SearchRequest, SearchResponse
from app.schemas.cart import CartValidateRequest, CartValidateResponse
from app.schemas.menu import CategoryOut, MenuItemOut, MenuOut, RestaurantOut
from app.ratelimit import rate_limit
from app.services import menu_service
from app.services.assistant import AssistantService
from app.services.cart import validate_cart
from app.services.intent_rules import parse_message
from app.services.search import describe_filters, search

router = APIRouter(prefix="/api")


def _restaurant(db: Session, slug: str):
    try:
        return menu_service.get_restaurant(db, slug)
    except menu_service.NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/health", tags=["system"])
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - report, don't crash the health check
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "assistant_mode": "llm" if settings.llm_enabled else "rules",
    }


@router.get("/restaurants/{slug}", response_model=RestaurantOut, tags=["menu"])
def get_restaurant(slug: str, db: Session = Depends(get_db)):
    return menu_service.serialize_restaurant(_restaurant(db, slug))


@router.get("/restaurants/{slug}/menu", response_model=MenuOut, tags=["menu"])
def get_menu(slug: str, db: Session = Depends(get_db)):
    return menu_service.build_menu(db, _restaurant(db, slug))


@router.get("/restaurants/{slug}/menu/categories", response_model=list[CategoryOut], tags=["menu"])
def get_categories(slug: str, db: Session = Depends(get_db)):
    return menu_service.category_summaries(db, _restaurant(db, slug))


@router.get("/restaurants/{slug}/menu/items/{item_id}", response_model=MenuItemOut, tags=["menu"])
def get_item(slug: str, item_id: uuid.UUID, db: Session = Depends(get_db)):
    restaurant = _restaurant(db, slug)
    try:
        return menu_service.serialize_item(menu_service.get_item(db, restaurant, item_id))
    except menu_service.NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/restaurants/{slug}/assistant/chat",
    response_model=ChatResponse,
    tags=["assistant"],
    dependencies=[Depends(rate_limit("chat"))],
)
def chat(
    slug: str,
    req: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider | None = Depends(get_provider),
):
    restaurant = _restaurant(db, slug)
    if restaurant.settings is not None and not restaurant.settings.ai_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The assistant is disabled for this restaurant.")
    service = AssistantService(db, settings, provider)
    return service.chat(restaurant, req)


@router.post(
    "/restaurants/{slug}/assistant/search",
    response_model=SearchResponse,
    tags=["assistant"],
    dependencies=[Depends(rate_limit("search"))],
)
def assistant_search(slug: str, req: SearchRequest, db: Session = Depends(get_db)):
    """Deterministic structured search. ``query`` is parsed with the rule-based
    parser; explicit ``filters`` take precedence over anything parsed."""
    restaurant = _restaurant(db, slug)
    items = menu_service.load_items(db, restaurant)
    filters = SearchFilters()
    if req.query:
        filters = parse_message(req.query, items).filters
    if req.filters is not None:
        explicit = req.filters.model_dump(exclude_unset=True)
        filters = SearchFilters.model_validate({**filters.model_dump(), **explicit})
    outcome = search(items, filters, limit=req.limit)
    return SearchResponse(
        items=[menu_service.serialize_item(s.item) for s in outcome.matches],
        total=len(outcome.matches),
        applied_filters=filters,
        filter_summary=describe_filters(filters),
    )


@router.post("/cart/validate", response_model=CartValidateResponse, tags=["cart"])
def cart_validate(req: CartValidateRequest, db: Session = Depends(get_db)):
    restaurant = _restaurant(db, req.restaurant_slug)
    return validate_cart(db, restaurant, req)
