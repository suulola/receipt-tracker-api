import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    DATE,
    TIMESTAMP,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    items: Mapped[List["Item"]] = relationship(back_populates="category")


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("name", "branch", "city", name="uq_store_name_branch_city"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    province: Mapped[Optional[str]] = mapped_column(String(2))
    postal_code: Mapped[Optional[str]] = mapped_column(String(7))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    type: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    receipts: Mapped[List["Receipt"]] = relationship(back_populates="store")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("categories.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    category: Mapped[Optional[Category]] = relationship(back_populates="items", lazy="selectin")
    receipt_items: Mapped[List["ReceiptItem"]] = relationship(back_populates="item")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    purchase_date: Mapped[Optional[date]] = mapped_column(DATE)
    transaction_number: Mapped[Optional[str]] = mapped_column(String(100))
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    image_count: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="receipts", lazy="selectin")
    items: Mapped[List["ReceiptItem"]] = relationship(
        back_populates="receipt", lazy="selectin", cascade="all, delete-orphan"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False)
    raw_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    savings: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="receipt_items", lazy="selectin")
