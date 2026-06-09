import pandas as pd

from codex_backed.features.feature_cache import load_or_build_feature_rows
from codex_backed.features.historical_builder import HistoricalFeatureOptions, build_historical_feature_rows


def test_historical_builder_computes_setup_critical_fields():
    bars_by_ticker = {
        "SPY": _bars("2023-01-02", 280, start=380.0, step=0.15),
        "TST": _bars("2023-01-02", 280, start=100.0, step=0.25),
    }
    start = bars_by_ticker["TST"][230]["date"]
    end = bars_by_ticker["TST"][260]["date"]

    rows = build_historical_feature_rows(
        bars_by_ticker,
        tickers=["TST"],
        options=HistoricalFeatureOptions(
            start=start,
            end=end,
            horizons={"short_term", "medium_term"},
            signal_frequency="weekly",
        ),
    )

    assert rows
    row = rows[0]
    assert row["ticker"] == "TST"
    assert row["horizon"] in {"short_term", "medium_term"}
    for field in [
        "sma50_relative",
        "sma50_slope",
        "rsi14",
        "rsi_slope",
        "atr_percent",
        "perf_1w",
        "volume_dryup_ratio",
        "breakout_volume_multiple",
        "dist_from_20d_high",
        "dist_from_52w_high",
        "rs_vs_spy_20d",
    ]:
        assert row[field] is not None, field
    assert row["market_regime"] in {"BULL_RISK_ON", "BEAR_RISK_OFF", "SIDEWAYS_CHOPPY", "LIQUIDITY_RALLY"}


def test_feature_cache_hits_when_metadata_matches(tmp_path):
    calls = {"count": 0}

    def build_rows():
        calls["count"] += 1
        return [{"ticker": "TST", "date": "2024-01-01", "price": 100, "horizon": "short_term"}]

    cache_path = tmp_path / "features.pkl"
    metadata = {"source": "native", "tickers": ["TST"], "start": "2024-01-01", "end": "2024-01-31"}

    first = load_or_build_feature_rows(
        cache_path=cache_path,
        metadata=metadata,
        rebuild=False,
        builder=build_rows,
    )
    second = load_or_build_feature_rows(
        cache_path=cache_path,
        metadata=metadata,
        rebuild=False,
        builder=build_rows,
    )

    assert first.status == "rebuilt"
    assert second.status == "hit"
    assert first.rows == second.rows
    assert calls["count"] == 1


def test_feature_cache_rebuilds_when_metadata_changes(tmp_path):
    calls = {"count": 0}

    def build_rows():
        calls["count"] += 1
        return [{"ticker": "TST", "date": "2024-01-01", "price": 100 + calls["count"], "horizon": "short_term"}]

    cache_path = tmp_path / "features.pkl"
    load_or_build_feature_rows(
        cache_path=cache_path,
        metadata={"source": "native", "tickers": ["TST"]},
        rebuild=False,
        builder=build_rows,
    )
    changed = load_or_build_feature_rows(
        cache_path=cache_path,
        metadata={"source": "native", "tickers": ["TST", "ABC"]},
        rebuild=False,
        builder=build_rows,
    )

    assert changed.status == "rebuilt"
    assert changed.rows[0]["price"] == 102
    assert calls["count"] == 2


def _bars(start_date: str, periods: int, *, start: float, step: float) -> list[dict]:
    rows = []
    dates = pd.bdate_range(start_date, periods=periods)
    for idx, date in enumerate(dates):
        close = start + idx * step + (1.5 if idx % 11 == 0 else -1.0 if idx % 7 == 0 else 0.0)
        rows.append(
            {
                "date": date.date().isoformat(),
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + idx * 1000,
            }
        )
    return rows
