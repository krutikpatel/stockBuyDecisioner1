"""
Improvements 3: Fine-tuning Params — TDD test suite.

Tests written BEFORE implementation. Each section corresponds to a plan step.
Run the full suite; failing tests indicate which step is not yet implemented.

Coverage:
  Step 1  — New TechnicalIndicators RS % difference fields
  Step 2  — New decision labels (BUY_NOW_CONTINUATION, OVERSOLD_REBOUND_CANDIDATE, etc.)
  Step 3  — Precise BUY_ON_PULLBACK logic (_is_pullback_to_sma50)
  Step 4  — Split AVOID_BAD_CHART (_classify_bad_chart)
  Step 5  — BUY_NOW_CONTINUATION tightening
  Step 6  — Relative strength thresholds (_rs_continuation_ok, _rs_leader, _rs_avoid)
  Step 7  — Regime-specific thresholds (_get_regime_thresholds)
  Step 8  — ATR-based position sizing (_atr_size_multiplier, _compute_stop_atr)
  Step 9  — Context-specific relative volume scoring
  Step 10 — 1W/1M performance bucket gates
  Step 11 — 52-week high distance classifier (_classify_52w_position)
  Step 12 — Entry timing / momentum RSI split in signal_card_service
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels, MarketRegime


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 300, start: float = 100.0, drift: float = 0.001) -> pd.DataFrame:
    """Deterministic upward-trending OHLCV DataFrame with DatetimeIndex."""
    np.random.seed(7)
    returns = np.random.normal(drift, 0.01, n)
    prices = start * np.cumprod(1 + returns)
    noise = prices * 0.005
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": prices - noise,
            "High": prices + noise * 2,
            "Low": prices - noise * 2,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 10_000_000, n).astype(float),
        },
        index=dates,
    )


def _make_ohlcv_drift(n: int = 300, start: float = 100.0, drift: float = 0.002) -> pd.DataFrame:
    """Stronger upward drift — stock outperforms benchmark."""
    return _make_ohlcv(n, start, drift)


def _make_ti(**overrides) -> TechnicalIndicators:
    """Build a minimal TechnicalIndicators for recommendation logic tests."""
    defaults = dict(
        rsi_14=60.0,
        rsi_slope=2.0,
        sma20_relative=2.0,
        sma50_relative=4.0,
        sma200_relative=10.0,
        sma20_slope=0.3,
        sma50_slope=0.2,
        sma200_slope=0.1,
        volume_dryup_ratio=0.7,
        breakout_volume_multiple=1.5,
        perf_1w=2.0,
        perf_1m=6.0,
        perf_3m=12.0,
        rs_vs_spy=1.15,
        rs_vs_spy_20d=1.5,
        rs_vs_spy_63d=3.0,
        rs_vs_sector_20d=1.0,
        rs_vs_sector_63d=2.0,
        trend=TrendClassification(label="strong_uptrend", description=""),
        is_extended=False,
        atr=2.0,
        atr_percent=2.0,
        dist_from_52w_high=-4.0,
        change_from_open_percent=0.5,
        support_resistance=SupportResistanceLevels(
            supports=[95.0], resistances=[110.0],
            nearest_support=95.0, nearest_resistance=110.0,
        ),
    )
    defaults.update(overrides)
    return TechnicalIndicators(**defaults)


# ===========================================================================
# STEP 1 — New TechnicalIndicators RS % difference fields
# ===========================================================================

class TestNewTechnicalIndicatorFields:
    """TechnicalIndicators must expose 4 new RS % difference fields."""

    def test_rs_vs_spy_20d_field_exists(self):
        ti = TechnicalIndicators()
        assert hasattr(ti, "rs_vs_spy_20d"), "TechnicalIndicators must have rs_vs_spy_20d field"

    def test_rs_vs_spy_63d_field_exists(self):
        ti = TechnicalIndicators()
        assert hasattr(ti, "rs_vs_spy_63d"), "TechnicalIndicators must have rs_vs_spy_63d field"

    def test_rs_vs_sector_20d_field_exists(self):
        ti = TechnicalIndicators()
        assert hasattr(ti, "rs_vs_sector_20d"), "TechnicalIndicators must have rs_vs_sector_20d field"

    def test_rs_vs_sector_63d_field_exists(self):
        ti = TechnicalIndicators()
        assert hasattr(ti, "rs_vs_sector_63d"), "TechnicalIndicators must have rs_vs_sector_63d field"

    def test_new_fields_default_to_none(self):
        ti = TechnicalIndicators()
        assert ti.rs_vs_spy_20d is None
        assert ti.rs_vs_spy_63d is None
        assert ti.rs_vs_sector_20d is None
        assert ti.rs_vs_sector_63d is None

    def test_compute_technicals_populates_rs_vs_spy_20d(self):
        from app.services.technical_analysis_service import compute_technicals
        stock_df = _make_ohlcv_drift(n=300, drift=0.002)
        spy_df = _make_ohlcv(n=300, drift=0.001)  # stock outperforms spy
        ti = compute_technicals(stock_df, spy_df=spy_df)
        assert ti.rs_vs_spy_20d is not None, "rs_vs_spy_20d should be computed when spy_df provided"
        # Stock has higher drift → should outperform SPY over 20D
        assert ti.rs_vs_spy_20d > 0, f"Expected positive rs_vs_spy_20d, got {ti.rs_vs_spy_20d}"

    def test_compute_technicals_populates_rs_vs_spy_63d(self):
        from app.services.technical_analysis_service import compute_technicals
        stock_df = _make_ohlcv_drift(n=300, drift=0.002)
        spy_df = _make_ohlcv(n=300, drift=0.001)
        ti = compute_technicals(stock_df, spy_df=spy_df)
        assert ti.rs_vs_spy_63d is not None, "rs_vs_spy_63d should be computed when spy_df provided"
        assert ti.rs_vs_spy_63d > 0

    def test_compute_technicals_populates_rs_vs_sector_20d(self):
        from app.services.technical_analysis_service import compute_technicals
        stock_df = _make_ohlcv_drift(n=300, drift=0.002)
        sector_df = _make_ohlcv(n=300, drift=0.001)
        ti = compute_technicals(stock_df, sector_df=sector_df)
        assert ti.rs_vs_sector_20d is not None, "rs_vs_sector_20d should be computed when sector_df provided"
        assert ti.rs_vs_sector_20d > 0

    def test_compute_technicals_populates_rs_vs_sector_63d(self):
        from app.services.technical_analysis_service import compute_technicals
        stock_df = _make_ohlcv_drift(n=300, drift=0.002)
        sector_df = _make_ohlcv(n=300, drift=0.001)
        ti = compute_technicals(stock_df, sector_df=sector_df)
        assert ti.rs_vs_sector_63d is not None
        assert ti.rs_vs_sector_63d > 0

    def test_compute_technicals_rs_fields_none_without_benchmarks(self):
        from app.services.technical_analysis_service import compute_technicals
        stock_df = _make_ohlcv(n=300)
        ti = compute_technicals(stock_df)  # no spy/sector
        assert ti.rs_vs_spy_20d is None
        assert ti.rs_vs_spy_63d is None
        assert ti.rs_vs_sector_20d is None
        assert ti.rs_vs_sector_63d is None

    def test_underperforming_stock_has_negative_rs(self):
        from app.services.technical_analysis_service import compute_technicals
        # Stock drifts down, benchmark drifts up
        stock_df = _make_ohlcv(n=300, drift=-0.001)
        spy_df = _make_ohlcv(n=300, drift=0.001)
        ti = compute_technicals(stock_df, spy_df=spy_df)
        assert ti.rs_vs_spy_20d is not None
        # Underperformer should have negative RS
        assert ti.rs_vs_spy_20d < 0, f"Expected negative rs_vs_spy_20d, got {ti.rs_vs_spy_20d}"

    def test_rs_fields_are_percentage_not_ratio(self):
        """Values should be % difference (can be > 1 or < -1 unlike a ratio)."""
        from app.services.technical_analysis_service import compute_rs_vs_benchmark
        stock = pd.Series([100.0] * 280 + list(np.linspace(100, 120, 20)))
        bench = pd.Series([100.0] * 280 + list(np.linspace(100, 105, 20)))
        result = compute_rs_vs_benchmark(stock, bench, period=20)
        assert result is not None
        # stock gained ~20%, bench ~5%, diff ~15%
        assert 10.0 < result < 25.0, f"Expected ~15% RS, got {result}"


# ===========================================================================
# STEP 2 — New decision labels
# ===========================================================================

class TestNewDecisionLabels:
    """recommendation_service.ALL_DECISIONS must include new labels; old BUY_NOW_MOMENTUM removed."""

    def test_buy_now_continuation_in_all_decisions(self):
        from app.services.recommendation_service import ALL_DECISIONS
        assert "BUY_NOW_CONTINUATION" in ALL_DECISIONS

    def test_oversold_rebound_candidate_in_all_decisions(self):
        from app.services.recommendation_service import ALL_DECISIONS
        assert "OVERSOLD_REBOUND_CANDIDATE" in ALL_DECISIONS

    def test_true_downtrend_avoid_in_all_decisions(self):
        from app.services.recommendation_service import ALL_DECISIONS
        assert "TRUE_DOWNTREND_AVOID" in ALL_DECISIONS

    def test_broken_support_avoid_in_all_decisions(self):
        from app.services.recommendation_service import ALL_DECISIONS
        assert "BROKEN_SUPPORT_AVOID" in ALL_DECISIONS

    def test_buy_now_momentum_removed(self):
        from app.services.recommendation_service import ALL_DECISIONS, SHORT_TERM_DECISIONS
        assert "BUY_NOW_MOMENTUM" not in ALL_DECISIONS
        assert "BUY_NOW_MOMENTUM" not in SHORT_TERM_DECISIONS

    def test_buy_now_continuation_in_short_term_decisions(self):
        from app.services.recommendation_service import SHORT_TERM_DECISIONS
        assert "BUY_NOW_CONTINUATION" in SHORT_TERM_DECISIONS


# ===========================================================================
# STEP 3 — Precise BUY_ON_PULLBACK logic
# ===========================================================================

class TestIsPullbackToSma50:
    """_is_pullback_to_sma50() must enforce exact SMA50, RSI, and volume thresholds."""

    def _ti_pullback(self, **overrides) -> TechnicalIndicators:
        """Perfect pullback-to-SMA50 scenario."""
        base = dict(
            sma50_relative=1.0,        # 1% above SMA50 (in range)
            sma20_relative=3.0,        # 3% above SMA20
            rsi_14=50.0,               # RSI in 40-58 range
            rsi_slope=0.5,             # stabilizing
            volume_dryup_ratio=0.75,   # < 0.85
            perf_1m=-5.0,              # >= -12%
            perf_3m=5.0,               # positive
            rs_vs_sector_20d=0.0,      # >= -3%
            sma50_slope=0.1,
            sma200_relative=5.0,
            trend=TrendClassification(label="strong_uptrend", description=""),
            support_resistance=SupportResistanceLevels(
                supports=[95.0], resistances=[110.0],
                nearest_support=95.0, nearest_resistance=110.0,
            ),
        )
        base.update(overrides)
        return TechnicalIndicators(**base)

    def test_perfect_pullback_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback()
        assert _is_pullback_to_sma50(ti) is True

    def test_sma50_below_minus3_pct_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(sma50_relative=-3.1)  # too far below SMA50
        assert _is_pullback_to_sma50(ti) is False

    def test_sma50_above_plus5_pct_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(sma50_relative=5.1)  # too extended above SMA50
        assert _is_pullback_to_sma50(ti) is False

    def test_sma50_at_minus3_boundary_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(sma50_relative=-3.0)
        assert _is_pullback_to_sma50(ti) is True

    def test_sma50_at_plus5_boundary_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(sma50_relative=5.0)
        assert _is_pullback_to_sma50(ti) is True

    def test_rsi_39_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(rsi_14=39.0)
        assert _is_pullback_to_sma50(ti) is False

    def test_rsi_40_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(rsi_14=40.0)
        assert _is_pullback_to_sma50(ti) is True

    def test_rsi_58_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(rsi_14=58.0)
        assert _is_pullback_to_sma50(ti) is True

    def test_rsi_59_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(rsi_14=59.0)
        assert _is_pullback_to_sma50(ti) is False

    def test_volume_dryup_086_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(volume_dryup_ratio=0.86)  # > 0.85 threshold
        assert _is_pullback_to_sma50(ti) is False

    def test_volume_dryup_084_returns_true(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(volume_dryup_ratio=0.84)
        assert _is_pullback_to_sma50(ti) is True

    def test_perf_1m_below_minus12_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(perf_1m=-12.1)
        assert _is_pullback_to_sma50(ti) is False

    def test_rs_sector_below_minus3_returns_false(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(rs_vs_sector_20d=-3.1)
        assert _is_pullback_to_sma50(ti) is False

    def test_none_volume_dryup_does_not_crash(self):
        from app.services.recommendation_service import _is_pullback_to_sma50
        # When volume_dryup_ratio is None, should not crash — treat as not a clean dry-up
        ti = self._ti_pullback(volume_dryup_ratio=None)
        result = _is_pullback_to_sma50(ti)
        assert isinstance(result, bool)

    def test_hyper_growth_allows_wider_range(self):
        """Hyper-growth: allow SMA50 [-5%, +8%], RSI 38-62."""
        from app.services.recommendation_service import _is_pullback_to_sma50
        ti = self._ti_pullback(sma50_relative=-4.5, rsi_14=38.5)
        # Without archetype context, standard rules apply (fails)
        # With HYPER_GROWTH archetype, should pass
        result_hyper = _is_pullback_to_sma50(ti, archetype="HYPER_GROWTH")
        assert result_hyper is True


# ===========================================================================
# STEP 4 — Split AVOID_BAD_CHART
# ===========================================================================

class TestClassifyBadChart:
    """_classify_bad_chart() returns one of three sub-labels based on technicals."""

    def _make_downtrend_ti(self, **overrides) -> TechnicalIndicators:
        base = dict(
            trend=TrendClassification(label="downtrend", description=""),
            rsi_14=38.0,
            rsi_slope=-2.0,
            sma50_relative=-8.0,
            sma200_relative=-5.0,
            sma200_slope=-0.2,
            rs_vs_spy_63d=-7.0,
            rs_vs_sector_63d=-4.0,
            updown_volume_ratio=0.6,    # < 1/1.3 ≈ 0.77
            volume_dryup_ratio=1.3,     # elevated but < 1.5 (not a fresh support break)
            change_from_open_percent=-0.5,  # slightly red but not a hard break
            support_resistance=SupportResistanceLevels(
                supports=[], resistances=[], nearest_support=None, nearest_resistance=None,
            ),
        )
        base.update(overrides)
        return TechnicalIndicators(**base)

    def test_true_downtrend_when_all_conditions_met(self):
        from app.services.recommendation_service import _classify_bad_chart
        ti = self._make_downtrend_ti()
        result = _classify_bad_chart(ti)
        assert result == "TRUE_DOWNTREND_AVOID"

    def test_oversold_rebound_when_rsi_turning_up(self):
        from app.services.recommendation_service import _classify_bad_chart
        ti = self._make_downtrend_ti(
            rsi_14=35.0,         # in 25-42 range
            rsi_slope=2.0,       # turning up (positive)
            perf_1w=1.0,         # recent improvement (5D return proxy)
            breakout_volume_multiple=1.3,  # >= 1.2
            sma200_slope=0.1,    # not negative
        )
        result = _classify_bad_chart(ti)
        assert result == "OVERSOLD_REBOUND_CANDIDATE"

    def test_broken_support_when_heavy_vol_and_red_close(self):
        from app.services.recommendation_service import _classify_bad_chart
        ti = self._make_downtrend_ti(
            rsi_14=37.0,               # < 40
            rsi_slope=-3.0,            # falling
            volume_dryup_ratio=1.6,    # > 1.5 (heavy vol on break)
            change_from_open_percent=-2.0,  # < -1% (weak close)
            sma200_slope=-0.1,
            perf_1w=None,              # no recent improvement
        )
        result = _classify_bad_chart(ti)
        assert result == "BROKEN_SUPPORT_AVOID"

    def test_rsi_above_42_not_rebound(self):
        """RSI > 42 should not qualify for OVERSOLD_REBOUND_CANDIDATE."""
        from app.services.recommendation_service import _classify_bad_chart
        ti = self._make_downtrend_ti(
            rsi_14=43.0,   # above 42 threshold
            rsi_slope=2.0,
            perf_5d=1.0,
            breakout_volume_multiple=1.3,
        )
        result = _classify_bad_chart(ti)
        # Should fall through to TRUE_DOWNTREND_AVOID or BROKEN_SUPPORT_AVOID, not REBOUND
        assert result != "OVERSOLD_REBOUND_CANDIDATE"

    def test_rsi_below_25_not_rebound(self):
        """RSI < 25 should not qualify for OVERSOLD_REBOUND_CANDIDATE (too extreme)."""
        from app.services.recommendation_service import _classify_bad_chart
        ti = self._make_downtrend_ti(
            rsi_14=24.0,
            rsi_slope=2.0,
            perf_5d=1.0,
            breakout_volume_multiple=1.3,
        )
        result = _classify_bad_chart(ti)
        assert result != "OVERSOLD_REBOUND_CANDIDATE"


# ===========================================================================
# STEP 5 — BUY_NOW_CONTINUATION strict criteria
# ===========================================================================

class TestBuyNowContinuation:
    """Short-term v2 should emit BUY_NOW_CONTINUATION with strict criteria."""

    def _bullish_ti(self, **overrides) -> TechnicalIndicators:
        base = dict(
            rsi_14=62.0,         # 55-68
            rsi_slope=1.5,       # >= 0
            sma20_relative=3.0,  # 0-5%
            sma50_relative=8.0,  # 0-12%
            sma20_slope=0.3,
            sma50_slope=0.2,
            sma200_slope=0.1,
            perf_1w=3.0,         # 0-6%
            perf_1m=8.0,         # 3-15%
            breakout_volume_multiple=1.4,  # >= 1.3
            rs_vs_spy_20d=2.0,   # > 0
            rs_vs_spy_63d=4.0,   # > 0
            rs_vs_sector_20d=1.5, # > 0
            trend=TrendClassification(label="strong_uptrend", description=""),
            is_extended=False,
            support_resistance=SupportResistanceLevels(
                supports=[95.0], resistances=[110.0],
                nearest_support=95.0, nearest_resistance=110.0,
            ),
        )
        base.update(overrides)
        return TechnicalIndicators(**base)

    def test_perfect_setup_returns_buy_now_continuation(self):
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti()
        result = _decide_short_term_v2(75.0, ti)
        assert result == "BUY_NOW_CONTINUATION"

    def test_rsi_54_below_threshold_not_continuation(self):
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(rsi_14=54.0)
        result = _decide_short_term_v2(75.0, ti)
        assert result != "BUY_NOW_CONTINUATION"

    def test_rsi_55_at_threshold_is_continuation(self):
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(rsi_14=55.0)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "BUY_NOW_CONTINUATION"

    def test_rsi_68_at_upper_threshold_is_continuation(self):
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(rsi_14=68.0)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "BUY_NOW_CONTINUATION"

    def test_sma20_at_plus5_point1_routes_to_extended(self):
        """SMA20 > +5% → BUY_STARTER_EXTENDED (not BUY_NOW_CONTINUATION)."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(sma20_relative=5.1)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "BUY_STARTER_STRONG_BUT_EXTENDED"

    def test_sma20_at_plus10_point1_routes_to_wait(self):
        """SMA20 > +10% → WAIT_FOR_PULLBACK."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(sma20_relative=10.1)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "WAIT_FOR_PULLBACK"

    def test_1w_return_above_10_pct_routes_to_wait(self):
        """1W return > 10% → WAIT_FOR_PULLBACK."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(perf_1w=10.1)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "WAIT_FOR_PULLBACK"

    def test_1m_return_above_25_pct_routes_to_wait(self):
        """1M return > 25% → WAIT_FOR_PULLBACK."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(perf_1m=25.1)
        result = _decide_short_term_v2(75.0, ti)
        assert result == "WAIT_FOR_PULLBACK"

    def test_negative_rs_spy_20d_blocks_continuation(self):
        """RS20_SPY <= 0 should prevent BUY_NOW_CONTINUATION."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(rs_vs_spy_20d=-0.1)
        result = _decide_short_term_v2(75.0, ti)
        assert result != "BUY_NOW_CONTINUATION"

    def test_low_volume_blocks_continuation(self):
        """Relative volume < 1.3 should prevent BUY_NOW_CONTINUATION."""
        from app.services.recommendation_service import _decide_short_term_v2
        ti = self._bullish_ti(breakout_volume_multiple=1.2)
        result = _decide_short_term_v2(75.0, ti)
        assert result != "BUY_NOW_CONTINUATION"


