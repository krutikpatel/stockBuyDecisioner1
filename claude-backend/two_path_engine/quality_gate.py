"""Quality gate: multi-factor AND-logic filter that splits stocks into
quality_intact vs deteriorating_business paths."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.algo_config import AlgoConfig, get_algo_config
from app.features.feature_snapshot import FeatureSnapshot


@dataclass
class QualityGateResult:
    passes: bool
    reasons: list[str] = field(default_factory=list)


class QualityGate:
    """AND-logic quality filter.

    All conditions must pass for a stock to enter the buy-side path.
    Any single failure routes the stock to the avoid-side path.
    """

    def __init__(self, algo_config: AlgoConfig | None = None) -> None:
        self._cfg = algo_config or get_algo_config()

    def evaluate(self, snapshot: FeatureSnapshot) -> QualityGateResult:
        qg = self._cfg.quality_gate
        gross_margin_min: float = qg.get("gross_margin_min", 0.30)
        op_margin_min: float = qg.get("op_margin_min", -0.05)
        roe_min: float = qg.get("roe_min", 5.0)
        fcf_substitutes_roe: bool = qg.get("fcf_substitutes_roe", True)
        debt_equity_max: float = qg.get("debt_equity_max", 2.0)
        current_ratio_min: float = qg.get("current_ratio_min", 1.0)

        failures: list[str] = []

        # 1. Gross margin
        if snapshot.gross_margin is None:
            failures.append("gross_margin missing — cannot confirm margin quality")
        elif snapshot.gross_margin < gross_margin_min:
            failures.append(
                f"gross_margin {snapshot.gross_margin:.1%} < min {gross_margin_min:.1%}"
            )

        # 2. Operating margin
        if snapshot.operating_margin is None:
            failures.append("operating_margin missing — cannot confirm operational viability")
        elif snapshot.operating_margin < op_margin_min:
            failures.append(
                f"operating_margin {snapshot.operating_margin:.1%} < min {op_margin_min:.1%}"
            )

        # 3. ROE (or FCF as substitute)
        roe_ok = snapshot.roe is not None and snapshot.roe >= roe_min
        fcf_ok = fcf_substitutes_roe and snapshot.free_cash_flow is not None and snapshot.free_cash_flow > 0
        if not roe_ok and not fcf_ok:
            roe_str = f"{snapshot.roe:.1f}" if snapshot.roe is not None else "None"
            fcf_str = f"{snapshot.free_cash_flow:,.0f}" if snapshot.free_cash_flow is not None else "None"
            failures.append(
                f"ROE {roe_str} < {roe_min} and FCF {fcf_str} not positive — "
                "neither profitability condition met"
            )

        # 4. Debt/equity
        if snapshot.debt_to_equity is not None and snapshot.debt_to_equity > debt_equity_max:
            failures.append(
                f"debt_to_equity {snapshot.debt_to_equity:.2f} > max {debt_equity_max:.2f}"
            )

        # 5. Current ratio
        if snapshot.current_ratio is not None and snapshot.current_ratio < current_ratio_min:
            failures.append(
                f"current_ratio {snapshot.current_ratio:.2f} < min {current_ratio_min:.2f}"
            )

        if failures:
            return QualityGateResult(passes=False, reasons=failures)
        return QualityGateResult(
            passes=True,
            reasons=["All quality gate conditions met"],
        )
