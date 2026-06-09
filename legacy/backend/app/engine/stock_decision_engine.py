from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.config.config_loader import MultiSourceConfig, get_multi_config
from app.engine.config_driven_strategy_engine import ConfigDrivenStrategyEngine
from app.engine.rule_engine import RuleEngine
from app.engine.setup_detector import SetupDetector
from app.engine.strategy_router import StrategyRouter
from app.engine.technical_signal_detector import TechnicalSignalDetector
from app.features.feature_builder import build_feature_snapshot
from app.features.feature_snapshot import FeatureSnapshot
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import MarketRegimeAssessment, TechnicalIndicators
from app.models.news import NewsSummary
from app.models.response import HorizonRecommendation, SignalCards
from app.services.data_completeness_service import compute_completeness
from app.services.risk_management_service import compute_risk_management


_DECISION_SUMMARIES: dict[str, str] = {
    "BUY_ON_PULLBACK": "Pullback entry setup. Score {score:.0f}/100 — wait for dip to moving average support.",
    "BUY_NOW_CONTINUATION": "Tight momentum continuation signal. Score {score:.0f}/100 — RSI 55-68, positive RS, within 5% of SMA20.",
    "BUY_STARTER_STRONG_BUT_EXTENDED": "Strong setup but extended. Score {score:.0f}/100. Start small and add on pullback.",
    "WAIT_FOR_PULLBACK": "Good setup but not ideal entry. Score {score:.0f}/100. Wait for pullback to moving average.",
    "OVERSOLD_REBOUND_CANDIDATE": "Oversold rebound setup. Score {score:.0f}/100 — RSI turning up, selling pressure fading. Small position, tight stop.",
    "TRUE_DOWNTREND_AVOID": "Confirmed downtrend. Score {score:.0f}/100 — price below both SMAs, weak RS. Avoid until trend repairs.",
    "BROKEN_SUPPORT_AVOID": "Heavy-volume support break. Score {score:.0f}/100 — price broke key support on high volume. Stand aside.",
    "WATCHLIST": "Some positives but confirmation missing. Score {score:.0f}/100. Monitor for setup.",
    "WATCHLIST_NEEDS_CONFIRMATION": "Improving picture but needs confirmation. Score {score:.0f}/100. Add to watchlist.",
    "AVOID_LOW_CONFIDENCE": "Insufficient data for reliable recommendation. Score {score:.0f}/100. Proceed with caution.",
    "ACCUMULATE_ON_WEAKNESS": "Strong long-term thesis. Score {score:.0f}/100. Accumulate gradually on any weakness.",
    "BUY_NOW_LONG_TERM": "Excellent long-term setup. Score {score:.0f}/100 — quality business at a reasonable valuation.",
    "WATCHLIST_VALUATION_TOO_RICH": "Good business but valuation stretched. Score {score:.0f}/100. Wait for better pricing.",
    "AVOID_LONG_TERM": "Not suitable for long-term holding. Score {score:.0f}/100 — deteriorating fundamentals or excessive valuation.",
}


def _confidence_label(score: float, algo_config: Optional[AlgoConfig] = None) -> str:
    cfg = algo_config or get_algo_config()
    dl = cfg.decision_logic
    if score >= dl["confidence_high_threshold"]:
        return "high"
    if score >= dl["confidence_medium_high_threshold"]:
        return "medium_high"
    if score >= dl["confidence_medium_threshold"]:
        return "medium"
    return "low"


def _make_summary(decision: str, score: float) -> str:
    tmpl = _DECISION_SUMMARIES.get(decision, "Score {score:.0f}/100.")
    return tmpl.format(score=score)


