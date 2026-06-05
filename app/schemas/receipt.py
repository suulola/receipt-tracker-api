import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: parses camelCase from frontend, serialises to camelCase for responses."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# Valid category slugs — must stay in sync with the categories table in schema.sql
CategorySlug = Literal[
    "fruits", "vegetables", "dairy", "meat", "seafood", "bakery",
    "beverages", "snacks", "frozen", "canned_goods",
    "household", "cleaning", "stationery", "electronics",
    "clothing", "health_beauty", "tools_hardware", "other",
]


# ── Inbound (frontend → backend) ─────────────────────────────────────────────

class StoreIn(CamelModel):
    name: str = Field(max_length=200)
    branch: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=300)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=2)
    postal_code: Optional[str] = Field(None, max_length=10)
    phone: Optional[str] = Field(None, max_length=20)


class ReceiptItemIn(CamelModel):
    raw_name: str = Field(max_length=300)
    category: CategorySlug = "other"
    quantity: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[float] = None
    total_price: float
    savings: Optional[float] = None


class ReceiptIn(CamelModel):
    store: StoreIn
    customer_name: Optional[str] = Field(None, max_length=200)
    transaction_date: Optional[str] = Field(None, max_length=10)   # YYYY-MM-DD
    transaction_number: Optional[str] = Field(None, max_length=50)
    items: list[ReceiptItemIn]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    image_count: Optional[int] = None


# ── Outbound (backend → frontend) ────────────────────────────────────────────

class StoreOut(CamelModel):
    id: uuid.UUID
    name: str
    branch: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None


class ReceiptItemOut(CamelModel):
    id: uuid.UUID
    raw_name: str
    normalized_name: str
    category_slug: str
    category_label: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: float
    savings: Optional[float] = None


class ReceiptOut(CamelModel):
    id: uuid.UUID
    store: StoreOut
    purchase_date: Optional[date] = None
    transaction_number: Optional[str] = None
    customer_name: Optional[str] = None
    items: list[ReceiptItemOut]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    image_count: int
    created_at: datetime


class ReceiptListItem(CamelModel):
    id: uuid.UUID
    store_name: str
    store_branch: Optional[str] = None
    store_city: Optional[str] = None
    purchase_date: Optional[date] = None
    total: Optional[float] = None
    item_count: int
    created_at: datetime


# ── Compare ───────────────────────────────────────────────────────────────────

class CompareResult(CamelModel):
    receipt_item_id: uuid.UUID
    receipt_id: uuid.UUID
    store_name: str
    store_branch: Optional[str] = None
    store_city: Optional[str] = None
    purchase_date: Optional[date] = None
    raw_name: str
    normalized_name: str
    category_slug: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: float
    savings: Optional[float] = None
    price_per_unit: Optional[float] = None  # computed: total_price / quantity


class CompareResponse(CamelModel):
    query: str
    results: list[CompareResult]


# ── Items browse ─────────────────────────────────────────────────────────────

class ItemSummary(CamelModel):
    normalized_name: str
    category_slug: str
    category_label: str
    purchase_count: int


# ── Analyse ───────────────────────────────────────────────────────────────────

class AnalyseRequest(CamelModel):
    item: str = Field(max_length=200)
    results: list[CompareResult]


class AnalyseResponse(CamelModel):
    recommendation: str