# ===========================================================================
# STEP 6 — Relative strength helper functions
# ===========================================================================

class TestRsHelpers:
    """_rs_continuation_ok(), _rs_leader(), _rs_avoid() helper functions."""

    def _ti(self, **kw) -> TechnicalIndicators:
        return _make_ti(**kw)

    def test_rs_continuation_ok_all_positive(self):
        from app.services.recommendation_service import _rs_continuation_ok
        ti = self._ti(rs_vs_spy_20d=1.0, rs_vs_spy_63d=2.0, rs_vs_sector_20d=0.5)
        assert _rs_continuation_ok(ti) is True

    def test_rs_continuation_ok_spy_20d_zero_blocks(self):
        from app.services.recommendation_service import _rs_continuation_ok
        ti = self._ti(rs_vs_spy_20d=-0.1, rs_vs_spy_63d=2.0, rs_vs_sector_20d=0.5)
        assert _rs_continuation_ok(ti) is False

    def test_rs_continuation_ok_sector_20d_zero_blocks(self):
        from app.services.recommendation_service import _rs_continuation_ok
        ti = self._ti(rs_vs_spy_20d=1.0, rs_vs_spy_63d=2.0, rs_vs_sector_20d=-0.1)
        assert _rs_continuation_ok(ti) is False

    def test_rs_leader_above_thresholds(self):
        from app.services.recommendation_service import _rs_leader
        ti = self._ti(rs_vs_spy_20d=3.5, rs_vs_spy_63d=5.5, rs_vs_sector_20d=2.5)
        assert _rs_leader(ti) is True

    def test_rs_leader_spy_20d_at_3_pct(self):
        """Boundary: RS20_SPY exactly 3% → leader."""
        from app.services.recommendation_service import _rs_leader
        ti = self._ti(rs_vs_spy_20d=3.0, rs_vs_spy_63d=5.5, rs_vs_sector_20d=2.5)
        assert _rs_leader(ti) is True

    def test_rs_leader_spy_20d_below_3_pct(self):
        """RS20_SPY < 3% → not leader."""
        from app.services.recommendation_service import _rs_leader
        ti = self._ti(rs_vs_spy_20d=2.9, rs_vs_spy_63d=5.5, rs_vs_sector_20d=2.5)
        assert _rs_leader(ti) is False

    def test_rs_avoid_spy_20d_below_minus5(self):
        from app.services.recommendation_service import _rs_avoid
        ti = self._ti(rs_vs_spy_20d=-5.1, rs_vs_spy_63d=0.0, rs_vs_sector_20d=0.0)
        assert _rs_avoid(ti) is True

    def test_rs_avoid_spy_63d_below_minus10(self):
        from app.services.recommendation_service import _rs_avoid
        ti = self._ti(rs_vs_spy_20d=0.0, rs_vs_spy_63d=-10.1, rs_vs_sector_20d=0.0)
        assert _rs_avoid(ti) is True

    def test_rs_avoid_sector_20d_below_minus5(self):
        from app.services.recommendation_service import _rs_avoid
        ti = self._ti(rs_vs_spy_20d=0.0, rs_vs_spy_63d=0.0, rs_vs_sector_20d=-5.1)
        assert _rs_avoid(ti) is True

    def test_rs_avoid_all_positive_returns_false(self):
        from app.services.recommendation_service import _rs_avoid
        ti = self._ti(rs_vs_spy_20d=1.0, rs_vs_spy_63d=2.0, rs_vs_sector_20d=1.0)
        assert _rs_avoid(ti) is False

    def test_rs_helpers_handle_none_gracefully(self):
        from app.services.recommendation_service import _rs_continuation_ok, _rs_leader, _rs_avoid
        ti = TechnicalIndicators()  # all None
        # Should not crash
        assert isinstance(_rs_continuation_ok(ti), bool)
        assert isinstance(_rs_leader(ti), bool)
        assert isinstance(_rs_avoid(ti), bool)


