from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.tables import Category, Item, ReceiptItem
from app.schemas.receipt import ItemSummary

router = APIRouter(prefix="/items", tags=["items"])


@router.get("")
async def list_items(session: AsyncSession = Depends(get_session)) -> list:
    stmt = (
        select(
            Item.normalized_name,
            Category.slug.label("category_slug"),
            Category.label.label("category_label"),
            func.count(ReceiptItem.id).label("purchase_count"),
        )
        .join(Category, Item.category_id == Category.id, isouter=True)
        .join(ReceiptItem, ReceiptItem.item_id == Item.id)
        .group_by(Item.id, Item.normalized_name, Category.slug, Category.label)
        .order_by(Item.normalized_name)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ItemSummary(
            normalized_name=row.normalized_name,
            category_slug=row.category_slug or "other",
            category_label=row.category_label or "Other",
            purchase_count=row.purchase_count,
        ).model_dump(by_alias=True, mode="json")
        for row in rows
    ]
