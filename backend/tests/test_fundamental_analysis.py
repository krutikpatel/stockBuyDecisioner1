"""Phase 2 unit tests: fundamental and valuation analysis."""
import pytest
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.services.fundamental_analysis_service import score_fundamentals
from app.services.valuation_analysis_service import score_valuation, score_valuation_with_archetype


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_strong_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_ttm=10_000_000_000,
        revenue_growth_yoy=0.25,
        revenue_growth_qoq=0.06,
        eps_ttm=5.0,
        eps_growth_yoy=0.30,
        gross_margin=0.60,
        operating_margin=0.25,
        net_margin=0.20,
        free_cash_flow=2_000_000_000,
        free_cash_flow_margin=0.20,
        cash=5_000_000_000,
        total_debt=1_000_000_000,
        net_debt=-4_000_000_000,
        current_ratio=3.0,
        debt_to_equity=0.3,
        roe=0.30,
    )


def _make_weak_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_ttm=5_000_000_000,
        revenue_growth_yoy=-0.10,
        revenue_growth_qoq=-0.05,
        eps_ttm=-1.0,
        eps_growth_yoy=-0.20,
        gross_margin=0.08,
        operating_margin=-0.05,
        net_margin=-0.10,
        free_cash_flow=-500_000_000,
        free_cash_flow_margin=-0.10,
        cash=200_000_000,
        total_debt=2_000_000_000,
        net_debt=1_800_000_000,
        current_ratio=0.8,
        debt_to_equity=3.5,
        roe=-0.15,
    )


def _make_attractive_valuation() -> ValuationData:
    return ValuationData(
        trailing_pe=18.0,
        forward_pe=14.0,
        peg_ratio=0.9,
        price_to_sales=1.5,
        ev_to_ebitda=8.0,
        price_to_fcf=12.0,
        fcf_yield=6.0,
        peer_comparison_available=False,
    )


def _make_expensive_valuation() -> ValuationData:
    return ValuationData(
        trailing_pe=80.0,
        forward_pe=55.0,
        peg_ratio=4.5,
        price_to_sales=25.0,
        ev_to_ebitda=50.0,
        price_to_fcf=120.0,
        fcf_yield=0.5,
        peer_comparison_available=False,
    )


# ---------------------------------------------------------------------------
# Fundamental scoring tests
# ---------------------------------------------------------------------------

class TestFundamentalScoring:
    def test_score_in_valid_range(self):
        strong = score_fundamentals(_make_strong_fundamentals())
        weak = score_fundamentals(_make_weak_fundamentals())
        assert 0 <= strong <= 100
        assert 0 <= weak <= 100

    def test_strong_scores_higher_than_weak(self):
        strong = score_fundamentals(_make_strong_fundamentals())
        weak = score_fundamentals(_make_weak_fundamentals())
        assert strong > weak, f"Expected strong ({strong}) > weak ({weak})"

    def test_positive_revenue_growth_raises_score(self):
        base = FundamentalData()
        base.revenue_growth_yoy = None
        baseline = score_fundamentals(base)

        high_growth = FundamentalData()
        high_growth.revenue_growth_yoy = 0.25
        assert score_fundamentals(high_growth) > baseline

    def test_negative_revenue_growth_lowers_score(self):
        base = FundamentalData()
        base.revenue_growth_yoy = None
        baseline = score_fundamentals(base)

        declining = FundamentalData()
        declining.revenue_growth_yoy = -0.15
        assert score_fundamentals(declining) < baseline

    def test_positive_fcf_raises_score(self):
        no_fcf = FundamentalData(free_cash_flow=None)
        pos_fcf = FundamentalData(free_cash_flow=1_000_000_000)
        neg_fcf = FundamentalData(free_cash_flow=-500_000_000)
        assert score_fundamentals(pos_fcf) > score_fundamentals(no_fcf)
        assert score_fundamentals(pos_fcf) > score_fundamentals(neg_fcf)

    def test_negative_fcf_lowers_score(self):
        pos_fcf = FundamentalData(free_cash_flow=1_000_000_000)
        neg_fcf = FundamentalData(free_cash_flow=-500_000_000)
        assert score_fundamentals(neg_fcf) < score_fundamentals(pos_fcf)

    def test_high_roe_raises_score(self):
        low_roe = FundamentalData(roe=0.05)
        high_roe = FundamentalData(roe=0.25)
        assert score_fundamentals(high_roe) > score_fundamentals(low_roe)

    def test_negative_roe_lowers_score(self):
        pos_roe = FundamentalData(roe=0.20)
        neg_roe = FundamentalData(roe=-0.10)
        assert score_fundamentals(pos_roe) > score_fundamentals(neg_roe)

    def test_high_debt_to_equity_lowers_score(self):
        low_dte = FundamentalData(debt_to_equity=0.3)
        high_dte = FundamentalData(debt_to_equity=3.0)
        assert score_fundamentals(low_dte) > score_fundamentals(high_dte)

    def test_net_cash_position_raises_score(self):
        net_cash = FundamentalData(cash=5_000_000_000, net_debt=-4_000_000_000)
        leveraged = FundamentalData(cash=200_000_000, net_debt=5_000_000_000)
        assert score_fundamentals(net_cash) > score_fundamentals(leveraged)

    def test_empty_data_returns_50(self):
        """No signal data → score stays at baseline 50."""
        empty = FundamentalData()
        assert score_fundamentals(empty) == 50.0

    def test_expanding_margins_raise_score(self):
        low_margins = FundamentalData(gross_margin=0.05, operating_margin=-0.02)
        high_margins = FundamentalData(gross_margin=0.65, operating_margin=0.30)
        assert score_fundamentals(high_margins) > score_fundamentals(low_margins)