# ===========================================================================
# STEP 7 — Regime-specific thresholds
# ===========================================================================

class TestRegimeThresholds:
    """_get_regime_thresholds() returns correct thresholds per regime."""

    def test_liquidity_rally_rsi_upper_is_74(self):
        from app.services.recommendation_service import _get_regime_thresholds
        t = _get_regime_thresholds(MarketRegime.LIQUIDITY_RALLY)
        assert t.rsi_max >= 74

    def test_bull_risk_on_rsi_upper_is_68(self):
        from app.services.recommendation_service import _get_regime_thresholds
        t = _get_regime_thresholds(MarketRegime.BULL_RISK_ON)
        assert t.rsi_max == 68

    def test_sideways_choppy_lower_rsi_max(self):
        from app.services.recommendation_service import _get_regime_thresholds
        t = _get_regime_thresholds(MarketRegime.SIDEWAYS_CHOPPY)
        assert t.rsi_max <= 58

    def test_liquidity_rally_sma20_max_is_8(self):
        from app.services.recommendation_service import _get_regime_thresholds
        t = _get_regime_thresholds(MarketRegime.LIQUIDITY_RALLY)
        assert t.sma20_max >= 8.0

    def test_bull_risk_on_sma20_max_is_5(self):
        from app.services.recommendation_service import _get_regime_thresholds
        t = _get_regime_thresholds(MarketRegime.BULL_RISK_ON)
        assert t.sma20_max == 5.0

    def test_liquidity_rally_allows_rsi_72(self):
        """With LIQUIDITY_RALLY, RSI 72 should still allow BUY_NOW_CONTINUATION."""
        from app.services.recommendation_service import _decide_short_term_v2
        from app.models.market import MarketRegimeAssessment
        ti = _make_ti(rsi_14=72.0, sma20_relative=3.0)
        regime = MarketRegimeAssessment(regime=MarketRegime.LIQUIDITY_RALLY, confidence=0.8)
        result = _decide_short_term_v2(75.0, ti, regime=regime)
        assert result == "BUY_NOW_CONTINUATION"

    def test_bull_risk_on_blocks_rsi_72(self):
        """In BULL_RISK_ON, RSI 72 exceeds threshold → not BUY_NOW_CONTINUATION."""
        from app.services.recommendation_service import _decide_short_term_v2
        from app.models.market import MarketRegimeAssessment
        ti = _make_ti(rsi_14=72.0, sma20_relative=3.0)
        regime = MarketRegimeAssessment(regime=MarketRegime.BULL_RISK_ON, confidence=0.8)
        result = _decide_short_term_v2(75.0, ti, regime=regime)
        assert result != "BUY_NOW_CONTINUATION"

    def test_bear_risk_off_blocks_buy_now_continuation(self):
        """In BEAR_RISK_OFF, BUY_NOW_CONTINUATION should not be emitted."""
        from app.services.recommendation_service import _decide_short_term_v2
        from app.models.market import MarketRegimeAssessment
        ti = _make_ti(rsi_14=62.0, sma20_relative=3.0)
        regime = MarketRegimeAssessment(regime=MarketRegime.BEAR_RISK_OFF, confidence=0.8)
        result = _decide_short_term_v2(75.0, ti, regime=regime)
        assert result != "BUY_NOW_CONTINUATION"

    def test_sideways_choppy_prefers_pullback(self):
        """In SIDEWAYS_CHOPPY, should route to BUY_ON_PULLBACK over BUY_NOW_CONTINUATION."""
        from app.services.recommendation_service import _decide_short_term_v2
        from app.models.market import MarketRegimeAssessment
        ti = _make_ti(
            rsi_14=50.0,        # in pullback RSI range
            sma50_relative=2.0,  # near SMA50
            volume_dryup_ratio=0.75,
        )
        regime = MarketRegimeAssessment(regime=MarketRegime.SIDEWAYS_CHOPPY, confidence=0.8)
        result = _decide_short_term_v2(72.0, ti, regime=regime)
        assert result == "BUY_ON_PULLBACK"


