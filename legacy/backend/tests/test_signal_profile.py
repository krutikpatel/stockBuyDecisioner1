"""US-007 unit tests: signal profile output."""
import pytest

from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels
from app.models.news import NewsSummary
from app.models.response import SignalProfile
from app.services.signal_profile_service import build_signal_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_technicals(
    tech_score: float = 75.0,
    is_extended: bool = False,
    trend: str = "strong_uptrend",
    ext_20ma: float = 3.0,
) -> TechnicalIndicators:
    return TechnicalIndicators(
        ma_10=100.0, ma_20=98.0, ma_50=95.0, ma_100=92.0, ma_200=88.0,
        rsi_14=60.0, macd=0.8, macd_signal=0.3, macd_histogram=0.5,
        atr=1.5, volume_trend="above_average",
        trend=TrendClassification(label=trend, description="test"),
        is_extended=is_extended,
        extension_pct_above_20ma=ext_20ma,
        extension_pct_above_50ma=5.0,
        support_resistance=SupportResistanceLevels(
            supports=[95.0], resistances=[115.0],
            nearest_support=95.0, nearest_resistance=115.0,
        ),
        rs_vs_spy=1.2, technical_score=tech_score,
    )


def _make_fundamentals(score: float = 70.0) -> FundamentalData:
    return FundamentalData(
        revenue_growth_yoy=0.20, operating_margin=0.25,
        free_cash_flow=1_000_000_000, fundamental_score=score,
    )


def _make_valuation(score: float = 65.0, archetype_score: float = 0.0) -> ValuationData:
    return ValuationData(
        forward_pe=18.0, valuation_score=score,
        archetype_adjusted_score=archetype_score,
    )


def _make_earnings(score: float = 65.0) -> EarningsData:
    return EarningsData(beat_rate=0.75, earnings_score=score)


def _make_news(score: float = 65.0) -> NewsSummary:
    return NewsSummary(news_score=score, positive_count=3, negative_count=1)


# ---------------------------------------------------------------------------
# Momentum label tests
# ---------------------------------------------------------------------------

class TestMomentumSignal:
    def test_very_bullish_when_high_score_not_extended(self):
        ti = _make_technicals(tech_score=85.0, is_extended=False)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.momentum == "VERY_BULLISH"

    def test_bullish_when_extended_despite_high_score(self):
        ti = _make_technicals(tech_score=85.0, is_extended=True)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.momentum == "BULLISH"

    def test_bearish_when_low_technical_score(self):
        ti = _make_technicals(tech_score=30.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.momentum == "VERY_BEARISH"

    def test_neutral_for_middling_score(self):
        ti = _make_technicals(tech_score=52.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.momentum == "NEUTRAL"


# ---------------------------------------------------------------------------
# Growth label tests
# ---------------------------------------------------------------------------

class TestGrowthSignal:
    def test_very_bullish_when_fundamental_score_above_80(self):
        fd = _make_fundamentals(score=85.0)
        profile = build_signal_profile(_make_technicals(), fd, _make_valuation(), _make_earnings(), _make_news())
        assert profile.growth == "VERY_BULLISH"

    def test_bearish_when_fundamental_score_low(self):
        fd = _make_fundamentals(score=30.0)
        profile = build_signal_profile(_make_technicals(), fd, _make_valuation(), _make_earnings(), _make_news())
        assert profile.growth == "VERY_BEARISH"

    def test_neutral_for_average_fundamentals(self):
        fd = _make_fundamentals(score=53.0)
        profile = build_signal_profile(_make_technicals(), fd, _make_valuation(), _make_earnings(), _make_news())
        assert profile.growth == "NEUTRAL"


# ---------------------------------------------------------------------------
# Valuation label tests
# ---------------------------------------------------------------------------

class TestValuationSignal:
    def test_attractive_when_score_above_70(self):
        vd = _make_valuation(score=75.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), vd, _make_earnings(), _make_news())
        assert profile.valuation == "ATTRACTIVE"

    def test_risky_when_score_below_40(self):
        vd = _make_valuation(score=25.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), vd, _make_earnings(), _make_news())
        assert profile.valuation == "RISKY"

    def test_uses_archetype_adjusted_score_when_set(self):
        vd = _make_valuation(score=25.0, archetype_score=75.0)  # raw=risky, adjusted=attractive
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), vd, _make_earnings(), _make_news())
        assert profile.valuation == "ATTRACTIVE"

    def test_falls_back_to_raw_score_when_archetype_zero(self):
        vd = _make_valuation(score=25.0, archetype_score=0.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), vd, _make_earnings(), _make_news())
        assert profile.valuation == "RISKY"


