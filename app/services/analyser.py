import anthropic

from app.config import settings
from app.schemas.receipt import CompareResult

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _format_history(item_name: str, results: list[CompareResult]) -> str:
    if not results:
        return "No purchase history found."

    lines = [f'Purchase history for "{item_name}":\n']
    for r in results:
        store = r.store_name
        if r.store_branch:
            store += f" {r.store_branch}"
        if r.store_city:
            store += f" ({r.store_city})"

        qty = f"{r.quantity}{r.unit}" if r.quantity and r.unit else (str(r.quantity) if r.quantity else "")
        price = f"${r.total_price:.2f}"
        per_unit = f" = ${r.price_per_unit:.2f}/{r.unit}" if r.price_per_unit and r.unit else ""
        date = str(r.purchase_date) if r.purchase_date else "unknown date"
        savings = f" (saved ${r.savings:.2f})" if r.savings else ""

        lines.append(f"  - {store}: {qty} for {price}{per_unit}{savings} on {date}")

    return "\n".join(lines)


def analyse(item_name: str, results: list[CompareResult]) -> str:
    history = _format_history(item_name, results)

    message = get_client().messages.create(
        model="claude-haiku-4-5-20251001",  # fast + cheap for on-demand analysis
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{history}\n\n"
                    "Based on this Canadian shopping history, give a brief practical recommendation:\n"
                    "1. Which store offers the best value per unit?\n"
                    "2. Any price trends worth noting?\n"
                    "3. Where to buy next?\n\n"
                    "Keep it to 3–4 sentences. Be specific about prices and stores."
                ),
            }
        ],
    )

    return message.content[0].text