# ===========================================================================
# STEP 8 — ATR-based position sizing
# ===========================================================================

class TestAtrSizing:
    """_atr_size_multiplier() and _compute_stop_atr() tests."""

    def test_low_atr_full_size(self):
        from app.services.risk_management_service import _atr_size_multiplier
        assert _atr_size_multiplier(1.5) == pytest.approx(1.0)

    def test_normal_atr_full_size(self):
        from app.services.risk_management_service import _atr_size_multiplier
        assert _atr_size_multiplier(3.0) == pytest.approx(1.0)

    def test_high_atr_reduced_size(self):
        from app.services.risk_management_service import _atr_size_multiplier
        mult = _atr_size_multiplier(5.0)
        assert 0.5 <= mult <= 0.65, f"Expected 50-65% of target, got {mult*100:.0f}%"

    def test_extreme_atr_small_size(self):
        from app.services.risk_management_service import _atr_size_multiplier
        mult = _atr_size_multiplier(8.0)
        assert 0.25 <= mult <= 0.40, f"Expected 25-40% of target, got {mult*100:.0f}%"

    def test_compute_stop_atr_short_term_uses_1point5_multiple(self):
        from app.services.risk_management_service import _compute_stop_atr
        entry = 100.0
        atr = 2.0
        stop = _compute_stop_atr(entry, atr, "short_term")
        # stop = entry - 1.5 * ATR = 100 - 3.0 = 97.0
        assert stop == pytest.approx(97.0, rel=0.01)

    def test_compute_stop_atr_medium_term_uses_2_multiple(self):
        from app.services.risk_management_service import _compute_stop_atr
        entry = 100.0
        atr = 2.0
        stop = _compute_stop_atr(entry, atr, "medium_term")
        # stop = entry - 2.0 * ATR = 100 - 4.0 = 96.0
        assert stop == pytest.approx(96.0, rel=0.01)

    def test_atr_sizing_integrated_in_risk_management(self):
        """compute_risk_management should apply ATR-based sizing when atr_percent available."""
        from app.services.risk_management_service import compute_risk_management
        ti = _make_ti(atr=3.0, atr_percent=3.0)
        _, exit_plan, _, sizing = compute_risk_management(
            price=100.0,
            technicals=ti,
            decision="BUY_NOW_CONTINUATION",
            risk_profile="moderate",
        )
        # Stop should be ATR-based when atr available
        assert exit_plan.stop_loss is not None
        # For moderate, normal ATR → no reduction
        assert sizing.suggested_starter_pct_of_full == 25

    def test_high_atr_reduces_position_size(self):
        """When ATR% > 7, position size should be reduced."""
        from app.services.risk_management_service import compute_risk_management
        ti = _make_ti(atr=8.0, atr_percent=8.0)
        _, _, _, sizing = compute_risk_management(
            price=100.0,
            technicals=ti,
            decision="BUY_NOW_CONTINUATION",
            risk_profile="moderate",
        )
        # 25 * 0.30 = ~7.5, round to int
        assert sizing.suggested_starter_pct_of_full < 20


