"""Stage 2: FeatureSnapshot — verify build_feature_snapshot produces correct output."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.features.feature_builder import build_feature_snapshot
from app.features.feature_snapshot import FeatureSnapshot
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import MarketData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, n))
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    high = prices * (1 + abs(rng.normal(0, 0.005, n)))
    low = prices * (1 - abs(rng.normal(0, 0.005, n)))
    volume = rng.integers(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame({"Close": prices, "High": high, "Low": low, "Volume": volume}, index=dates)


def _make_fundamentals(**kwargs) -> FundamentalData:
    defaults = dict(
        gross_margin=0.55,
        operating_margin=0.20,
        revenue_growth_yoy=0.25,
        roe=18.0,
        free_cash_flow=1e9,
        debt_to_equity=0.5,
        current_ratio=2.0,
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _make_valuation(**kwargs) -> ValuationData:
    defaults = dict(forward_pe=22.0, peg_ratio=1.5, price_to_sales=4.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


def _make_market_data(**kwargs) -> MarketData:
    defaults = dict(
        ticker="TEST",
        current_price=100.0,
        previous_close=98.0,
        open=99.0,
        day_high=102.0,
        day_low=97.0,
        volume=5_000_000,
        avg_volume_30d=5_000_000,
        market_cap=1e11,
    )
    defaults.update(kwargs)
    return MarketData(**defaults)


def _make_earnings(**kwargs) -> EarningsData:
    defaults = dict(beat_rate=0.75, avg_eps_surprise_pct=5.0, within_30_days=False)
    defaults.update(kwargs)
    return EarningsData(**defaults)


def _build(seed: int = 42) -> FeatureSnapshot:
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300, seed=seed)
    technicals = compute_technicals(df)
    return build_feature_snapshot(
        ticker="TEST",
        price=float(df["Close"].iloc[-1]),
        technicals=technicals,
        fundamentals=_make_fundamentals(),
        valuation=_make_valuation(),
        earnings=_make_earnings(),
        market_data=_make_market_data(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_feature_snapshot_builds():
    snap = _build()
    assert snap is not None
    assert isinstance(snap, FeatureSnapshot)


def test_ticker_set():
    snap = _build()
    assert snap.ticker == "TEST"


def test_price_positive():
    snap = _build()
    assert snap.price > 0


def test_fundamental_fields_mapped():
    snap = _build()
    assert snap.gross_margin == pytest.approx(0.55)
    assert snap.operating_margin == pytest.approx(0.20)
    assert snap.sales_growth_yoy == pytest.approx(0.25)
    assert snap.roe == pytest.approx(18.0)
    assert snap.free_cash_flow == pytest.approx(1e9)
    assert snap.debt_to_equity == pytest.approx(0.5)
    assert snap.current_ratio == pytest.approx(2.0)


def test_valuation_fields_mapped():
    snap = _build()
    assert snap.forward_pe == pytest.approx(22.0)
    assert snap.peg_ratio == pytest.approx(1.5)
    assert snap.price_to_sales == pytest.approx(4.0)


def test_earnings_fields_mapped():
    snap = _build()
    assert snap.beat_rate == pytest.approx(0.75)
    assert snap.avg_eps_surprise_pct == pytest.approx(5.0)
    assert snap.earnings_within_30_days is False


def test_market_data_mapped():
    snap = _build()
    assert snap.market_cap == pytest.approx(1e11)
    assert snap.avg_volume == pytest.approx(5_000_000)


def test_technical_fields_populated():
    snap = _build()
    assert snap.rsi14 is not None
    assert snap.sma20_relative is not None
    assert snap.sma200_relative is not None


def test_trend_label_set():
    snap = _build()
    assert snap.trend_label in ("strong_uptrend", "weak_uptrend", "sideways", "downtrend", "unknown")


def test_to_dict_is_flat():
    snap = _build()
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert "rsi14" in d
    assert "gross_margin" in d
    assert "ticker" in d


def test_to_dict_ticker_matches():
    snap = _build()
    assert snap.to_dict()["ticker"] == "TEST"


def test_missing_data_graceful():
    """FeatureSnapshot should still build when optional fields are None."""
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300)
    technicals = compute_technicals(df)
    snap = build_feature_snapshot(
        ticker="EMPTY",
        price=50.0,
        technicals=technicals,
        fundamentals=FundamentalData(),
        valuation=ValuationData(),
        earnings=EarningsData(),
    )
    assert snap is not None
    assert snap.gross_margin is None
    assert snap.roe is None


def test_earnings_within_30_days():
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300)
    technicals = compute_technicals(df)
    earnings = EarningsData(within_30_days=True, next_earnings_date="2026-06-15")
    snap = build_feature_snapshot(
        ticker="EARN",
        price=100.0,
        technicals=technicals,
        fundamentals=_make_fundamentals(),
        valuation=_make_valuation(),
        earnings=earnings,
    )
    assert snap.earnings_within_30_days is True
