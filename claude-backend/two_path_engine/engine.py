"""TwoPathEngine: main orchestrator.

Fetches live data, builds FeatureSnapshot, routes through quality gate,
then scores via the appropriate side scorer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.features.feature_builder import build_feature_snapshot
from app.features.feature_snapshot import FeatureSnapshot
from app.providers.earnings_provider import get_earnings_data
from app.providers.fundamental_provider import get_fundamental_data, get_valuation_data
from app.providers.market_data_provider import get_history, get_market_data
from app.services.market_regime_service import classify_regime
from app.services.risk_management_service import compute_risk_management
from app.services.stock_archetype_service import classify_and_attach
from app.services.technical_analysis_service import compute_technicals
from two_path_engine.avoid_side import AvoidSideScorer, AvoidSideResult
from two_path_engine.buy_side import BuySideScorer, BuySideResult
from two_path_engine.quality_gate import QualityGate

logger = logging.getLogger(__name__)


@dataclass
class TwoPathDecision:
    ticker: str
    path_taken: str        # "quality_intact" | "deteriorating_business"
    decision: str          # BUY | WAIT | AVOID | WATCHLIST
    score: float
    reasons: list[str] = field(default_factory=list)
    gate_reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    risk_plan: dict = field(default_factory=dict)
    snapshot: FeatureSnapshot | None = None


class TwoPathEngine:
    """Orchestrates the two-path decision for a single ticker.

    Call analyze(ticker) for a full live analysis.
    Call analyze_snapshot(snapshot) to score a pre-built FeatureSnapshot
    (used in backtests and unit tests).
    """

    def __init__(self) -> None:
        self._gate = QualityGate()
        self._buy = BuySideScorer()
        self._avoid = AvoidSideScorer()

    # ------------------------------------------------------------------
    # Live analysis path
    # ------------------------------------------------------------------

    def analyze(self, ticker: str) -> TwoPathDecision:
        """Fetch live data and run full two-path analysis."""
        ticker = ticker.upper().strip()
        logger.info("Fetching data for %s", ticker)

        # Price data
        df = get_history(ticker, period="2y", interval="1d")
        spy_df = get_history("SPY", period="2y", interval="1d")
        qqq_df = get_history("QQQ", period="2y", interval="1d")

        # Fundamental / earnings / valuation
        market_data = get_market_data(ticker)
        fundamental_data = get_fundamental_data(ticker)
        valuation_data = get_valuation_data(ticker, market_cap=market_data.market_cap)
        earnings_data = get_earnings_data(ticker)

        # Classify archetype, attach to fundamental_data
        classify_and_attach(fundamental_data, valuation_data)

        # Compute technicals
        technicals = compute_technicals(df, spy_df=spy_df)

        # Classify market regime
        regime = classify_regime(spy_df, qqq_df)

        # Build FeatureSnapshot
        price = float(df["Close"].iloc[-1])
        snapshot = build_feature_snapshot(
            ticker=ticker,
            price=price,
            technicals=technicals,
            fundamentals=fundamental_data,
            valuation=valuation_data,
            earnings=earnings_data,
            market_data=market_data,
            regime_assessment=regime,
        )

        decision = self.analyze_snapshot(snapshot)

        # Compute risk plan
        risk_plan = _build_risk_plan(snapshot, decision.decision)
        decision.risk_plan = risk_plan
        return decision

    # ------------------------------------------------------------------
    # Snapshot scoring path (used in tests and backtests)
    # ------------------------------------------------------------------

    def analyze_snapshot(self, snapshot: FeatureSnapshot) -> TwoPathDecision:
        """Run two-path analysis on a pre-built FeatureSnapshot."""
        gate_result = self._gate.evaluate(snapshot)

        if gate_result.passes:
            side_result = self._buy.score(snapshot)
            return TwoPathDecision(
                ticker=snapshot.ticker,
                path_taken="quality_intact",
                decision=side_result.decision,
                score=side_result.score,
                reasons=side_result.reasons,
                gate_reasons=gate_result.reasons,
                missing_fields=side_result.missing_fields,
                snapshot=snapshot,
            )
        else:
            side_result = self._avoid.score(snapshot)
            return TwoPathDecision(
                ticker=snapshot.ticker,
                path_taken="deteriorating_business",
                decision=side_result.decision,
                score=side_result.score,
                reasons=side_result.reasons,
                gate_reasons=gate_result.reasons,
                missing_fields=side_result.missing_fields,
                snapshot=snapshot,
            )


# ------------------------------------------------------------------
# Risk plan helper
# ------------------------------------------------------------------

def _build_risk_plan(snapshot: FeatureSnapshot, decision: str) -> dict:
    """Compute a simple risk plan from snapshot data."""
    price = snapshot.price
    atr_pct = snapshot.atr_percent or 2.0
    atr_abs = price * (atr_pct / 100.0)

    stop_loss = round(price - 2.0 * atr_abs, 2)
    target_1 = round(price * 1.10, 2)
    target_2 = round(price * 1.20, 2)

    return {
        "decision": decision,
        "entry_price": round(price, 2),
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "atr_pct": round(atr_pct, 2),
        "risk_per_share": round(price - stop_loss, 2),
    }
