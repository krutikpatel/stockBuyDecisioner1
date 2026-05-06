"""US-009 unit tests: backtest regime and archetype segmentation."""
import pytest

from backtest.metrics import build_metrics, _by_regime, _by_archetype
from backtest.config import BENCHMARK_TICKERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal(
    ticker: str = "NVDA",
    date: str = "2025-01-06",
    horizon: str = "short_term",
    decision: str = "BUY_NOW",
    score: float = 80.0,
    forward_return: float = 5.0,
    spy_return: float = 2.0,
    qqq_return: float = 3.0,
    archetype: str = "HYPER_GROWTH",
    market_regime: str = "BULL_RISK_ON",
) -> dict:
    excess = round(forward_return - spy_return, 4) if forward_return is not None else None
    exc_qqq = round(forward_return - qqq_return, 4) if forward_return is not None else None
    return {
        "ticker": ticker,
        "date": date,
        "horizon": horizon,
        "decision": decision,
        "score": score,
        "confidence": "high",
        "archetype": archetype,
        "market_regime": market_regime,
        "price": 100.0,
        "technical_score": 75.0,
        "fundamental_score": 70.0,
        "valuation_score": 65.0,
        "earnings_score": 60.0,
        "trend": "strong_uptrend",
        "rsi": 60.0,
        "is_extended": False,
        "entry_preferred": 98.0,
        "stop_loss": 90.0,
        "first_target": 115.0,
        "forward_return": forward_return,
        "spy_return": spy_return,
        "qqq_return": qqq_return,
        "excess_return": excess,
        "excess_return_vs_qqq": exc_qqq,
    }


# ---------------------------------------------------------------------------
# BENCHMARK_TICKERS test
# ---------------------------------------------------------------------------

class TestBenchmarkConfig:
    def test_benchmark_tickers_contains_spy_and_qqq(self):
        assert "SPY" in BENCHMARK_TICKERS
        assert "QQQ" in BENCHMARK_TICKERS


# ---------------------------------------------------------------------------
# by_regime aggregation
# ---------------------------------------------------------------------------

class TestByRegime:
    def test_by_regime_groups_signals_correctly(self):
        signals = [
            _signal(market_regime="BULL_RISK_ON", forward_return=8.0, spy_return=2.0, qqq_return=3.0),
            _signal(market_regime="BULL_RISK_ON", forward_return=4.0, spy_return=2.0, qqq_return=3.0),
            _signal(market_regime="BEAR_RISK_OFF", forward_return=-3.0, spy_return=0.0, qqq_return=0.0),
        ]
        import pandas as pd
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_regime(df)
        assert "BULL_RISK_ON" in result
        assert "BEAR_RISK_OFF" in result
        assert result["BULL_RISK_ON"]["n_signals"] == 2
        assert result["BEAR_RISK_OFF"]["n_signals"] == 1

    def test_by_regime_win_rate_correct(self):
        import pandas as pd
        signals = [
            _signal(market_regime="BULL_RISK_ON", forward_return=5.0, spy_return=1.0, qqq_return=2.0),
            _signal(market_regime="BULL_RISK_ON", forward_return=-2.0, spy_return=1.0, qqq_return=2.0),
            _signal(market_regime="BULL_RISK_ON", forward_return=3.0, spy_return=1.0, qqq_return=2.0),
            _signal(market_regime="BULL_RISK_ON", forward_return=1.0, spy_return=1.0, qqq_return=2.0),
        ]
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_regime(df)
        # 3 wins out of 4 = 75%
        assert result["BULL_RISK_ON"]["win_rate_pct"] == 75.0

    def test_by_regime_excess_vs_qqq_computed(self):
        import pandas as pd
        signals = [
            _signal(market_regime="BULL_RISK_ON", forward_return=8.0, spy_return=2.0, qqq_return=3.0),
        ]
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_regime(df)
        # excess_return_vs_qqq = 8 - 3 = 5
        assert result["BULL_RISK_ON"]["avg_excess_vs_qqq_pct"] == pytest.approx(5.0, abs=0.1)

    def test_by_regime_returns_empty_dict_when_no_regime_column(self):
        import pandas as pd
        signals = [_signal()]
        df = pd.DataFrame(signals)
        df = df.drop(columns=["market_regime"])
        result = _by_regime(df)
        assert result == {}


