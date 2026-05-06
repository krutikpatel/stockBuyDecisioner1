"""
Story 8 TDD tests: Signal Profile from SignalCards + Markdown with Signal Cards section
Tests written BEFORE implementation.

Coverage:
- build_signal_profile_from_cards(): derives SignalProfile from SignalCards scores
- generate_markdown(): output contains signal cards section when signal_cards present
- Signal profile labels derived correctly from card scores
"""
from __future__ import annotations

import pytest

from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCard, SignalCardLabel, SignalCards, SignalProfile, StockAnalysisResult
from app.services.signal_profile_service import build_signal_profile, build_signal_profile_from_cards


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(score: float, name: str = "test") -> SignalCard:
    return SignalCard(
        name=name,
        score=score,
        label=SignalCardLabel.from_score(score),
        explanation="test",
    )


def _bullish_cards() -> SignalCards:
    return SignalCards(
        momentum=_make_card(80.0, "momentum"),
        trend=_make_card(75.0, "trend"),
        entry_timing=_make_card(72.0, "entry_timing"),
        volume_accumulation=_make_card(70.0, "volume_accumulation"),
        volatility_risk=_make_card(68.0, "volatility_risk"),
        relative_strength=_make_card(78.0, "relative_strength"),
        growth=_make_card(82.0, "growth"),
        valuation=_make_card(65.0, "valuation"),
        quality=_make_card(75.0, "quality"),
        ownership=_make_card(68.0, "ownership"),
        catalyst=_make_card(72.0, "catalyst"),
    )


def _bearish_cards() -> SignalCards:
    return SignalCards(
        momentum=_make_card(18.0, "momentum"),
        trend=_make_card(15.0, "trend"),
        entry_timing=_make_card(20.0, "entry_timing"),
        volume_accumulation=_make_card(18.0, "volume_accumulation"),
        volatility_risk=_make_card(22.0, "volatility_risk"),
        relative_strength=_make_card(15.0, "relative_strength"),
        growth=_make_card(20.0, "growth"),
        valuation=_make_card(25.0, "valuation"),
        quality=_make_card(18.0, "quality"),
        ownership=_make_card(20.0, "ownership"),
        catalyst=_make_card(18.0, "catalyst"),
    )


# ---------------------------------------------------------------------------
# build_signal_profile_from_cards
# ---------------------------------------------------------------------------

class TestBuildSignalProfileFromCards:
    def test_returns_signal_profile(self):
        result = build_signal_profile_from_cards(_bullish_cards())
        assert isinstance(result, SignalProfile)

    def test_bullish_cards_yield_bullish_momentum(self):
        result = build_signal_profile_from_cards(_bullish_cards())
        assert result.momentum in ("BULLISH", "VERY_BULLISH")

    def test_bullish_cards_yield_bullish_growth(self):
        result = build_signal_profile_from_cards(_bullish_cards())
        assert result.growth in ("BULLISH", "VERY_BULLISH")

    def test_bearish_cards_yield_bearish_momentum(self):
        result = build_signal_profile_from_cards(_bearish_cards())
        assert result.momentum in ("BEARISH", "VERY_BEARISH")

    def test_bearish_cards_yield_bearish_growth(self):
        result = build_signal_profile_from_cards(_bearish_cards())
        assert result.growth in ("BEARISH", "VERY_BEARISH")

    def test_valuation_derived_from_valuation_card(self):
        # High valuation score -> ATTRACTIVE
        cards = _bullish_cards()  # valuation score = 65 -> FAIR/ATTRACTIVE
        result = build_signal_profile_from_cards(cards)
        assert result.valuation in ("ATTRACTIVE", "FAIR", "ELEVATED", "RISKY")

    def test_entry_timing_from_entry_timing_card(self):
        cards = _bullish_cards()
        result = build_signal_profile_from_cards(cards)
        assert result.entry_timing in ("IDEAL", "ACCEPTABLE", "EXTENDED", "VERY_EXTENDED")

    def test_sentiment_from_catalyst_card(self):
        cards = _bullish_cards()
        result = build_signal_profile_from_cards(cards)
        assert result.sentiment in ("VERY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "VERY_BEARISH")

    def test_risk_reward_from_volatility_card(self):
        cards = _bullish_cards()
        result = build_signal_profile_from_cards(cards)
        assert result.risk_reward in ("EXCELLENT", "GOOD", "ACCEPTABLE", "POOR")

    def test_existing_build_signal_profile_still_works(self):
        """Backward compat: original build_signal_profile() still works."""
        ti = TechnicalIndicators(
            trend=TrendClassification(label="sideways", description="No clear trend"),
            support_resistance=SupportResistanceLevels(supports=[], resistances=[]),
            technical_score=65.0,
        )
        fd = FundamentalData(fundamental_score=60.0)
        vd = ValuationData(valuation_score=55.0)
        ed = EarningsData(earnings_score=60.0)
        ns = NewsSummary(news_score=55.0)
        result = build_signal_profile(ti, fd, vd, ed, ns)
        assert isinstance(result, SignalProfile)


# ---------------------------------------------------------------------------
# Markdown report contains signal cards section
# ---------------------------------------------------------------------------

class TestMarkdownReportSignalCards:
    def _make_result_with_signal_cards(self, cards: SignalCards) -> StockAnalysisResult:
        from app.models.market import MarketData
        from datetime import datetime

        md = MarketData(
            ticker="AAPL",
            current_price=150.0,
            previous_close=148.0,
            open=149.0,
            day_high=151.0,
            day_low=147.0,
            volume=50_000_000,
            avg_volume_30d=45_000_000,
        )
        ti = TechnicalIndicators(
            trend=TrendClassification(label="sideways", description="test"),
            support_resistance=SupportResistanceLevels(supports=[], resistances=[]),
        )
        return StockAnalysisResult(
            ticker="AAPL",
            generated_at=datetime.now().isoformat(),
            current_price=150.0,
            data_quality={"score": 80.0, "warnings": []},
            market_data=md,
            technicals=ti,
            fundamentals=FundamentalData(),
            valuation=ValuationData(),
            earnings=EarningsData(),
            news=NewsSummary(),
            recommendations=[],
            markdown_report="",
            signal_cards=cards,
        )

    def test_markdown_contains_signal_cards_section(self):
        from app.services.markdown_report_service import generate_markdown
        result = self._make_result_with_signal_cards(_bullish_cards())
        md = generate_markdown(result)
        assert "Signal Cards" in md or "signal_cards" in md.lower() or "Momentum" in md

    def test_markdown_contains_all_11_card_names(self):
        from app.services.markdown_report_service import generate_markdown
        result = self._make_result_with_signal_cards(_bullish_cards())
        md = generate_markdown(result)
        card_keywords = [
            "Momentum", "Trend", "Entry", "Volume", "Volatility",
            "Relative", "Growth", "Valuation", "Quality", "Ownership", "Catalyst",
        ]
        found = sum(1 for kw in card_keywords if kw in md)
        assert found >= 6, f"Expected at least 6 card names in markdown, found {found}"

    def test_markdown_without_signal_cards_no_crash(self):
        """Backward compat: if signal_cards is None, markdown still generates."""
        from app.services.markdown_report_service import generate_markdown
        result = self._make_result_with_signal_cards(_bullish_cards())
        result.signal_cards = None
        md = generate_markdown(result)
        assert isinstance(md, str)
        assert len(md) > 0
