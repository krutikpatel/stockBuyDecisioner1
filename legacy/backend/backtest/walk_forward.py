"""
Walk-forward validation for the backtest framework.

Generates rolling train/test folds and runs the production backtest loop
for each fold, producing in-sample (IS) vs out-of-sample (OOS) metrics
to surface overfitting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.algo_config import AlgoConfig
from backtest.config import BACKTEST_START, BACKTEST_END, DEFAULT_RISK_PROFILE, DEFAULT_PHASE
from backtest.outcome import attach_outcomes
from backtest.metrics import build_metrics

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    is_metrics: dict = field(default_factory=dict)
    oos_metrics: dict = field(default_factory=dict)
    is_win_rate: Optional[float] = None
    oos_win_rate: Optional[float] = None
    is_avg_return: Optional[float] = None
    oos_avg_return: Optional[float] = None


@dataclass
class WalkForwardResult:
    folds: list[WalkForwardFold]
    summary: dict
    oos_vs_is_consistency: float   # 0–1; higher means less overfitting


class WalkForwardValidator:
    """Runs rolling walk-forward validation folds.

    Each fold:
      - IS (train) window:  run_backtest over [train_start, train_end]
      - OOS (test) window:  run_backtest over [test_start, test_end]

    Folds advance by step_weeks at a time.
    """

    def __init__(
        self,
        train_window_weeks: int = 104,
        test_window_weeks: int  = 26,
        step_weeks: int         = 13,
        phase: int              = DEFAULT_PHASE,
        risk_profile: str       = DEFAULT_RISK_PROFILE,
        algo_config: Optional[AlgoConfig] = None,
    ) -> None:
        self.train_window_weeks = train_window_weeks
        self.test_window_weeks  = test_window_weeks
        self.step_weeks         = step_weeks
        self.phase              = phase
        self.risk_profile       = risk_profile
        self.algo_config        = algo_config

    # ------------------------------------------------------------------ public

    def run(
        self,
        data: dict,
        tickers: Optional[list[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        horizon: str = "short_term",
    ) -> WalkForwardResult:
        """Run all folds and return aggregated results.

        Args:
            data:    Output of data_loader.load_all_data().
            tickers: Ticker subset (default: BACKTEST_TICKERS).
            start:   Overall window start (default: BACKTEST_START).
            end:     Overall window end (default: BACKTEST_END).
            horizon: Which horizon to use for OOS/IS metric reporting.
        """
        # Import here to avoid circular imports at module level
        from backtest.runner import run_backtest

        folds_def = self._generate_folds(start or BACKTEST_START, end or BACKTEST_END)
        if not folds_def:
            logger.warning(
                "No walk-forward folds generated for %s → %s", start, end
            )
            return WalkForwardResult(folds=[], summary={}, oos_vs_is_consistency=0.0)

        logger.info(
            "Running %d walk-forward folds (horizon=%s, train=%dwk, test=%dwk, step=%dwk)",
            len(folds_def), horizon,
            self.train_window_weeks, self.test_window_weeks, self.step_weeks,
        )
        folds: list[WalkForwardFold] = []

        for idx, (train_start, train_end, test_start, test_end) in enumerate(folds_def):
            logger.info(
                "Fold %d/%d — IS: %s→%s  OOS: %s→%s",
                idx + 1, len(folds_def),
                train_start, train_end, test_start, test_end,
            )

            is_signals = run_backtest(
                data=data, tickers=tickers,
                start=train_start, end=train_end,
                risk_profile=self.risk_profile, phase=self.phase,
                algo_config=self.algo_config,
            )
            is_signals = attach_outcomes(is_signals, data["prices"])
            is_m = build_metrics(is_signals, horizon)

            oos_signals = run_backtest(
                data=data, tickers=tickers,
                start=test_start, end=test_end,
                risk_profile=self.risk_profile, phase=self.phase,
                algo_config=self.algo_config,
            )
            oos_signals = attach_outcomes(oos_signals, data["prices"])
            oos_m = build_metrics(oos_signals, horizon)

            is_overall  = is_m.get("overall_stats", {})
            oos_overall = oos_m.get("overall_stats", {})

            folds.append(WalkForwardFold(
                fold_index=idx,
                train_start=train_start, train_end=train_end,
                test_start=test_start,   test_end=test_end,
                is_metrics=is_m,         oos_metrics=oos_m,
                is_win_rate=is_overall.get("overall_win_rate_pct"),
                oos_win_rate=oos_overall.get("overall_win_rate_pct"),
                is_avg_return=is_overall.get("avg_return_pct"),
                oos_avg_return=oos_overall.get("avg_return_pct"),
            ))

        summary     = self._summarize(folds)
        consistency = self._compute_consistency(folds)
        return WalkForwardResult(
            folds=folds, summary=summary, oos_vs_is_consistency=consistency
        )

    # ----------------------------------------------------------------- private

    def _generate_folds(
        self, start: str, end: str
    ) -> list[tuple[str, str, str, str]]:
        """Yield (train_start, train_end, test_start, test_end) tuples."""
        folds: list[tuple[str, str, str, str]] = []
        train_td = pd.Timedelta(weeks=self.train_window_weeks)
        test_td  = pd.Timedelta(weeks=self.test_window_weeks)
        step_td  = pd.Timedelta(weeks=self.step_weeks)

        overall_end = pd.Timestamp(end)
        cursor      = pd.Timestamp(start)

        while True:
            train_start = cursor
            train_end   = cursor + train_td
            test_start  = train_end + pd.Timedelta(days=1)
            test_end    = test_start + test_td

            if test_end > overall_end:
                break

            folds.append((
                train_start.strftime("%Y-%m-%d"),
                train_end.strftime("%Y-%m-%d"),
                test_start.strftime("%Y-%m-%d"),
                test_end.strftime("%Y-%m-%d"),
            ))
            cursor += step_td

        return folds

    @staticmethod
    def _summarize(folds: list[WalkForwardFold]) -> dict:
        if not folds:
            return {}
        oos_wrs  = [f.oos_win_rate  for f in folds if f.oos_win_rate  is not None]
        is_wrs   = [f.is_win_rate   for f in folds if f.is_win_rate   is not None]
        oos_rets = [f.oos_avg_return for f in folds if f.oos_avg_return is not None]
        is_rets  = [f.is_avg_return  for f in folds if f.is_avg_return  is not None]
        return {
            "n_folds":               len(folds),
            "avg_oos_win_rate_pct":  round(sum(oos_wrs)  / len(oos_wrs),  1) if oos_wrs  else None,
            "avg_is_win_rate_pct":   round(sum(is_wrs)   / len(is_wrs),   1) if is_wrs   else None,
            "avg_oos_avg_return_pct": round(sum(oos_rets) / len(oos_rets), 2) if oos_rets else None,
            "avg_is_avg_return_pct": round(sum(is_rets)  / len(is_rets),  2) if is_rets  else None,
            "oos_win_rates":         oos_wrs,
            "oos_avg_returns":       oos_rets,
        }

    @staticmethod
    def _compute_consistency(folds: list[WalkForwardFold]) -> float:
        """Fraction of folds where OOS return >= 50% of IS return.

        A score near 1.0 means OOS closely tracks IS (low overfitting risk).
        """
        if not folds:
            return 0.0
        consistent = 0
        comparable = 0
        for f in folds:
            if f.is_avg_return is None or f.oos_avg_return is None:
                continue
            comparable += 1
            if f.is_avg_return > 0:
                consistent += int(f.oos_avg_return >= f.is_avg_return * 0.5)
            else:
                consistent += int(f.oos_avg_return >= f.is_avg_return)
        return round(consistent / comparable, 3) if comparable > 0 else 0.0
