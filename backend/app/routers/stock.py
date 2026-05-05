from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.request import StockAnalysisRequest
from app.models.response import DataQualityReport, StockAnalysisResult
from app.providers.market_data_provider import get_history, get_market_data, get_sector_etf
from app.providers.fundamental_provider import get_fundamental_data, get_valuation_data
from app.providers.earnings_provider import get_earnings_data, score_earnings
from app.providers.news_provider import get_news_items
from app.providers.options_provider import get_options_snapshot
from app.services.technical_analysis_service import compute_technicals
from app.services.fundamental_analysis_service import score_fundamentals
from app.services.valuation_analysis_service import score_valuation
from app.services.news_sentiment_service import classify_news
from app.services.scoring_service import compute_scores
from app.services.recommendation_service import build_recommendations
from app.services.markdown_report_service import generate_markdown

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
logger = logging.getLogger(__name__)


def _build_data_quality(
    fundamentals,
    valuation,
    earnings,
    news,
    options_available: bool,
    technicals,
) -> DataQualityReport:
    warnings = []
    score = 100.0

    if not valuation.peer_comparison_available:
        warnings.append("Peer valuation comparison unavailable.")
        score -= 5

    if news.coverage_limited:
        warnings.append("News coverage may be limited — yfinance news data.")
        score -= 5

    if not options_available:
        warnings.append("Options data unavailable for this ticker.")
        score -= 5

    if earnings.next_earnings_date is None:
        warnings.append("Next earnings date could not be determined.")
        score -= 5

    if earnings.last_earnings_date is None:
        warnings.append("Earnings history unavailable.")
        score -= 10

    if fundamentals.revenue_ttm is None:
        warnings.append("Revenue data unavailable.")
        score -= 10

    if technicals.ma_200 is None:
        warnings.append("Only limited historical data — 200-day MA not calculable.")
        score -= 10

    return DataQualityReport(score=max(0.0, score), warnings=warnings)


@router.post("/analyze", response_model=StockAnalysisResult)
async def analyze_stock(request: StockAnalysisRequest) -> StockAnalysisResult:
    ticker = request.ticker.upper().strip()

    try:
        # 1. Market data
        market_data = get_market_data(ticker)
        price = market_data.current_price

        # 2. Technical analysis
        hist_1y = get_history(ticker, "1y", "1d")
        spy_hist = get_history("SPY", "1y", "1d")

        sector_etf = get_sector_etf(ticker)
        sector_hist = None
        if sector_etf:
            try:
                sector_hist = get_history(sector_etf, "1y", "1d")
            except Exception:
                pass

        technicals = compute_technicals(hist_1y, spy_df=spy_hist, sector_df=sector_hist)

        # 3. Fundamentals & valuation
        fundamentals = get_fundamental_data(ticker)
        fundamentals.fundamental_score = score_fundamentals(fundamentals)

        valuation = get_valuation_data(ticker, market_cap=market_data.market_cap)
        valuation.valuation_score = score_valuation(valuation)

        # 4. Earnings
        earnings = get_earnings_data(ticker)
        earnings.earnings_score = score_earnings(earnings)

        # 5. News & sentiment
        news_items = get_news_items(ticker)
        news_summary = classify_news(news_items)

        # 6. Options (for short-term catalyst score proxy)
        options = get_options_snapshot(ticker)
        # Use put/call ratio as a mild catalyst/sentiment signal
        catalyst_score = 50.0
        if options.available and options.put_call_ratio is not None:
            pcr = options.put_call_ratio
            if pcr < 0.7:
                catalyst_score = 65.0  # bullish options flow
            elif pcr > 1.3:
                catalyst_score = 35.0  # bearish options flow

        # 7. Aggregate scores
        scores = compute_scores(
            technicals=technicals,
            fundamentals=fundamentals,
            valuation=valuation,
            earnings=earnings,
            news=news_summary,
            catalyst_score=catalyst_score,
        )

        # 8. Recommendations
        recommendations = build_recommendations(
            technicals=technicals,
            fundamentals=fundamentals,
            valuation=valuation,
            earnings=earnings,
            news=news_summary,
            scores=scores,
            horizons=request.horizons,
            risk_profile=request.risk_profile,
            current_price=price,
        )

        # 9. Data quality
        data_quality = _build_data_quality(
            fundamentals, valuation, earnings, news_summary,
            options.available, technicals,
        )

        # 10. Build result (without markdown first — needs the result object)
        result = StockAnalysisResult(
            ticker=ticker,
            generated_at=datetime.now(timezone.utc).isoformat(),
            current_price=price,
            data_quality=data_quality,
            market_data=market_data,
            technicals=technicals,
            fundamentals=fundamentals,
            valuation=valuation,
            earnings=earnings,
            news=news_summary,
            recommendations=recommendations,
            markdown_report="",
        )
        result.markdown_report = generate_markdown(result)

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error analyzing %s", ticker)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/{ticker}/report")
async def get_report(ticker: str):
    req = StockAnalysisRequest(ticker=ticker)
    result = await analyze_stock(req)
    return {"ticker": result.ticker, "markdown_report": result.markdown_report}


@router.get("/{ticker}/technicals")
async def get_technicals(ticker: str):
    req = StockAnalysisRequest(ticker=ticker)
    result = await analyze_stock(req)
    return {"ticker": result.ticker, "technicals": result.technicals}


@router.get("/{ticker}/news")
async def get_news(ticker: str):
    req = StockAnalysisRequest(ticker=ticker)
    result = await analyze_stock(req)
    return {"ticker": result.ticker, "news": result.news}
