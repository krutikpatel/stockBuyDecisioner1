"""Tests for backtest.walk_forward (pure unit tests — no live backtest calls)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backtest.walk_forward import WalkForwardValidator, WalkForwardFold, WalkForwardResult


@pytest.fixture
def validator():
    return WalkForwardValidator(
        train_window_weeks=104,
        test_window_weeks=26,
        step_weeks=13,
    )


class TestGenerateFolds:
    def test_generates_multiple_folds_for_long_range(self, validator):
        folds = validator._generate_folds("2019-01-01", "2024-01-01")
        assert len(folds) > 0

    def test_fold_structure(self, validator):
        folds = validator._generate_folds("2019-01-01", "2024-01-01")
        train_start, train_end, test_start, test_end = folds[0]
        assert train_start == "2019-01-01"
        assert train_end > train_start
        assert test_start > train_end
        assert test_end > test_start

    def test_train_window_approximately_correct(self, validator):
        folds = validator._generate_folds("2019-01-01", "2024-01-01")
        import pandas as pd
        train_start, train_end, _, _ = folds[0]
        delta = (pd.Timestamp(train_end) - pd.Timestamp(train_start)).days
        expected = validator.train_window_weeks * 7
        assert abs(delta - expected) <= 1

    def test_returns_empty_for_too_short_range(self, validator):
        # A 3-month range can't fit a 2-year train + 6-month test
        folds = validator._generate_folds("2023-01-01", "2023-04-01")
        assert folds == []

    def test_folds_advance_by_step(self, validator):
        folds = validator._generate_folds("2019-01-01", "2024-01-01")
        import pandas as pd
        if len(folds) >= 2:
            s0 = pd.Timestamp(folds[0][0])
            s1 = pd.Timestamp(folds[1][0])
            delta_days = (s1 - s0).days
            expected   = validator.step_weeks * 7
            assert abs(delta_days - expected) <= 1


class TestComputeConsistency:
    def _make_fold(self, is_ret, oos_ret, idx=0) -> WalkForwardFold:
        return WalkForwardFold(
            fold_index=idx,
            train_start="2019-01-01", train_end="2021-01-01",
            test_start="2021-01-02",  test_end="2021-07-01",
            is_avg_return=is_ret,
            oos_avg_return=oos_ret,
        )

    def test_perfect_consistency(self):
        folds = [
            self._make_fold(5.0, 4.0, 0),
            self._make_fold(3.0, 2.5, 1),
        ]
        score = WalkForwardValidator._compute_consistency(folds)
        assert score == 1.0

    def test_zero_consistency_when_oos_much_worse(self):
        folds = [
            self._make_fold(5.0, 0.5, 0),   # OOS < 50% of IS
            self._make_fold(4.0, 1.0, 1),   # OOS == 25% of IS
        ]
        score = WalkForwardValidator._compute_consistency(folds)
        assert score == 0.0

    def test_empty_folds_returns_zero(self):
        score = WalkForwardValidator._compute_consistency([])
        assert score == 0.0

    def test_folds_with_none_returns_ignored(self):
        folds = [
            WalkForwardFold(
                fold_index=0,
                train_start="2019-01-01", train_end="2021-01-01",
                test_start="2021-01-02",  test_end="2021-07-01",
                is_avg_return=None, oos_avg_return=None,
            )
        ]
        score = WalkForwardValidator._compute_consistency(folds)
        assert score == 0.0

    def test_both_negative_counts_oos_not_worse(self):
        folds = [self._make_fold(-2.0, -1.5, 0)]   # OOS less negative → consistent
        score = WalkForwardValidator._compute_consistency(folds)
        assert score == 1.0


class TestSummarize:
    def _fold(self, is_wr, oos_wr, is_ret, oos_ret, idx=0) -> WalkForwardFold:
        return WalkForwardFold(
            fold_index=idx,
            train_start="2019-01-01", train_end="2021-01-01",
            test_start="2021-01-02",  test_end="2021-07-01",
            is_win_rate=is_wr,      oos_win_rate=oos_wr,
            is_avg_return=is_ret,   oos_avg_return=oos_ret,
        )

    def test_averages_computed(self):
        folds = [
            self._fold(60.0, 55.0, 3.0, 2.5, 0),
            self._fold(65.0, 60.0, 4.0, 3.0, 1),
        ]
        summary = WalkForwardValidator._summarize(folds)
        assert summary["n_folds"] == 2
        assert summary["avg_oos_win_rate_pct"] == pytest.approx(57.5, abs=0.1)
        assert summary["avg_oos_avg_return_pct"] == pytest.approx(2.75, abs=0.01)

    def test_empty_folds_returns_empty(self):
        summary = WalkForwardValidator._summarize([])
        assert summary == {}
