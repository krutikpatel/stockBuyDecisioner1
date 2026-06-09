from pathlib import Path

from codex_backed.config.loader import load_config_bundle
from codex_backed.entry.engine import EntryDecisionEngine
from codex_backed.entry.setup_detector import EntrySetupDetector
from codex_backed.features.snapshot import FeatureSnapshot


def _bundle():
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    return load_config_bundle(config_dir)


def test_setup_detector_selects_growth_leader_pullback():
    bundle = _bundle()
    detector = EntrySetupDetector(bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="MSFT",
        date="2024-01-02",
        price=100,
        trend_label="strong_uptrend",
        sma20_relative=1.0,
        sma50_relative=1.0,
        sma200_relative=10.0,
        sma50_slope=0.2,
        rsi14=50,
        volume_dryup_ratio=0.7,
        rs_vs_spy_20d=1.0,
        perf_1w=0.5,
        breakout_volume_multiple=1.0,
        rsi_slope=0.1,
    )

    result = detector.detect(snapshot.to_dict())

    assert result.selected_setup == "GROWTH_LEADER_PULLBACK"
    assert "STRONG_UPTREND" in result.matched_signals
    assert "VOLUME_DRY_UP" in result.optional_signals


def test_entry_engine_routes_clean_quality_dislocation_to_buy_full():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="NVDA",
        date="2024-01-02",
        price=100,
        market_regime="BEAR_RISK_OFF",
        trend_label="downtrend",
        sma50_relative=-8.0,
        sma200_relative=-4.0,
        rsi14=40,
        rsi_slope=0.2,
        dist_from_52w_high=-30,
        volume_dryup_ratio=0.7,
    )

    decision = engine.decide(snapshot, horizon="short_term")

    assert decision.entry_strategy == "quality_dislocation"
    assert decision.entry_label == "BUY_FULL"
    assert decision.entry_score == 80
    assert decision.is_actionable


def test_entry_engine_routes_overdistressed_quality_dislocation_to_watchlist():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="NVDA",
        date="2024-01-02",
        price=100,
        market_regime="BEAR_RISK_OFF",
        trend_label="downtrend",
        sma50_relative=-8.0,
        sma200_relative=-4.0,
        rsi14=30,
        rsi_slope=0.2,
        dist_from_52w_high=-30,
        volume_dryup_ratio=0.7,
    )

    decision = engine.decide(snapshot, horizon="short_term")

    assert decision.entry_strategy == "quality_dislocation"
    assert decision.entry_label == "WATCHLIST"
    assert decision.entry_score == 100
    assert not decision.is_actionable


def test_entry_engine_routes_broad_bull_leadership_to_watchlist_only():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="AAPL",
        date="2024-01-02",
        price=100,
        market_regime="BULL_RISK_ON",
        trend_label="strong_uptrend",
        rs_vs_spy_20d=4.0,
        sma50_slope=0.4,
        sma20_relative=3.0,
    )

    decision = engine.decide(snapshot, horizon="medium_term")

    assert decision.entry_strategy == "bull_leadership"
    assert decision.entry_label == "WATCHLIST"
    assert decision.entry_score == 100


def test_entry_engine_excludes_weak_ticker_before_other_routes():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="SNOW",
        date="2024-01-02",
        price=100,
        market_regime="BULL_RISK_ON",
        trend_label="strong_uptrend",
        rs_vs_spy_20d=8.0,
        sma50_slope=0.4,
        sma20_relative=3.0,
    )

    decision = engine.decide(snapshot, horizon="medium_term")

    assert decision.entry_strategy == "no_trade"
    assert decision.entry_label == "NO_TRADE"


def test_entry_engine_blocks_growth_pullback_in_liquidity_rally():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="AAPL",
        date="2024-01-02",
        price=100,
        market_regime="LIQUIDITY_RALLY",
        trend_label="strong_uptrend",
        sma20_relative=1.0,
        sma50_relative=1.0,
        sma200_relative=10.0,
        sma50_slope=0.2,
        rsi14=50,
        volume_dryup_ratio=0.7,
        rs_vs_spy_20d=1.0,
        perf_1w=0.5,
        breakout_volume_multiple=1.0,
        rsi_slope=0.1,
    )

    decision = engine.decide(snapshot, horizon="short_term")

    assert decision.selected_setup == "GROWTH_LEADER_PULLBACK"
    assert decision.entry_strategy == "no_trade"
    assert decision.entry_label == "NO_TRADE"


def test_entry_engine_falls_back_to_no_trade():
    bundle = _bundle()
    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    snapshot = FeatureSnapshot(
        ticker="XYZ",
        date="2024-01-02",
        price=100,
        market_regime="BULL_RISK_ON",
        rsi14=70,
        sales_growth_yoy=0.0,
    )

    decision = engine.decide(snapshot, horizon="short_term")

    assert decision.entry_strategy == "no_trade"
    assert decision.entry_label == "NO_TRADE"
    assert not decision.is_actionable