# ---------------------------------------------------------------------------
# Entry timing tests
# ---------------------------------------------------------------------------

class TestEntryTimingSignal:
    def test_ideal_when_strong_uptrend_not_extended(self):
        ti = _make_technicals(trend="strong_uptrend", is_extended=False)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.entry_timing == "IDEAL"

    def test_extended_when_is_extended_and_modest_extension(self):
        ti = _make_technicals(is_extended=True, ext_20ma=8.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.entry_timing == "EXTENDED"

    def test_very_extended_when_extension_above_15pct(self):
        ti = _make_technicals(is_extended=True, ext_20ma=18.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news())
        assert profile.entry_timing == "VERY_EXTENDED"


# ---------------------------------------------------------------------------
# Sentiment and risk/reward tests
# ---------------------------------------------------------------------------

class TestSentimentSignal:
    def test_very_bullish_for_high_news_score(self):
        ne = _make_news(score=80.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), ne)
        assert profile.sentiment == "VERY_BULLISH"

    def test_neutral_for_average_news(self):
        ne = _make_news(score=50.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), ne)
        assert profile.sentiment == "NEUTRAL"

    def test_bearish_for_low_news_score(self):
        ne = _make_news(score=20.0)
        profile = build_signal_profile(_make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), ne)
        assert profile.sentiment == "VERY_BEARISH"


class TestRiskRewardSignal:
    def test_excellent_when_both_earnings_and_technical_high(self):
        ed = _make_earnings(score=80.0)
        ti = _make_technicals(tech_score=80.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), ed, _make_news())
        assert profile.risk_reward == "EXCELLENT"

    def test_poor_when_both_low(self):
        ed = _make_earnings(score=20.0)
        ti = _make_technicals(tech_score=20.0)
        profile = build_signal_profile(ti, _make_fundamentals(), _make_valuation(), ed, _make_news())
        assert profile.risk_reward == "POOR"


# ---------------------------------------------------------------------------
# SignalProfile field validity
# ---------------------------------------------------------------------------

class TestSignalProfileValidity:
    MOMENTUM_LABELS = {"VERY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "VERY_BEARISH"}
    VALUATION_LABELS = {"ATTRACTIVE", "FAIR", "ELEVATED", "RISKY"}
    ENTRY_LABELS = {"IDEAL", "ACCEPTABLE", "EXTENDED", "VERY_EXTENDED"}
    RR_LABELS = {"EXCELLENT", "GOOD", "ACCEPTABLE", "POOR"}

    def test_all_fields_contain_valid_values(self):
        profile = build_signal_profile(
            _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news()
        )
        assert profile.momentum in self.MOMENTUM_LABELS
        assert profile.growth in self.MOMENTUM_LABELS
        assert profile.valuation in self.VALUATION_LABELS
        assert profile.entry_timing in self.ENTRY_LABELS
        assert profile.sentiment in self.MOMENTUM_LABELS
        assert profile.risk_reward in self.RR_LABELS

    def test_signal_profile_is_pydantic_model(self):
        profile = build_signal_profile(
            _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), _make_news()
        )
        assert isinstance(profile, SignalProfile)

    def test_high_momentum_low_valuation_combination(self):
        """NVDA-like: very bullish momentum, risky valuation — both should coexist."""
        ti = _make_technicals(tech_score=88.0, is_extended=False)
        vd = _make_valuation(score=20.0)  # expensive
        profile = build_signal_profile(ti, _make_fundamentals(), vd, _make_earnings(), _make_news())
        assert profile.momentum == "VERY_BULLISH"
        assert profile.valuation == "RISKY"
