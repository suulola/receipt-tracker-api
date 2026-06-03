from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.tables import Category, Item, Receipt, ReceiptItem, Store
from app.schemas.receipt import CompareResponse, CompareResult

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("")
async def compare_items(
    item: str = Query(..., min_length=1, max_length=200, description="Item name to search across all receipts"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    search = f"%{item.lower()}%"

    # Match on normalized item name OR the raw name on the receipt line
    stmt = (
        select(
            ReceiptItem.id.label("receipt_item_id"),
            ReceiptItem.raw_name,
            ReceiptItem.quantity,
            ReceiptItem.unit,
            ReceiptItem.unit_price,
            ReceiptItem.total_price,
            ReceiptItem.savings,
            Receipt.id.label("receipt_id"),
            Receipt.purchase_date,
            Store.name.label("store_name"),
            Store.branch.label("store_branch"),
            Store.city.label("store_city"),
            Item.normalized_name,
            Category.slug.label("category_slug"),
        )
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .join(Store, Receipt.store_id == Store.id)
        .join(Item, ReceiptItem.item_id == Item.id)
        .outerjoin(Category, Item.category_id == Category.id)
        .where(
            or_(
                Item.normalized_name.ilike(search),
                ReceiptItem.raw_name.ilike(search),
            )
        )
        .order_by(Receipt.purchase_date.desc().nullslast())
        .limit(100)
    )

    result = await session.execute(stmt)
    rows = result.all()

    results = []
    for row in rows:
        qty = float(row.quantity) if row.quantity is not None else None
        total = float(row.total_price)
        price_per_unit = round(total / qty, 4) if qty and qty > 0 else None

        results.append(
            CompareResult(
                receipt_item_id=row.receipt_item_id,
                receipt_id=row.receipt_id,
                store_name=row.store_name,
                store_branch=row.store_branch,
                store_city=row.store_city,
                purchase_date=row.purchase_date,
                raw_name=row.raw_name,
                normalized_name=row.normalized_name,
                category_slug=row.category_slug or "other",
                quantity=qty,
                unit=row.unit,
                unit_price=float(row.unit_price) if row.unit_price is not None else None,
                total_price=total,
                savings=float(row.savings) if row.savings is not None else None,
                price_per_unit=price_per_unit,
            )
        )

    return CompareResponse(
        query=item,
        results=results,
    ).model_dump(by_alias=True, mode="json")
