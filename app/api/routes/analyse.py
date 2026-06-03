from fastapi import APIRouter, HTTPException, Request

from app.limiter import limiter
from app.schemas.receipt import AnalyseRequest, AnalyseResponse
from app.services.analyser import analyse

router = APIRouter(prefix="/analyse", tags=["analyse"])


@router.post("")
@limiter.limit("10/minute")
async def analyse_prices(request: Request, data: AnalyseRequest) -> dict:
    if not data.results:
        raise HTTPException(status_code=400, detail="No price history to analyse")

    recommendation = analyse(data.item, data.results)
    return AnalyseResponse(recommendation=recommendation).model_dump(by_alias=True, mode="json")
