"""Stage 1: Verify all copied services import and compute without error."""
import numpy as np
import pandas as pd
import pytest

from app.algo_config import AlgoConfig, get_algo_config, reset_algo_config


# ---------------------------------------------------------------------------
# AlgoConfig
# ---------------------------------------------------------------------------

def test_algo_config_loads():
    reset_algo_config()
    cfg = get_algo_config()
    assert cfg is not None


def test_algo_config_has_required_sections():
    cfg = get_algo_config()
    assert cfg.technical_indicators
    assert cfg.technical_scoring
    assert cfg.extension_detection
    assert cfg.stock_archetype
    assert cfg.market_regime
    assert cfg.risk_management
    assert cfg.valuation


def test_algo_config_has_quality_gate():
    cfg = get_algo_config()
    qg = cfg.quality_gate
    assert "gross_margin_min" in qg
    assert "op_margin_min" in qg
    assert "roe_min" in qg
    assert "debt_equity_max" in qg
    assert "current_ratio_min" in qg


def test_algo_config_no_old_sections():
    cfg = get_algo_config()
    # These sections belong to the deleted engine and should not exist
    with pytest.raises((KeyError, AttributeError)):
        _ = cfg._data["signal_cards"]
    with pytest.raises((KeyError, AttributeError)):
        _ = cfg._data["scoring"]
    with pytest.raises((KeyError, AttributeError)):
        _ = cfg._data["decision_logic"]


# ---------------------------------------------------------------------------
# Service imports
# ---------------------------------------------------------------------------

def test_imports():
    from app.services.technical_analysis_service import compute_technicals
    from app.services.fundamental_analysis_service import score_fundamentals
    from app.services.valuation_analysis_service import score_valuation
    from app.services.market_regime_service import classify_regime
    from app.services.stock_archetype_service import classify_archetype
    from app.services.risk_management_service import compute_risk_management
    from app.features.feature_builder import build_feature_snapshot
    from app.features.feature_snapshot import FeatureSnapshot
    from app.engine.rule_engine import RuleEngine


# ---------------------------------------------------------------------------
# Synthetic price data helper
# ---------------------------------------------------------------------------

def _make_price_df(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, n))
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    high = prices * (1 + abs(rng.normal(0, 0.005, n)))
    low = prices * (1 - abs(rng.normal(0, 0.005, n)))
    volume = rng.integers(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame({"Close": prices, "High": high, "Low": low, "Volume": volume}, index=dates)


# ---------------------------------------------------------------------------
# Technical analysis
# ---------------------------------------------------------------------------

def test_compute_technicals_runs():
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300)
    result = compute_technicals(df)
    assert result is not None
    assert result.ma_20 is not None


def test_compute_technicals_has_key_indicators():
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300)
    result = compute_technicals(df)
    assert result.rsi_14 is not None
    assert result.ma_20 is not None
    assert result.ma_50 is not None
    assert result.ma_200 is not None
    assert result.atr is not None


def test_compute_technicals_with_spy():
    from app.services.technical_analysis_service import compute_technicals
    df = _make_price_df(300, seed=1)
    spy = _make_price_df(300, seed=2)
    result = compute_technicals(df, spy_df=spy)
    assert result is not None


# ---------------------------------------------------------------------------
# Fundamental analysis
# ---------------------------------------------------------------------------

def test_score_fundamentals_healthy():
    from app.services.fundamental_analysis_service import score_fundamentals
    from app.models.fundamentals import FundamentalData
    data = FundamentalData(
        revenue_growth_yoy=0.25,
        eps_growth_yoy=0.30,
        gross_margin=0.60,
        operating_margin=0.22,
        free_cash_flow=1e9,
        current_ratio=2.5,
        debt_to_equity=0.3,
        roe=25.0,
        roic=18.0,
    )
    score = score_fundamentals(data)
    assert score > 60, f"Healthy fundamentals should score > 60, got {score}"


def test_score_fundamentals_deteriorating():
    from app.services.fundamental_analysis_service import score_fundamentals
    from app.models.fundamentals import FundamentalData
    data = FundamentalData(
        revenue_growth_yoy=-0.15,
        eps_growth_yoy=-0.25,
        gross_margin=0.20,
        operating_margin=-0.08,
        free_cash_flow=-5e8,
        current_ratio=0.9,
        debt_to_equity=3.5,
        roe=-10.0,
    )
    score = score_fundamentals(data)
    assert score < 50, f"Deteriorating fundamentals should score < 50, got {score}"


def test_score_fundamentals_all_none():
    from app.services.fundamental_analysis_service import score_fundamentals
    from app.models.fundamentals import FundamentalData
    score = score_fundamentals(FundamentalData())
    assert 0 <= score <= 100