# ===========================================================================
# STEP 9 — Context-specific relative volume scoring
# ===========================================================================

class TestContextVolumeScoring:
    """score_volume_accumulation() should score based on context."""

    def _make_ti_vol(self, **kw) -> TechnicalIndicators:
        defaults = dict(
            obv_trend=1,
            chaikin_money_flow=0.15,
            updown_volume_ratio=1.2,
            vwap_deviation=1.0,
        )
        defaults.update(kw)
        return TechnicalIndicators(**defaults)

    def test_breakout_vol_green_close_scores_high(self):
        """Breakout: rel vol >= 1.8 + green close (change_from_open > 0) → high score."""
        from app.services.signal_card_service import score_volume_accumulation
        ti = self._make_ti_vol(
            breakout_volume_multiple=2.0,
            change_from_open_percent=1.5,  # green close
            volume_dryup_ratio=1.0,
        )
        card = score_volume_accumulation(ti)
        assert card.score >= 65, f"Expected high score for breakout, got {card.score}"

    def test_pullback_dryup_scores_well(self):
        """Pullback: dry-up ratio < 0.85 → volume score should be good."""
        from app.services.signal_card_service import score_volume_accumulation
        ti = self._make_ti_vol(
            breakout_volume_multiple=0.7,   # low volume (pullback)
            volume_dryup_ratio=0.6,         # strong dry-up
            change_from_open_percent=-0.3,   # slight red
        )
        card = score_volume_accumulation(ti)
        assert card.score >= 50, f"Expected decent score for volume dry-up, got {card.score}"

    def test_high_vol_red_close_penalized(self):
        """High volume + red close = distribution → should score lower than high vol + green."""
        from app.services.signal_card_service import score_volume_accumulation
        ti_red = self._make_ti_vol(
            breakout_volume_multiple=2.0,
            change_from_open_percent=-2.5,  # red close (distribution)
            volume_dryup_ratio=1.8,
        )
        ti_green = self._make_ti_vol(
            breakout_volume_multiple=2.0,
            change_from_open_percent=2.5,   # green close (breakout)
            volume_dryup_ratio=0.8,
        )
        card_red = score_volume_accumulation(ti_red)
        card_green = score_volume_accumulation(ti_green)
        assert card_red.score < card_green.score, (
            f"Distribution (red) score {card_red.score} should be < breakout (green) score {card_green.score}"
        )


