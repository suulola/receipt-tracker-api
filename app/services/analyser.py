import anthropic
import openai

from app.config import settings
from app.schemas.receipt import CompareResult

_anthropic_client: anthropic.Anthropic | None = None
_openai_client: openai.OpenAI | None = None


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def _get_openai() -> openai.OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _format_history(item_name: str, results: list[CompareResult]) -> str:
    """Build a plain-text purchase history summary to inject into the AI prompt."""
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
    """Return a short AI buying recommendation informed by the item's purchase history."""
    history = _format_history(item_name, results)
    prompt = (
        f"{history}\n\n"
        "Based on this Canadian shopping history, give a brief practical recommendation:\n"
        "1. Which store offers the best value per unit?\n"
        "2. Any price trends worth noting?\n"
        "3. Where to buy next?\n\n"
        "Keep it to 3–4 sentences. Be specific about prices and stores."
    )

    if settings.ai_provider == "openai":
        response = _get_openai().chat.completions.create(
            model="gpt-4o-mini",  # fast + cheap for on-demand analysis
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    # Default: Anthropic
    message = _get_anthropic().messages.create(
        model="claude-haiku-4-5-20251001",  # fast + cheap for on-demand analysis
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    from anthropic.types import TextBlock
    text = next((b.text for b in message.content if isinstance(b, TextBlock)), "")
    return text
