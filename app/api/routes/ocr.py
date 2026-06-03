from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.limiter import limiter
from app.schemas.receipt import ReceiptIn, StoreIn, ReceiptItemIn
from app.services.ocr import extract_receipt

router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image (base64-encoded)


class OcrRequest(BaseModel):
    images: list[str]   # base64 or data-URL encoded receipt photos


@router.post("")
@limiter.limit("10/minute")
async def ocr_receipt(request: Request, data: OcrRequest) -> dict:
    if not data.images:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(data.images) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images per receipt")
    for img in data.images:
        if len(img.encode()) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Each image must be under 5 MB")

    extraction = await extract_receipt(data.images)

    # Convert OcrExtraction → ReceiptIn so the response shape matches
    # exactly what POST /receipts expects — the frontend can confirm then
    # submit the same payload without any transformation.
    receipt = ReceiptIn(
        store=StoreIn(
            name=extraction.store.name,
            branch=extraction.store.branch,
            address=extraction.store.address,
            city=extraction.store.city,
            province=extraction.store.province,
            postal_code=extraction.store.postal_code,
            phone=extraction.store.phone,
        ),
        customer_name=extraction.customer_name,
        transaction_date=extraction.transaction_date,
        transaction_number=extraction.transaction_number,
        items=[
            ReceiptItemIn(
                raw_name=item.raw_name,
                category=item.category,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_price=item.total_price,
                savings=item.savings,
            )
            for item in extraction.items
        ],
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        total=extraction.total,
        image_count=len(data.images),
    )

    return receipt.model_dump(by_alias=True, mode="json")