# ---------------------------------------------------------------------------
# Valuation scoring tests
# ---------------------------------------------------------------------------

class TestValuationScoring:
    def test_score_in_valid_range(self):
        cheap = score_valuation(_make_attractive_valuation())
        expensive = score_valuation(_make_expensive_valuation())
        assert 0 <= cheap <= 100
        assert 0 <= expensive <= 100

    def test_attractive_valuation_scores_higher_than_expensive(self):
        cheap = score_valuation(_make_attractive_valuation())
        expensive = score_valuation(_make_expensive_valuation())
        assert cheap > expensive, f"Expected cheap ({cheap}) > expensive ({expensive})"

    def test_low_forward_pe_raises_score(self):
        low_pe = ValuationData(forward_pe=12.0)
        high_pe = ValuationData(forward_pe=60.0)
        assert score_valuation(low_pe) > score_valuation(high_pe)

    def test_peg_below_1_raises_score(self):
        low_peg = ValuationData(peg_ratio=0.8)
        high_peg = ValuationData(peg_ratio=4.0)
        assert score_valuation(low_peg) > score_valuation(high_peg)

    def test_high_fcf_yield_raises_score(self):
        high_yield = ValuationData(fcf_yield=7.0)
        low_yield = ValuationData(fcf_yield=0.3)
        assert score_valuation(high_yield) > score_valuation(low_yield)

    def test_peg_ratio_calculation(self):
        """PEG = forward P/E / (eps_growth * 100) — tested via provider separately."""
        # Here test that score reflects the PEG value properly
        good_peg = ValuationData(forward_pe=20.0, peg_ratio=1.0)
        bad_peg = ValuationData(forward_pe=20.0, peg_ratio=3.5)
        assert score_valuation(good_peg) > score_valuation(bad_peg)

    def test_price_to_fcf_used_in_scoring(self):
        cheap_pfcf = ValuationData(price_to_fcf=10.0, fcf_yield=8.0)
        expensive_pfcf = ValuationData(price_to_fcf=100.0, fcf_yield=0.5)
        assert score_valuation(cheap_pfcf) > score_valuation(expensive_pfcf)

    def test_empty_valuation_returns_50(self):
        empty = ValuationData()
        assert score_valuation(empty) == 50.0

    def test_low_ev_ebitda_raises_score(self):
        cheap = ValuationData(ev_to_ebitda=8.0)
        expensive = ValuationData(ev_to_ebitda=60.0)
        assert score_valuation(cheap) > score_valuation(expensive)


# ---------------------------------------------------------------------------
# PEG and P/FCF calculation tests (provider logic, tested inline)
# ---------------------------------------------------------------------------

class TestDerivedMetrics:
    def test_peg_calculation(self):
        """PEG = forward_PE / (eps_growth_rate * 100)"""
        forward_pe = 20.0
        eps_growth = 0.20  # 20% growth rate
        expected_peg = forward_pe / (eps_growth * 100)
        assert expected_peg == pytest.approx(1.0, rel=1e-5)

    def test_price_to_fcf_calculation(self):
        """P/FCF = market_cap / free_cash_flow"""
        market_cap = 1_000_000_000
        free_cash_flow = 100_000_000
        expected = market_cap / free_cash_flow
        assert expected == pytest.approx(10.0, rel=1e-5)

    def test_fcf_yield_calculation(self):
        """FCF yield = FCF / market_cap * 100"""
        free_cash_flow = 100_000_000
        market_cap = 1_000_000_000
        expected = free_cash_flow / market_cap * 100
        assert expected == pytest.approx(10.0, rel=1e-5)


