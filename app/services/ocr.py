from typing import Literal, Optional

import instructor
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings

SYSTEM_PROMPT = """You are a receipt data extraction expert specialising in Canadian retail receipts.

Given one or more receipt images, extract all data into structured JSON.

Rules:
- If multiple images are provided, they are sequential segments of the SAME physical receipt (top-to-bottom order)
- Deduplicate: if the same item or store header appears in more than one image, include it only once
- Normalize units: "3LB" → quantity 3, unit "lb" | "1.5KG" → quantity 1.5, unit "kg" | "1L" → quantity 1, unit "L"
- Quantity multiplier: when a line starts with "Nx" (e.g. "5x Compliments Still Water (500 ml × 40 ct)"), the leading number (5) is the quantity purchased. Parenthetical size/pack descriptors like "(500 ml × 40 ct)" describe the product packaging — put them in the unit field (e.g. unit="500ml × 40ct"), never use them as the quantity.
- Infer unit_price when not shown: unit_price = total_price / quantity
- Assign categories based on the real-world nature of the item, not the store type
- transaction_date must be YYYY-MM-DD format (e.g. "05/11/2026" → "2026-05-11")
- province must be a two-letter Canadian code: ON, BC, AB, QC, MB, SK, NS, NB, NL, PE, NT, YT, NU
- customer_name: ONLY set if a loyalty or membership name is explicitly printed (e.g. Costco member name). Never use operator numbers or cashier IDs.
- savings: extract discount amount per item if shown (e.g. "SAVED $15.00" → savings 15.00)
- Delivery app receipts (DoorDash, Uber Eats, Skip, Instacart): use the grocery store name printed on the receipt (not the delivery platform name). Exclude non-grocery charges from items: delivery fee, service fee, platform fee, regulatory fee, bag fee, tip/gratuity, and any platform discount lines.
- Omit any field that is not visible or not applicable
- Items list must include every purchasable line — skip subtotal, tax, total, and promotional text lines"""

CategorySlug = Literal[
    "fruits", "vegetables", "dairy", "meat", "seafood", "bakery",
    "beverages", "snacks", "frozen", "canned_goods", "household",
    "cleaning", "stationery", "electronics", "clothing",
    "health_beauty", "tools_hardware", "other",
]


class OcrStoreExtraction(BaseModel):
    name: str = Field(description="Store or chain name e.g. CANADIAN TIRE, COSTCO, FOOD BASICS")
    branch: Optional[str] = Field(None, description="Branch number or mall name e.g. #139 or Stanley Park Mall")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City name")
    province: Optional[str] = Field(None, description="Two-letter Canadian province code")
    postal_code: Optional[str] = Field(None, description="Canadian postal code e.g. N2A 1H2")
    phone: Optional[str] = Field(None, description="Store phone number if printed")


class OcrItemExtraction(BaseModel):
    raw_name: str = Field(description="Exact item name as printed on the receipt")
    category: CategorySlug = Field(description="Real-world category of this item")
    quantity: Optional[float] = Field(None, description="Numeric quantity purchased")
    unit: Optional[str] = Field(None, description="Unit of measure: lb, kg, L, mL, each, pack, bag, box, etc. For multi-packs use the pack descriptor e.g. '500ml × 40ct', '6-pack'.")
    unit_price: Optional[float] = Field(None, description="Price per single unit")
    total_price: float = Field(description="Total price for this line item")
    savings: Optional[float] = Field(None, description="Discount amount shown for this item if any")


class OcrExtraction(BaseModel):
    store: OcrStoreExtraction
    customer_name: Optional[str] = Field(None, description="Loyalty/membership customer name if explicitly printed")
    transaction_date: Optional[str] = Field(None, description="Purchase date in YYYY-MM-DD format")
    transaction_number: Optional[str] = Field(None, description="Transaction or receipt number")
    items: list[OcrItemExtraction] = Field(description="All purchasable line items")
    subtotal: Optional[float] = Field(None, description="Subtotal before tax")
    tax: Optional[float] = Field(None, description="Total tax (HST, GST, PST)")
    total: Optional[float] = Field(None, description="Final total paid")


def _strip_data_prefix(image: str) -> tuple[str, str]:
    """Return (base64_data, media_type) from a data URL or raw base64 string."""
    if image.startswith("data:"):
        header, data = image.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]
        return data, media_type
    return image, "image/jpeg"


def _anthropic_image_block(image: str) -> dict:
    data, media_type = _strip_data_prefix(image)
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _openai_image_block(image: str) -> dict:
    data, media_type = _strip_data_prefix(image)
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{data}"},
    }


async def extract_receipt(images: list[str]) -> OcrExtraction:
    """Send 1–5 receipt images to the configured AI provider and return structured data."""
    provider = settings.ai_provider
    count = len(images)
    user_text = (
        "Extract all data from this receipt image."
        if count == 1
        else f"Extract all data from this receipt. It is split across {count} images in top-to-bottom order. Treat them as one continuous receipt."
    )

    if provider == "openai":
        client = instructor.from_openai(AsyncOpenAI(api_key=settings.openai_api_key))
        return await client.chat.completions.create(
            model="gpt-4o",
            response_model=OcrExtraction,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {  # type: ignore[list-item, misc]  # instructor multimodal format
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        *[_openai_image_block(img) for img in images],
                    ],
                },
            ],
        )

    # Default: Anthropic
    client = instructor.from_anthropic(AsyncAnthropic(api_key=settings.anthropic_api_key))
    return await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        response_model=OcrExtraction,
        messages=[
            {  # type: ignore[list-item, misc]  # instructor multimodal format
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    *[_anthropic_image_block(img) for img in images],
                ],
            }
        ],
    )