# ===========================================================================
# STEP 10 — 1W/1M performance bucket gates
# ===========================================================================

class TestPerfGates:
    """_perf_gates() helper enforces 1W/1M return thresholds."""

    def test_continuation_valid_perf(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=3.0, perf_1m=8.0)
        assert _perf_gates(ti, "continuation") is True

    def test_continuation_1w_above_6_blocked(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=6.1, perf_1m=8.0)
        assert _perf_gates(ti, "continuation") is False

    def test_continuation_1m_below_3_blocked(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=3.0, perf_1m=2.9)
        assert _perf_gates(ti, "continuation") is False

    def test_continuation_1m_above_15_blocked(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=3.0, perf_1m=15.1)
        assert _perf_gates(ti, "continuation") is False

    def test_chasing_1w_above_10(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=10.1, perf_1m=8.0)
        assert _perf_gates(ti, "chasing") is True

    def test_chasing_1m_above_25(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=3.0, perf_1m=25.1)
        assert _perf_gates(ti, "chasing") is True

    def test_chasing_normal_perf_false(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1w=3.0, perf_1m=8.0)
        assert _perf_gates(ti, "chasing") is False

    def test_rebound_1m_below_minus10(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1m=-11.0, perf_1w=0.5, rsi_slope=2.0)
        assert _perf_gates(ti, "rebound") is True

    def test_rebound_1m_above_minus10_false(self):
        from app.services.recommendation_service import _perf_gates
        ti = _make_ti(perf_1m=-9.0, perf_1w=0.5, rsi_slope=2.0)
        assert _perf_gates(ti, "rebound") is False

    def test_perf_gates_handles_none(self):
        from app.services.recommendation_service import _perf_gates
        ti = TechnicalIndicators()  # all None
        # Should not crash
        assert isinstance(_perf_gates(ti, "continuation"), bool)
        assert isinstance(_perf_gates(ti, "chasing"), bool)
        assert isinstance(_perf_gates(ti, "rebound"), bool)


