"""Owner onboarding endpoints: upload a menu, review the draft, publish a page.

Protected by ADMIN_API_KEY (the endpoints 404 when it is unset).
"""

import secrets

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion import publish as publisher
from app.ingestion.extract import ExtractionError, PageText, Upload, extract_from_pages, extract_menu
from app.ingestion.text_parser import DraftMenu, parse_menu_text
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.ratelimit import hourly_limit

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def require_admin(x_admin_key: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> None:
    if settings.admin_api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding API is not enabled")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key.get_secret_value()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


class MenuTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


@router.post("/menu/parse-text", response_model=DraftMenu, dependencies=[Depends(require_admin)])
def parse_text(body: MenuTextIn) -> DraftMenu:
    """Extract a reviewable draft menu from raw (e.g. OCR'd) text. Does not persist anything."""
    return parse_menu_text(body.text)


@router.get("/status", dependencies=[Depends(require_admin)])
def onboarding_status(settings: Settings = Depends(get_settings)) -> dict:
    """What the upload can read on this server (shown on the admin page)."""
    return {"reads_photos_and_scans": True, "max_upload_mb": settings.menu_upload_max_mb}


class PageIn(BaseModel):
    label: str = Field(max_length=300)
    text: str = Field(max_length=40_000)
    layer: str = Field(default="", max_length=40_000)


async def _extract(
    files: list[UploadFile], text: str, settings: Settings, provider: LLMProvider | None, pages: str = ""
) -> DraftMenu:
    if pages:
        # The browser already OCR'd the files: only structuring happens here.
        try:
            parsed = TypeAdapter(list[PageIn]).validate_json(pages)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Invalid page data.") from exc
        if not 0 < len(parsed) <= 200 or sum(len(p.text) for p in parsed) > 400_000:
            raise HTTPException(status_code=422, detail="Upload at most 200 pages.")
        page_texts = [PageText(label=p.label, text=p.text, layer=p.layer) for p in parsed]
        try:
            return await run_in_threadpool(
                extract_from_pages, page_texts, text, settings=settings, provider=provider
            )
        except ExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(files) > 10:
        raise HTTPException(status_code=422, detail="Upload at most 10 files.")
    uploads, total = [], 0
    for f in files:
        data = await f.read()
        total += len(data)
        if total > settings.menu_upload_max_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Uploads are limited to {settings.menu_upload_max_mb} MB.")
        if data:
            uploads.append(Upload(filename=f.filename or "upload", content_type=f.content_type or "", data=data))
    try:
        # The LLM calls are blocking; keep them off the event loop.
        return await run_in_threadpool(extract_menu, uploads, text, settings=settings, provider=provider)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/menu/extract", response_model=DraftMenu, dependencies=[Depends(require_admin)])
async def extract(
    files: list[UploadFile] = File(default=[]),
    text: str = Form(default="", max_length=50_000),
    pages: str = Form(default="", max_length=2_000_000),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider | None = Depends(get_provider),
) -> DraftMenu:
    """Menu PDF / photos / pasted text (or pages the browser already OCR'd) to a reviewable draft."""
    return await _extract(files, text, settings, provider, pages)


@router.post(
    "/restaurants", response_model=publisher.PublishedCafe, status_code=201, dependencies=[Depends(require_admin)]
)
def publish(body: publisher.PublishRequest, db: Session = Depends(get_db)) -> publisher.PublishedCafe:
    """Publish a reviewed draft as a live page at /r/<slug>."""
    try:
        return publisher.publish(db, body)
    except publisher.SlugTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/restaurants", response_model=list[publisher.PublishedCafe], dependencies=[Depends(require_admin)])
def list_restaurants(db: Session = Depends(get_db)) -> list[publisher.PublishedCafe]:
    """Cafés published from uploads, newest first."""
    return publisher.list_uploaded(db)


@router.delete("/restaurants/{slug}", status_code=204, dependencies=[Depends(require_admin)])
def delete_restaurant(slug: str, db: Session = Depends(get_db)) -> None:
    """Take down an uploaded café's page (built-in demos can't be deleted)."""
    if not publisher.delete_uploaded(db, slug):
        raise HTTPException(status_code=404, detail="No uploaded café with that URL")


# --- Self-serve (public landing page) ------------------------------------
# No admin key: a restaurant owner uploads a menu and gets a link straight
# away. Rate limited per IP per hour, since every read is an LLM call.

public = APIRouter(prefix="/api/start", tags=["self-serve onboarding"])


def require_public(settings: Settings = Depends(get_settings)) -> None:
    if not settings.public_onboarding_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sign-ups are closed right now.")


@public.get("/status", dependencies=[Depends(require_public)])
def public_status(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "reads_photos_and_scans": True,
        "max_upload_mb": settings.menu_upload_max_mb,
        "max_items": settings.public_max_items,
    }


@public.post(
    "/extract",
    response_model=DraftMenu,
    dependencies=[Depends(require_public), Depends(hourly_limit("start-extract", "public_extract_per_hour"))],
)
async def public_extract(
    files: list[UploadFile] = File(default=[]),
    text: str = Form(default="", max_length=50_000),
    pages: str = Form(default="", max_length=2_000_000),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider | None = Depends(get_provider),
) -> DraftMenu:
    """Read an owner's menu into a draft they can check. Does not persist anything."""
    return await _extract(files, text, settings, provider, pages)


@public.post(
    "/publish",
    response_model=publisher.PublishedCafe,
    status_code=201,
    dependencies=[Depends(require_public), Depends(hourly_limit("start-publish", "public_publish_per_hour"))],
)
def public_publish(
    body: publisher.SelfServePublishRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> publisher.PublishedCafe:
    """Publish the owner's checked menu. A taken link gets a -2, -3... suffix."""
    if len(body.items) > settings.public_max_items:
        raise HTTPException(status_code=422, detail=f"Menus are limited to {settings.public_max_items} items.")
    req = publisher.PublishRequest(profile=body.profile, items=body.items, replace=False)
    try:
        return publisher.publish(db, req, owner=body.owner, auto_slug=True)
    except publisher.SlugTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
