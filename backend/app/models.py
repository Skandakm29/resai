"""SQLAlchemy models.

Every menu-related row carries ``restaurant_id`` so that every query can be
scoped to a single tenant, even when joining through child tables.

Money is stored as NUMERIC(10, 2) and handled as ``Decimal`` in Python.
Nullable booleans / statuses deliberately model "unknown": ``None`` means the
restaurant has not verified the attribute, and the assistant must say so.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")
Money = Numeric(10, 2)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Restaurant(TimestampMixin, Base):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    tagline: Mapped[str | None] = mapped_column(String(240))
    address_line: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    settings: Mapped[RestaurantSettings | None] = relationship(
        back_populates="restaurant", uselist=False, cascade="all, delete-orphan"
    )
    menus: Mapped[list[Menu]] = relationship(back_populates="restaurant", cascade="all, delete-orphan")


class RestaurantSettings(TimestampMixin, Base):
    __tablename__ = "restaurant_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), unique=True
    )
    assistant_name: Mapped[str] = mapped_column(String(80), default="Your Coffee Guide")
    welcome_message: Mapped[str] = mapped_column(Text)
    suggested_prompts: Mapped[list[str]] = mapped_column(JSONType, default=list)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # False until a real ordering/payment backend is integrated.
    ordering_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allergen_disclaimer: Mapped[str] = mapped_column(Text)
    # Branding for the customer page. brand_color is a #rrggbb hex; None = default theme.
    brand_color: Mapped[str | None] = mapped_column(String(7))
    assistant_icon: Mapped[str] = mapped_column(String(32), default="coffee", server_default="coffee")

    restaurant: Mapped[Restaurant] = relationship(back_populates="settings")


class Menu(TimestampMixin, Base):
    __tablename__ = "menus"
    __table_args__ = (UniqueConstraint("restaurant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="Main menu")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    restaurant: Mapped[Restaurant] = relationship(back_populates="menus")
    categories: Mapped[list[MenuCategory]] = relationship(
        back_populates="menu", cascade="all, delete-orphan", order_by="MenuCategory.sort_order"
    )
    versions: Mapped[list[MenuVersion]] = relationship(
        back_populates="menu", cascade="all, delete-orphan", order_by="MenuVersion.version_number"
    )


class MenuVersion(Base):
    """An immutable snapshot of a menu at publish time (audit + rollback)."""

    __tablename__ = "menu_versions"
    __table_args__ = (
        UniqueConstraint("menu_id", "version_number"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="menu_version_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source: Mapped[str] = mapped_column(String(32), default="manual")  # seed | manual | upload
    snapshot: Mapped[dict] = mapped_column(JSONType, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    menu: Mapped[Menu] = relationship(back_populates="versions")


class MenuCategory(TimestampMixin, Base):
    __tablename__ = "menu_categories"
    __table_args__ = (UniqueConstraint("menu_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    menu: Mapped[Menu] = relationship(back_populates="categories")
    items: Mapped[list[MenuItem]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="MenuItem.sort_order"
    )


menu_item_addons = Table(
    "menu_item_addons",
    Base.metadata,
    Column("item_id", ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True),
    Column("addon_id", ForeignKey("menu_addons.id", ondelete="CASCADE"), primary_key=True),
)


class MenuItem(TimestampMixin, Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint("menu_id", "slug"),
        CheckConstraint("price >= 0", name="menu_item_price_non_negative"),
        CheckConstraint("item_type IN ('beverage', 'food', 'dessert')", name="menu_item_type"),
        CheckConstraint("temperature IS NULL OR temperature IN ('hot', 'cold')", name="menu_item_temp"),
        CheckConstraint("strength IS NULL OR strength BETWEEN 1 AND 5", name="menu_item_strength"),
        CheckConstraint("sweetness IS NULL OR sweetness BETWEEN 1 AND 5", name="menu_item_sweetness"),
        CheckConstraint("serves >= 1", name="menu_item_serves"),
        CheckConstraint(
            "ingredients_status IN ('verified', 'partial', 'unknown')", name="menu_item_ingredients_status"
        ),
        CheckConstraint("allergens_status IN ('verified', 'unknown')", name="menu_item_allergens_status"),
        Index("ix_menu_items_restaurant_available", "restaurant_id", "is_available"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("menu_categories.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    # Starting price. For items with variants, each variant has its own price.
    price: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str | None] = mapped_column(String(500))

    item_type: Mapped[str] = mapped_column(String(16))  # beverage | food | dessert
    temperature: Mapped[str | None] = mapped_column(String(8))  # hot | cold
    contains_coffee: Mapped[bool | None] = mapped_column(Boolean)
    caffeine_level: Mapped[str | None] = mapped_column(String(16))  # none|low|medium|high
    strength: Mapped[int | None] = mapped_column(Integer)  # 1-5, coffee intensity
    sweetness: Mapped[int | None] = mapped_column(Integer)  # 1-5
    serves: Mapped[int] = mapped_column(Integer, default=1)

    # Verified dietary attributes. None = not verified by the restaurant.
    # "Vegetarian" follows the Indian convention: no meat, fish or egg.
    is_vegetarian: Mapped[bool | None] = mapped_column(Boolean)
    is_vegan: Mapped[bool | None] = mapped_column(Boolean)

    ingredients: Mapped[list[str] | None] = mapped_column(JSONType)
    ingredients_status: Mapped[str] = mapped_column(String(16), default="unknown")
    allergens: Mapped[list[str] | None] = mapped_column(JSONType)
    allergens_status: Mapped[str] = mapped_column(String(16), default="unknown")

    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)  # structural: espresso, tea, shareable
    flavor_tags: Mapped[list[str]] = mapped_column(JSONType, default=list)  # chocolate, nutty, citrus
    pairs_with: Mapped[list[str]] = mapped_column(JSONType, default=list)  # flavor tags it pairs with
    search_keywords: Mapped[list[str]] = mapped_column(JSONType, default=list)  # aliases: "cappuccino"

    variant_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[MenuCategory] = relationship(back_populates="items")
    variants: Mapped[list[MenuItemVariant]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="MenuItemVariant.sort_order"
    )
    addons: Mapped[list[MenuAddon]] = relationship(secondary=menu_item_addons, order_by="MenuAddon.sort_order")


class MenuItemVariant(TimestampMixin, Base):
    __tablename__ = "menu_item_variants"
    __table_args__ = (
        UniqueConstraint("item_id", "name"),
        CheckConstraint("price >= 0", name="menu_variant_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Money)  # absolute price for this variant
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped[MenuItem] = relationship(back_populates="variants")


class MenuAddon(TimestampMixin, Base):
    __tablename__ = "menu_addons"
    __table_args__ = (
        UniqueConstraint("menu_id", "name"),
        CheckConstraint("price >= 0", name="menu_addon_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    group_name: Mapped[str] = mapped_column(String(80), default="Extras")
    price: Mapped[Decimal] = mapped_column(Money)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    allergens: Mapped[list[str] | None] = mapped_column(JSONType)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    # Structured conversational constraints: active filters, last shown items.
    state: Mapped[dict] = mapped_column(JSONType, default=dict)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="conversation_message_role"),
        Index("ix_conversation_messages_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Python-side default: now() is constant within a transaction, and the user
    # and assistant messages of one turn are written in the same transaction.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