# ===========================================================================
# STEP 11 — 52-week high distance classifier
# ===========================================================================

class TestClassify52WPosition:
    """_classify_52w_position() buckets dist_from_52w_high into 5 categories."""

    def test_near_high_bucket(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-1.5)  # 1.5% below 52W high
        assert _classify_52w_position(ti) == "near_52w_high"

    def test_healthy_pullback_bucket(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-6.0)
        assert _classify_52w_position(ti) == "healthy_pullback"

    def test_extended_pullback_bucket(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-12.0)
        assert _classify_52w_position(ti) == "extended_pullback"

    def test_rebound_territory_bucket(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-25.0)
        assert _classify_52w_position(ti) == "rebound_territory"

    def test_avoid_zone_bucket(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-40.0)
        assert _classify_52w_position(ti) == "avoid_zone"

    def test_boundary_near_high_at_minus3(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-3.0)
        assert _classify_52w_position(ti) == "near_52w_high"

    def test_boundary_healthy_pullback_at_minus3_point1(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=-3.1)
        assert _classify_52w_position(ti) == "healthy_pullback"

    def test_none_dist_returns_unknown(self):
        from app.services.recommendation_service import _classify_52w_position
        ti = _make_ti(dist_from_52w_high=None)
        assert _classify_52w_position(ti) == "unknown"


