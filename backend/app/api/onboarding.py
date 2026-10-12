"""Owner onboarding endpoints (foundation). Protected by ADMIN_API_KEY."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.ingestion.text_parser import DraftMenu, parse_menu_text

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