class StockDecisionEngine:
    """Orchestrates the config-driven strategy pipeline to produce list[HorizonRecommendation].

    Pipeline: build_feature_snapshot → secondary tags → signal detection →
              setup detection → strategy routing → per-horizon scoring →
              risk management → HorizonRecommendation assembly.
    """

    def __init__(
        self,
        multi_config: Optional[MultiSourceConfig] = None,
        algo_config: Optional[AlgoConfig] = None,
    ) -> None:
        self._multi_cfg = multi_config or get_multi_config()
        self._algo_config = algo_config
        rule_engine = RuleEngine()
        self._rule_engine = rule_engine
        self._signal_detector = TechnicalSignalDetector(
            self._multi_cfg.signal_definitions, rule_engine
        )
        self._setup_detector = SetupDetector(self._multi_cfg.setup_definitions)
        self._router = StrategyRouter(self._multi_cfg, rule_engine)
        self._strategy_engines: dict[str, ConfigDrivenStrategyEngine] = {
            name: ConfigDrivenStrategyEngine(name, engine_cfg, rule_engine)
            for name, engine_cfg in self._multi_cfg.strategy_engines.items()
        }
        self._tag_rules = self._multi_cfg.secondary_tag_rules

    def _detect_secondary_tags(self, snapshot: FeatureSnapshot) -> list[str]:
        flat = snapshot.to_dict()
        return [
            tag
            for tag, rule in self._tag_rules.items()
            if self._rule_engine.evaluate(rule, flat).matched
        ]

    def decide(
        self,
        ticker: str,
        price: float,
        technicals: TechnicalIndicators,
        fundamentals: FundamentalData,
        valuation: ValuationData,
        earnings: EarningsData,
        news: NewsSummary,
        horizons: list[str],
        risk_profile: str,
        regime_assessment: Optional[MarketRegimeAssessment] = None,
        has_options_data: bool = False,
        has_sufficient_price_history: bool = True,
        signal_cards: Optional[SignalCards] = None,
    ) -> list[HorizonRecommendation]:
        """Run the full new pipeline and return per-horizon recommendations."""
        # 1. Flatten all service outputs into a single feature snapshot
        snapshot = build_feature_snapshot(
            ticker=ticker,
            price=price,
            technicals=technicals,
            fundamentals=fundamentals,
            valuation=valuation,
            earnings=earnings,
            regime_assessment=regime_assessment,
        )

        # 2. Detect secondary tags and attach to snapshot
        snapshot.secondary_tags = self._detect_secondary_tags(snapshot)

        # 3. Detect named technical signals
        signal_result = self._signal_detector.detect(snapshot)

        # 4. Combine signals into a setup name
        setup_result = self._setup_detector.detect(signal_result.active_signals)
        snapshot.selected_setup = setup_result.selected_setup

        # 5. Route to the appropriate strategy engine
        routing = self._router.route(snapshot)
        selected_strategy = routing.selected_strategy

        engine = self._strategy_engines.get(
            selected_strategy,
            self._strategy_engines.get("watchlist_low_confidence"),
        )
        if engine is None:
            # Should never happen if config is complete; safe fallback
            engine = next(iter(self._strategy_engines.values()))

        # 6. Compute data completeness once (shared across all horizons)
        completeness, confidence_score, completeness_warnings = compute_completeness(
            news=news,
            earnings=earnings,
            valuation=valuation,
            has_options_data=has_options_data,
            has_sufficient_price_history=has_sufficient_price_history,
            algo_config=self._algo_config,
        )

        recs: list[HorizonRecommendation] = []
        for horizon in horizons:
            # 7. Score via the selected strategy engine
            engine_result = engine.score(snapshot)

            decision = engine_result.recommendation
            score = engine_result.strategy_score

            # Positive reasons → bullish factors; missing data → bearish context
            bullish = [r for r in engine_result.reasons if r][:5]
            bearish = [f"Missing data: {f}" for f in engine_result.missing_data[:3]]

            summary = _make_summary(decision, score)
            confidence = _confidence_label(score, self._algo_config)

            # 8. Entry/exit/risk plan — reuse existing risk management service
            entry, exit_, rr, sizing = compute_risk_management(
                price=price,
                technicals=technicals,
                decision=decision,
                risk_profile=risk_profile,
                within_30_days_earnings=earnings.within_30_days,
            )

            warnings: list[str] = list(completeness_warnings)
            if engine_result.missing_data:
                warnings.extend(
                    f"Strategy signal incomplete: {f}" for f in engine_result.missing_data[:3]
                )
            if news.coverage_limited:
                warnings.append("News coverage may be limited — yfinance news data.")

            recs.append(
                HorizonRecommendation(
                    horizon=horizon,
                    decision=decision,
                    score=score,
                    confidence=confidence,
                    confidence_score=confidence_score,
                    data_completeness_score=completeness,
                    summary=summary,
                    bullish_factors=bullish,
                    bearish_factors=bearish,
                    entry_plan=entry,
                    exit_plan=exit_,
                    risk_reward=rr,
                    position_sizing=sizing,
                    data_warnings=warnings,
                    signal_cards_weights={},
                    setup=snapshot.selected_setup,
                    strategy_name=selected_strategy,
                )
            )

        return recs


_engine_singleton: Optional[StockDecisionEngine] = None


def get_decision_engine(
    multi_config: Optional[MultiSourceConfig] = None,
    algo_config: Optional[AlgoConfig] = None,
) -> StockDecisionEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = StockDecisionEngine(multi_config, algo_config)
    return _engine_singleton


def reset_decision_engine() -> None:
    global _engine_singleton
    _engine_singleton = None