# ===========================================================================
# STEP 12 — Entry timing RSI split in signal_card_service
# ===========================================================================

class TestEntryTimingRsiSplit:
    """score_entry_timing() should score RSI by continuation/pullback/rebound/overbought context."""

    def _make_ti_entry(self, rsi: float, rsi_slope: float = 1.0) -> TechnicalIndicators:
        return TechnicalIndicators(
            rsi_14=rsi,
            rsi_slope=rsi_slope,
            stochastic_rsi=0.4,
            vwap_deviation=1.0,
            bollinger_band_position=0.5,
            ema8_relative=1.0,
            gap_percent=0.0,
        )

    def test_continuation_rsi_60_scores_highest(self):
        """RSI in 55-68 (continuation) should score highest among RSI components."""
        from app.services.signal_card_service import score_entry_timing
        ti_60 = self._make_ti_entry(60.0)
        ti_80 = self._make_ti_entry(80.0)
        card_60 = score_entry_timing(ti_60)
        card_80 = score_entry_timing(ti_80)
        assert card_60.score > card_80.score, (
            f"RSI 60 score {card_60.score} should be > RSI 80 score {card_80.score}"
        )

    def test_pullback_rsi_48_scores_well(self):
        """RSI in 40-55 (pullback sweet spot) should score decently."""
        from app.services.signal_card_service import score_entry_timing
        ti = self._make_ti_entry(48.0)
        card = score_entry_timing(ti)
        assert card.score >= 45, f"Pullback RSI 48 should score >= 45, got {card.score}"

    def test_rebound_rsi_33_scores_above_floor(self):
        """RSI in 25-42 (rebound candidate) should score above overbought RSI 80."""
        from app.services.signal_card_service import score_entry_timing
        ti_33 = self._make_ti_entry(33.0, rsi_slope=3.0)  # turning up
        ti_80 = self._make_ti_entry(80.0)
        card_33 = score_entry_timing(ti_33)
        card_80 = score_entry_timing(ti_80)
        assert card_33.score >= card_80.score, (
            f"Rebound RSI 33 (turning up) score {card_33.score} should be >= overbought RSI 80 score {card_80.score}"
        )

    def test_overbought_rsi_80_scores_low(self):
        """RSI > 76 → low RSI component score."""
        from app.services.signal_card_service import score_entry_timing
        ti = self._make_ti_entry(80.0)
        card = score_entry_timing(ti)
        # Not necessarily the lowest overall, but RSI contribution should be small
        assert card.score < 65, f"Overbought RSI 80 should score < 65, got {card.score}"

    def test_extended_rsi_72_scores_between_continuation_and_overbought(self):
        """RSI 68-76 (extended) should score between continuation (55-68) and overbought (>76)."""
        from app.services.signal_card_service import score_entry_timing
        ti_62 = self._make_ti_entry(62.0)
        ti_72 = self._make_ti_entry(72.0)
        ti_80 = self._make_ti_entry(80.0)
        card_62 = score_entry_timing(ti_62)
        card_72 = score_entry_timing(ti_72)
        card_80 = score_entry_timing(ti_80)
        assert card_62.score >= card_72.score >= card_80.score, (
            f"RSI 62:{card_62.score} >= RSI 72:{card_72.score} >= RSI 80:{card_80.score}"
        )