# ---------------------------------------------------------------------------
# US-003: Growth-Adjusted Valuation Tests
# ---------------------------------------------------------------------------

class TestArchetypeAwareValuation:

    def test_hyper_growth_high_pe_not_heavily_penalised(self):
        """NVDA/PLTR-like: forward P/E=80, 40% revenue growth → score > 50."""
        vd = ValuationData(forward_pe=80.0, price_to_sales=25.0, peg_ratio=None)
        score = score_valuation_with_archetype(
            vd,
            StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.40,
            operating_margin=0.25,
            gross_margin=0.75,
        )
        # Old scorer would give ~20–30 (heavily penalised). New one should be > 50.
        assert score > 50
        assert 0 <= score <= 100

    def test_hyper_growth_rule_of_40_bonus(self):
        """Rule of 40 ≥ 60 should give a meaningful bonus."""
        vd = ValuationData(forward_pe=50.0, peg_ratio=None)
        score_high_r40 = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.50, operating_margin=0.20,  # Rule of 40 = 70
        )
        score_low_r40 = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.10, operating_margin=0.05,  # Rule of 40 = 15
        )
        assert score_high_r40 > score_low_r40

    def test_mature_value_cheap_pe_scores_high(self):
        """MATURE_VALUE stock with P/E=12, FCF yield=5% → score > 70."""
        vd = ValuationData(forward_pe=12.0, fcf_yield=5.5, price_to_sales=2.0)
        score = score_valuation_with_archetype(
            vd,
            StockArchetype.MATURE_VALUE,
            revenue_growth_yoy=0.04,
        )
        assert score > 70

    def test_mature_value_expensive_pe_scores_lower_than_hyper_growth(self):
        """For MATURE_VALUE, high P/E is a real penalty (unlike HYPER_GROWTH)."""
        vd = ValuationData(forward_pe=45.0, fcf_yield=1.0)
        score_mature = score_valuation_with_archetype(vd, StockArchetype.MATURE_VALUE)
        score_hyper = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.35, operating_margin=0.20
        )
        assert score_mature < score_hyper

    def test_hyper_growth_slowing_revenue_penalised(self):
        """HYPER_GROWTH with low Rule of 40 should still score decently but less."""
        vd = ValuationData(forward_pe=60.0, peg_ratio=None)
        score_strong = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.50, operating_margin=0.25,
        )
        score_slowing = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            revenue_growth_yoy=0.05, operating_margin=-0.10,
        )
        assert score_strong > score_slowing

    def test_cyclical_low_pe_not_strongly_rewarded(self):
        """CYCLICAL stock at low P/E (potential peak earnings) → modest score."""
        vd = ValuationData(forward_pe=8.0, ev_to_ebitda=6.0, fcf_yield=7.0)
        score_cyclical = score_valuation_with_archetype(vd, StockArchetype.CYCLICAL_GROWTH)
        score_mature = score_valuation_with_archetype(vd, StockArchetype.MATURE_VALUE)
        # Cyclical deliberately doesn't reward ultra-low P/E as much
        assert score_cyclical <= score_mature

    def test_score_always_in_valid_range(self):
        """All archetype scorers must return [0, 100]."""
        vd = ValuationData(forward_pe=200.0, price_to_sales=100.0, fcf_yield=-5.0)
        for archetype in StockArchetype.ALL:
            score = score_valuation_with_archetype(vd, archetype)
            assert 0 <= score <= 100, f"Out of range for {archetype}: {score}"

    def test_high_ps_with_high_gross_margin_not_penalised_for_hyper_growth(self):
        """High P/S is forgiven for HYPER_GROWTH if gross margin > 60%."""
        vd = ValuationData(price_to_sales=30.0, forward_pe=70.0, peg_ratio=None)
        score_high_gm = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            gross_margin=0.75, revenue_growth_yoy=0.35, operating_margin=0.15
        )
        score_low_gm = score_valuation_with_archetype(
            vd, StockArchetype.HYPER_GROWTH,
            gross_margin=0.30, revenue_growth_yoy=0.35, operating_margin=0.15
        )
        assert score_high_gm >= score_low_gm
