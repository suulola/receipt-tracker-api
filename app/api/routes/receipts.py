import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

# ── Date param helper ─────────────────────────────────────────────────────────

def _parse_date_param(value: Optional[str], param_name: str) -> Optional[date]:
    """Parse a YYYY-MM-DD query string date, raising HTTP 400 on invalid format."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{param_name} must be YYYY-MM-DD")
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.tables import Receipt, ReceiptItem, Store
from app.schemas.receipt import ReceiptIn, ReceiptListItem, ReceiptItemOut, ReceiptOut, StoreOut
from app.services.normaliser import find_or_create_item

router = APIRouter(prefix="/receipts", tags=["receipts"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _eq_or_null(col, val):
    """Build a WHERE clause that handles NULL equality correctly."""
    return col.is_(None) if val is None else col == val


async def _upsert_store(session: AsyncSession, store_in) -> Store:
    """Return the existing Store row matching name + branch + city, or insert and return a new one."""
    stmt = select(Store).where(
        Store.name == store_in.name,
        _eq_or_null(Store.branch, store_in.branch),
        _eq_or_null(Store.city, store_in.city),
    )
    result = await session.execute(stmt)
    store = result.scalar_one_or_none()
    if store:
        return store

    store = Store(
        name=store_in.name,
        branch=store_in.branch,
        address=store_in.address,
        city=store_in.city,
        province=store_in.province,
        postal_code=store_in.postal_code,
        phone=store_in.phone,
    )
    session.add(store)
    await session.flush()
    return store


def _build_receipt_out(receipt: Receipt) -> ReceiptOut:
    """Map a fully-loaded Receipt ORM object to the ReceiptOut response schema, traversing item and category relations."""
    items_out = []
    for ri in receipt.items:
        items_out.append(
            ReceiptItemOut(
                id=ri.id,
                raw_name=ri.raw_name,
                normalized_name=ri.item.normalized_name if ri.item else ri.raw_name,
                category_slug=ri.item.category.slug if ri.item and ri.item.category else "other",
                category_label=ri.item.category.label if ri.item and ri.item.category else "Other",
                quantity=float(ri.quantity) if ri.quantity is not None else None,
                unit=ri.unit,
                unit_price=float(ri.unit_price) if ri.unit_price is not None else None,
                total_price=float(ri.total_price),
                savings=float(ri.savings) if ri.savings is not None else None,
            )
        )

    store = receipt.store
    return ReceiptOut(
        id=receipt.id,
        store=StoreOut(
            id=store.id,
            name=store.name,
            branch=store.branch,
            address=store.address,
            city=store.city,
            province=store.province,
            postal_code=store.postal_code,
        ),
        purchase_date=receipt.purchase_date,
        transaction_number=receipt.transaction_number,
        customer_name=receipt.customer_name,
        items=items_out,
        subtotal=float(receipt.subtotal) if receipt.subtotal is not None else None,
        tax=float(receipt.tax) if receipt.tax is not None else None,
        total=float(receipt.total) if receipt.total is not None else None,
        image_count=receipt.image_count,
        created_at=receipt.created_at,
    )


# ── POST /receipts ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_receipt(
    data: ReceiptIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Persist a new receipt: upsert the store, normalise each item via fuzzy match, and link all rows in one transaction."""
    async with session.begin():
        store = await _upsert_store(session, data.store)

        purchase_date: Optional[date] = None
        if data.transaction_date:
            try:
                purchase_date = date.fromisoformat(data.transaction_date)
            except ValueError:
                purchase_date = None  # Bad date from OCR — store receipt without a date

        receipt = Receipt(
            store_id=store.id,
            purchase_date=purchase_date,
            transaction_number=data.transaction_number,
            customer_name=data.customer_name,
            subtotal=data.subtotal,
            tax=data.tax,
            total=data.total,
            image_count=data.image_count or 1,
        )
        session.add(receipt)
        await session.flush()

        for item_in in data.items:
            item = await find_or_create_item(session, item_in.raw_name, item_in.category)

            unit_price = item_in.unit_price
            if unit_price is None and item_in.quantity and item_in.quantity > 0:
                unit_price = round(item_in.total_price / item_in.quantity, 2)

            receipt_item = ReceiptItem(
                receipt_id=receipt.id,
                item_id=item.id,
                raw_name=item_in.raw_name,
                quantity=item_in.quantity,
                unit=item_in.unit,
                unit_price=unit_price,
                total_price=item_in.total_price,
                savings=item_in.savings,
            )
            session.add(receipt_item)

    return {"id": str(receipt.id)}


# ── GET /receipts ─────────────────────────────────────────────────────────────

@router.get("")
async def list_receipts(
    store: Optional[str] = Query(None, max_length=200, description="Filter by store name (partial match)"),
    date_from: Optional[str] = Query(None, max_length=10, description="Earliest purchase date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, max_length=10, description="Latest purchase date YYYY-MM-DD"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list:
    """Return a paginated, filterable summary list of receipts ordered by purchase date descending."""
    stmt = (
        select(
            Receipt,
            Store.name.label("store_name"),
            Store.branch.label("store_branch"),
            Store.city.label("store_city"),
            func.count(ReceiptItem.id).label("item_count"),
        )
        .join(Store, Receipt.store_id == Store.id)
        .outerjoin(ReceiptItem, ReceiptItem.receipt_id == Receipt.id)
        .group_by(Receipt.id, Store.name, Store.branch, Store.city)
        .order_by(Receipt.purchase_date.desc().nullslast(), Receipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    date_from_parsed = _parse_date_param(date_from, "date_from")
    date_to_parsed = _parse_date_param(date_to, "date_to")

    if store:
        stmt = stmt.where(Store.name.ilike(f"%{store}%"))
    if date_from_parsed:
        stmt = stmt.where(Receipt.purchase_date >= date_from_parsed)
    if date_to_parsed:
        stmt = stmt.where(Receipt.purchase_date <= date_to_parsed)
    if category:
        from app.models.tables import Category, Item
        stmt = stmt.where(
            Receipt.id.in_(
                select(ReceiptItem.receipt_id)
                .join(Item, ReceiptItem.item_id == Item.id)
                .join(Category, Item.category_id == Category.id)
                .where(Category.slug == category)
            )
        )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ReceiptListItem(
            id=row.Receipt.id,
            store_name=row.store_name,
            store_branch=row.store_branch,
            store_city=row.store_city,
            purchase_date=row.Receipt.purchase_date,
            total=float(row.Receipt.total) if row.Receipt.total is not None else None,
            item_count=row.item_count,
            created_at=row.Receipt.created_at,
        ).model_dump(by_alias=True, mode="json")
        for row in rows
    ]


# ── GET /receipts/:id ─────────────────────────────────────────────────────────

@router.get("/{receipt_id}")
async def get_receipt(
    receipt_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return a single receipt with full item detail, or 404 if not found."""
    result = await session.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return _build_receipt_out(receipt).model_dump(by_alias=True, mode="json")


# ── DELETE /receipts/:id ──────────────────────────────────────────────────────

@router.delete("/{receipt_id}", status_code=204)
async def delete_receipt(
    receipt_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a receipt and its line items (cascade). Returns 204 on success, 404 if not found."""
    result = await session.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    await session.delete(receipt)
    await session.commit()
