"""Tests for US-001: Stock Archetype Classifier."""
import pytest

from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.services.stock_archetype_service import classify_archetype, classify_and_attach


def _fund(**kwargs) -> FundamentalData:
    defaults = dict(
        revenue_growth_yoy=0.12,
        operating_margin=0.10,
        free_cash_flow=1e9,
        eps_ttm=5.0,
        eps_growth_yoy=0.10,
        gross_margin=0.40,
        beta=1.0,
        sector="Technology",
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _val(**kwargs) -> ValuationData:
    defaults = dict(forward_pe=20.0, price_to_sales=4.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


class TestHyperGrowth:
    def test_very_high_revenue_growth(self):
        fd = _fund(revenue_growth_yoy=0.45)
        archetype, conf = classify_archetype(fd, _val())
        assert archetype == StockArchetype.HYPER_GROWTH
        assert conf > 70

    def test_high_growth_high_pe(self):
        """NVDA-like: 25% growth + high forward P/E."""
        fd = _fund(revenue_growth_yoy=0.25)
        vd = _val(forward_pe=50.0)
        archetype, _ = classify_archetype(fd, vd)
        assert archetype == StockArchetype.HYPER_GROWTH

    def test_exactly_30pct_growth_boundary(self):
        fd = _fund(revenue_growth_yoy=0.30)
        archetype, _ = classify_archetype(fd, _val())
        # 30% is NOT > 30%, so should not be HYPER_GROWTH via first branch
        # could be PROFITABLE_GROWTH
        assert archetype in (StockArchetype.HYPER_GROWTH, StockArchetype.PROFITABLE_GROWTH)

    def test_31pct_is_hyper_growth(self):
        fd = _fund(revenue_growth_yoy=0.31)
        archetype, _ = classify_archetype(fd, _val())
        assert archetype == StockArchetype.HYPER_GROWTH


class TestDefensive:
    def test_jnj_like_healthcare_low_beta(self):
        """JNJ-like: Healthcare sector, low beta."""
        fd = _fund(
            sector="Healthcare",
            beta=0.55,
            revenue_growth_yoy=0.05,
        )
        archetype, conf = classify_archetype(fd, _val(forward_pe=16.0, price_to_sales=3.0))
        assert archetype == StockArchetype.DEFENSIVE
        assert conf >= 65

    def test_utilities_sector(self):
        fd = _fund(sector="Utilities", beta=0.4, revenue_growth_yoy=0.03)
        archetype, _ = classify_archetype(fd, _val(forward_pe=18.0))
        assert archetype == StockArchetype.DEFENSIVE

    def test_consumer_defensive(self):
        fd = _fund(sector="Consumer Defensive", beta=0.7, revenue_growth_yoy=0.04)
        archetype, _ = classify_archetype(fd, _val())
        assert archetype == StockArchetype.DEFENSIVE


class TestCommodityCyclical:
    def test_xom_like_energy(self):
        """XOM-like: Energy sector."""
        fd = _fund(sector="Energy", beta=1.1, revenue_growth_yoy=0.08)
        archetype, conf = classify_archetype(fd, _val(forward_pe=12.0))
        assert archetype == StockArchetype.COMMODITY_CYCLICAL
        assert conf > 70

    def test_basic_materials(self):
        fd = _fund(sector="Basic Materials", beta=1.2, revenue_growth_yoy=0.06)
        archetype, _ = classify_archetype(fd, _val())
        assert archetype == StockArchetype.COMMODITY_CYCLICAL


class TestProfitableGrowth:
    def test_msft_like(self):
        """MSFT-like: ~16% growth, high margins, profitable."""
        fd = _fund(
            revenue_growth_yoy=0.16,
            operating_margin=0.45,
            free_cash_flow=5e10,
            eps_ttm=11.0,
            sector="Technology",
            beta=0.9,
        )
        vd = _val(forward_pe=28.0, price_to_sales=12.0)
        archetype, conf = classify_archetype(fd, vd)
        assert archetype == StockArchetype.PROFITABLE_GROWTH
        assert conf >= 60

    def test_requires_positive_economics(self):
        """25% growth with P/S=25 and negative earnings → SPECULATIVE_STORY, not PROFITABLE_GROWTH."""
        fd = _fund(
            revenue_growth_yoy=0.25,
            operating_margin=-0.15,
            free_cash_flow=-2e8,
            eps_ttm=-4.0,
        )
        vd = _val(price_to_sales=25.0)  # P/S > 20 triggers SPECULATIVE_STORY
        archetype, _ = classify_archetype(fd, vd)
        assert archetype == StockArchetype.SPECULATIVE_STORY


class TestMatureValue:
    def test_slow_growth_profitable(self):
        """Non-defensive sector, slow growth, positive FCF → MATURE_VALUE."""
        fd = _fund(
            revenue_growth_yoy=0.04,
            operating_margin=0.15,
            free_cash_flow=2e9,
            eps_ttm=8.0,
            sector="Financials",
            beta=0.9,
        )
        vd = _val(forward_pe=14.0, price_to_sales=2.0)
        archetype, _ = classify_archetype(fd, vd)
        assert archetype == StockArchetype.MATURE_VALUE

    def test_no_revenue_data_defaults_mature_value(self):
        """Missing revenue growth + profitable → MATURE_VALUE."""
        fd = _fund(revenue_growth_yoy=None, free_cash_flow=1e9, eps_ttm=5.0, sector="Financials")
        archetype, _ = classify_archetype(fd, _val(forward_pe=12.0))
        assert archetype == StockArchetype.MATURE_VALUE


class TestTurnaround:
    def test_recovering_eps_slow_revenue(self):
        fd = _fund(
            revenue_growth_yoy=0.06,
            eps_growth_yoy=0.25,
            revenue_growth_qoq=0.08,
            eps_ttm=2.0,
            operating_margin=0.05,
            free_cash_flow=5e8,
            sector="Industrials",
            beta=1.1,
        )
        vd = _val(forward_pe=18.0)
        archetype, conf = classify_archetype(fd, vd)
        assert archetype == StockArchetype.TURNAROUND
        assert conf >= 55


class TestSpeculativeStory:
    def test_high_ps_negative_earnings(self):
        """High P/S + negative earnings + fast revenue growth."""
        fd = _fund(
            revenue_growth_yoy=0.35,
            eps_ttm=-3.0,
            operating_margin=-0.20,
        )
        vd = _val(price_to_sales=25.0)
        archetype, conf = classify_archetype(fd, vd)
        assert archetype == StockArchetype.SPECULATIVE_STORY
        assert conf >= 70

    def test_extremely_high_ps(self):
        fd = _fund(revenue_growth_yoy=0.50, eps_ttm=-1.0)
        vd = _val(price_to_sales=45.0)
        archetype, _ = classify_archetype(fd, vd)
        assert archetype == StockArchetype.SPECULATIVE_STORY


class TestMissingData:
    def test_all_none_defaults_to_profitable_growth(self):
        """When all data is missing, fallback is PROFITABLE_GROWTH."""
        fd = FundamentalData()  # all None
        vd = ValuationData()
        archetype, conf = classify_archetype(fd, vd)
        assert archetype == StockArchetype.PROFITABLE_GROWTH
        assert conf < 60  # low confidence when data missing

    def test_valid_archetype_value(self):
        """Archetype returned is always in the known set."""
        fd = _fund()
        vd = _val()
        archetype, conf = classify_archetype(fd, vd)
        assert archetype in StockArchetype.ALL
        assert 0 <= conf <= 100


class TestClassifyAndAttach:
    def test_attaches_to_fundamental_data(self):
        fd = _fund(revenue_growth_yoy=0.40)
        vd = _val()
        result = classify_and_attach(fd, vd)
        assert result.archetype == StockArchetype.HYPER_GROWTH
        assert result.archetype_confidence > 0
        assert result is fd  # mutates in place
