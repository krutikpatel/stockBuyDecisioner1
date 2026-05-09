"""Tests for Step 5: scoring_service config migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.models.market import MarketRegime, MarketRegimeAssessment
from app.models.response import SignalCard, SignalCardLabel, SignalCards
from app.services.scoring_service import (
    SIGNAL_CARD_LONG_WEIGHTS,
    SIGNAL_CARD_MEDIUM_WEIGHTS,
    SIGNAL_CARD_SHORT_WEIGHTS,
    SHORT_TERM_WEIGHTS,
    MEDIUM_TERM_WEIGHTS,
    LONG_TERM_WEIGHTS,
    compute_scores_from_signal_cards,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _card(score: float = 60.0) -> SignalCard:
    return SignalCard(name="test", score=score, label=SignalCardLabel.NEUTRAL, explanation="", top_positives=[], top_negatives=[], missing_data_warnings=[])


def _cards(score: float = 60.0) -> SignalCards:
    c = _card(score)
    return SignalCards(
        momentum=c, trend=c, entry_timing=c, volume_accumulation=c,
        volatility_risk=c, relative_strength=c, growth=c, valuation=c,
        quality=c, ownership=c, catalyst=c,
    )


def _bull_regime(conf: float = 80.0) -> MarketRegimeAssessment:
    return MarketRegimeAssessment(regime=MarketRegime.BULL_RISK_ON, confidence=conf, implication="")


def _bear_regime(conf: float = 80.0) -> MarketRegimeAssessment:
    return MarketRegimeAssessment(regime=MarketRegime.BEAR_RISK_OFF, confidence=conf, implication="")


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Module-level aliases match default config
# ---------------------------------------------------------------------------

def test_signal_card_short_momentum_default():
    assert SIGNAL_CARD_SHORT_WEIGHTS["momentum"] == 25


def test_signal_card_medium_trend_default():
    assert SIGNAL_CARD_MEDIUM_WEIGHTS["trend"] == 20


def test_signal_card_long_quality_default():
    assert SIGNAL_CARD_LONG_WEIGHTS["quality"] == 35


def test_legacy_short_technical_default():
    assert SHORT_TERM_WEIGHTS["technical_momentum"] == 30


def test_legacy_medium_earnings_default():
    assert MEDIUM_TERM_WEIGHTS["earnings_revision"] == 25


def test_legacy_long_quality_default():
    assert LONG_TERM_WEIGHTS["business_quality"] == 25


# ---------------------------------------------------------------------------
# Weight sum validation still enforced
# ---------------------------------------------------------------------------

def test_invalid_weights_raise_assertion():
    data = _base_cfg()
    data["scoring"]["signal_card_short_weights"]["momentum"] = 99  # breaks sum
    cfg = AlgoConfig.from_dict(data)
    with pytest.raises(AssertionError):
        from app.services.scoring_service import _verify_weights
        _verify_weights(data["scoring"])


# ---------------------------------------------------------------------------
# compute_scores_from_signal_cards — default config
# ---------------------------------------------------------------------------

def test_uniform_cards_produce_uniform_composite():
    """All cards at 60 → all composites at 60."""
    result = compute_scores_from_signal_cards(_cards(60.0))
    assert result["short_term"]["composite"] == pytest.approx(60.0, abs=0.1)
    assert result["medium_term"]["composite"] == pytest.approx(60.0, abs=0.1)
    assert result["long_term"]["composite"] == pytest.approx(60.0, abs=0.1)


def test_bull_regime_boosts_short_composite():
    """BULL_RISK_ON should increase short composite above base."""
    base = compute_scores_from_signal_cards(_cards(60.0))
    boosted = compute_scores_from_signal_cards(_cards(60.0), regime_assessment=_bull_regime(80.0))
    assert boosted["short_term"]["composite"] > base["short_term"]["composite"]


def test_bear_regime_reduces_short_composite():
    """BEAR_RISK_OFF should decrease short composite below base."""
    base = compute_scores_from_signal_cards(_cards(60.0))
    reduced = compute_scores_from_signal_cards(_cards(60.0), regime_assessment=_bear_regime(80.0))
    assert reduced["short_term"]["composite"] < base["short_term"]["composite"]


# ---------------------------------------------------------------------------
# Custom config changes composites
# ---------------------------------------------------------------------------

def test_custom_short_weights_change_composite():
    """Change short weights: momentum=10, entry_timing=35 (still sums to 100)."""
    data = _base_cfg()
    data["scoring"]["signal_card_short_weights"]["momentum"] = 10
    data["scoring"]["signal_card_short_weights"]["entry_timing"] = 35
    cfg = AlgoConfig.from_dict(data)

    # With non-uniform cards: momentum=80, rest=50
    cards = _cards(50.0)
    cards.momentum = _card(80.0)

    default_result = compute_scores_from_signal_cards(cards)
    custom_result = compute_scores_from_signal_cards(cards, algo_config=cfg)

    # With less weight on momentum (10 vs 25), the custom composite should be lower
    assert custom_result["short_term"]["composite"] < default_result["short_term"]["composite"]


def test_custom_regime_bull_coef():
    """Custom bull_short_composite_coef=0.20 → bigger boost than default 0.10."""
    data = _base_cfg()
    data["regime_scoring"]["bull_short_composite_coef"] = 0.20
    cfg = AlgoConfig.from_dict(data)

    default_result = compute_scores_from_signal_cards(_cards(60.0), regime_assessment=_bull_regime(80.0))
    custom_result = compute_scores_from_signal_cards(_cards(60.0), regime_assessment=_bull_regime(80.0), algo_config=cfg)

    assert custom_result["short_term"]["composite"] > default_result["short_term"]["composite"]