# ---------------------------------------------------------------------------
# by_archetype aggregation
# ---------------------------------------------------------------------------

class TestByArchetype:
    def test_by_archetype_groups_correctly(self):
        import pandas as pd
        signals = [
            _signal(archetype="HYPER_GROWTH", forward_return=10.0, spy_return=2.0, qqq_return=3.0),
            _signal(archetype="HYPER_GROWTH", forward_return=6.0, spy_return=2.0, qqq_return=3.0),
            _signal(archetype="MATURE_VALUE", forward_return=2.0, spy_return=2.0, qqq_return=3.0),
        ]
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_archetype(df)
        assert "HYPER_GROWTH" in result
        assert "MATURE_VALUE" in result
        assert result["HYPER_GROWTH"]["n_signals"] == 2
        assert result["MATURE_VALUE"]["n_signals"] == 1

    def test_by_archetype_includes_best_decision(self):
        import pandas as pd
        signals = [
            _signal(archetype="HYPER_GROWTH", decision="BUY_NOW"),
            _signal(archetype="HYPER_GROWTH", decision="BUY_NOW"),
            _signal(archetype="HYPER_GROWTH", decision="BUY_STARTER"),
        ]
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_archetype(df)
        assert result["HYPER_GROWTH"]["best_decision"] == "BUY_NOW"

    def test_by_archetype_avg_score(self):
        import pandas as pd
        signals = [
            _signal(archetype="DEFENSIVE", score=60.0),
            _signal(archetype="DEFENSIVE", score=70.0),
        ]
        df = pd.DataFrame(signals)
        df = df[df["forward_return"].notna()].copy()
        result = _by_archetype(df)
        assert result["DEFENSIVE"]["avg_score"] == pytest.approx(65.0, abs=0.1)

    def test_by_archetype_returns_empty_dict_when_no_archetype_column(self):
        import pandas as pd
        signals = [_signal()]
        df = pd.DataFrame(signals)
        df = df.drop(columns=["archetype"])
        result = _by_archetype(df)
        assert result == {}


# ---------------------------------------------------------------------------
# build_metrics integration
# ---------------------------------------------------------------------------

class TestBuildMetricsIntegration:
    def _make_signals(self) -> list[dict]:
        return [
            _signal(archetype="HYPER_GROWTH", market_regime="BULL_RISK_ON"),
            _signal(archetype="MATURE_VALUE", market_regime="BEAR_RISK_OFF", forward_return=-2.0),
            _signal(decision="AVOID", score=40.0, forward_return=1.0, archetype="MATURE_VALUE", market_regime="BEAR_RISK_OFF"),
        ]

    def test_build_metrics_includes_by_regime(self):
        metrics = build_metrics(self._make_signals(), horizon="short_term")
        assert "by_regime" in metrics

    def test_build_metrics_includes_by_archetype(self):
        metrics = build_metrics(self._make_signals(), horizon="short_term")
        assert "by_archetype" in metrics

    def test_by_regime_in_metrics_has_correct_structure(self):
        metrics = build_metrics(self._make_signals(), horizon="short_term")
        by_regime = metrics["by_regime"]
        assert isinstance(by_regime, dict)
        for regime_key, regime_data in by_regime.items():
            assert "n_signals" in regime_data
            assert "win_rate_pct" in regime_data
            assert "avg_return_pct" in regime_data

    def test_by_archetype_in_metrics_has_correct_structure(self):
        metrics = build_metrics(self._make_signals(), horizon="short_term")
        by_archetype = metrics["by_archetype"]
        assert isinstance(by_archetype, dict)
        for arch_key, arch_data in by_archetype.items():
            assert "n_signals" in arch_data
            assert "win_rate_pct" in arch_data
            assert "avg_return_pct" in arch_data
            assert "best_decision" in arch_data

    def test_excess_return_vs_qqq_in_signal_is_correct(self):
        sig = _signal(forward_return=10.0, qqq_return=3.0)
        assert sig["excess_return_vs_qqq"] == pytest.approx(7.0, abs=0.01)
