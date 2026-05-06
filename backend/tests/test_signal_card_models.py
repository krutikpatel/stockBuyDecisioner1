"""
Story 5 TDD tests: SignalCard Pydantic models
Tests written BEFORE implementation.

Models covered:
- SignalCardLabel (enum-like str constants)
- SignalCard (score, label, explanation, factors, warnings)
- SignalCards (11-card container)
- StockAnalysisResult.signal_cards field
- HorizonRecommendation.signal_cards_weights field
- Label threshold mapping: score -> SignalCardLabel
"""
from __future__ import annotations

import pytest

from app.models.response import (
    SignalCard,
    SignalCardLabel,
    SignalCards,
    StockAnalysisResult,
    HorizonRecommendation,
)


# ---------------------------------------------------------------------------
# SignalCardLabel constants
# ---------------------------------------------------------------------------

class TestSignalCardLabel:
    def test_has_very_bullish(self):
        assert hasattr(SignalCardLabel, "VERY_BULLISH")
        assert SignalCardLabel.VERY_BULLISH == "VERY_BULLISH"

    def test_has_bullish(self):
        assert hasattr(SignalCardLabel, "BULLISH")
        assert SignalCardLabel.BULLISH == "BULLISH"

    def test_has_neutral(self):
        assert hasattr(SignalCardLabel, "NEUTRAL")
        assert SignalCardLabel.NEUTRAL == "NEUTRAL"

    def test_has_bearish(self):
        assert hasattr(SignalCardLabel, "BEARISH")
        assert SignalCardLabel.BEARISH == "BEARISH"

    def test_has_very_bearish(self):
        assert hasattr(SignalCardLabel, "VERY_BEARISH")
        assert SignalCardLabel.VERY_BEARISH == "VERY_BEARISH"

    def test_all_five_values(self):
        labels = [
            SignalCardLabel.VERY_BEARISH,
            SignalCardLabel.BEARISH,
            SignalCardLabel.NEUTRAL,
            SignalCardLabel.BULLISH,
            SignalCardLabel.VERY_BULLISH,
        ]
        assert len(labels) == 5
        assert len(set(labels)) == 5  # all unique


# ---------------------------------------------------------------------------
# SignalCardLabel.from_score() threshold mapping
# ---------------------------------------------------------------------------

class TestSignalCardLabelFromScore:
    def test_very_bullish_at_80(self):
        assert SignalCardLabel.from_score(80.0) == SignalCardLabel.VERY_BULLISH

    def test_very_bullish_at_100(self):
        assert SignalCardLabel.from_score(100.0) == SignalCardLabel.VERY_BULLISH

    def test_bullish_at_65(self):
        assert SignalCardLabel.from_score(65.0) == SignalCardLabel.BULLISH

    def test_neutral_at_40(self):
        assert SignalCardLabel.from_score(40.0) == SignalCardLabel.NEUTRAL

    def test_neutral_at_50(self):
        assert SignalCardLabel.from_score(50.0) == SignalCardLabel.NEUTRAL

    def test_bearish_at_30(self):
        assert SignalCardLabel.from_score(30.0) == SignalCardLabel.BEARISH

    def test_very_bearish_at_10(self):
        assert SignalCardLabel.from_score(10.0) == SignalCardLabel.VERY_BEARISH

    def test_very_bearish_at_0(self):
        assert SignalCardLabel.from_score(0.0) == SignalCardLabel.VERY_BEARISH

    def test_boundary_80_is_very_bullish(self):
        assert SignalCardLabel.from_score(80.0) == SignalCardLabel.VERY_BULLISH

    def test_boundary_just_below_80_is_bullish(self):
        assert SignalCardLabel.from_score(79.9) == SignalCardLabel.BULLISH

    def test_boundary_60_is_bullish(self):
        assert SignalCardLabel.from_score(60.0) == SignalCardLabel.BULLISH

    def test_boundary_just_below_60_is_neutral(self):
        assert SignalCardLabel.from_score(59.9) == SignalCardLabel.NEUTRAL

    def test_boundary_40_is_neutral(self):
        assert SignalCardLabel.from_score(40.0) == SignalCardLabel.NEUTRAL

    def test_boundary_just_below_40_is_bearish(self):
        assert SignalCardLabel.from_score(39.9) == SignalCardLabel.BEARISH

    def test_boundary_20_is_bearish(self):
        assert SignalCardLabel.from_score(20.0) == SignalCardLabel.BEARISH

    def test_boundary_just_below_20_is_very_bearish(self):
        assert SignalCardLabel.from_score(19.9) == SignalCardLabel.VERY_BEARISH


# ---------------------------------------------------------------------------
# SignalCard model
# ---------------------------------------------------------------------------

class TestSignalCard:
    def _make_card(self, score=65.0, label=None, **kwargs) -> SignalCard:
        return SignalCard(
            name="momentum",
            score=score,
            label=label or SignalCardLabel.BULLISH,
            explanation="Strong price momentum with MACD cross.",
            top_positives=["RSI rising", "MACD bullish cross"],
            top_negatives=["Overbought short-term"],
            missing_data_warnings=[],
            **kwargs,
        )

    def test_create_minimal_card(self):
        card = self._make_card()
        assert card.name == "momentum"
        assert card.score == 65.0
        assert card.label == SignalCardLabel.BULLISH

    def test_score_defaults_0_to_100_range(self):
        card = self._make_card(score=0.0)
        assert card.score == 0.0
        card2 = self._make_card(score=100.0)
        assert card2.score == 100.0

    def test_top_positives_is_list(self):
        card = self._make_card()
        assert isinstance(card.top_positives, list)

    def test_top_negatives_is_list(self):
        card = self._make_card()
        assert isinstance(card.top_negatives, list)

    def test_missing_data_warnings_default_empty(self):
        card = SignalCard(
            name="trend",
            score=50.0,
            label=SignalCardLabel.NEUTRAL,
            explanation="Neutral trend.",
            top_positives=[],
            top_negatives=[],
        )
        assert card.missing_data_warnings == []

    def test_explanation_is_str(self):
        card = self._make_card()
        assert isinstance(card.explanation, str)

    def test_serialization(self):
        card = self._make_card()
        d = card.model_dump()
        assert d["name"] == "momentum"
        assert d["score"] == 65.0
        assert d["label"] == SignalCardLabel.BULLISH


# ---------------------------------------------------------------------------
# SignalCards container (11 cards)
# ---------------------------------------------------------------------------

class TestSignalCards:
    def _make_signal_cards(self) -> SignalCards:
        def _card(name: str, score: float = 50.0) -> SignalCard:
            return SignalCard(
                name=name,
                score=score,
                label=SignalCardLabel.from_score(score),
                explanation=f"{name} analysis.",
                top_positives=[],
                top_negatives=[],
            )

        return SignalCards(
            momentum=_card("momentum", 70.0),
            trend=_card("trend", 60.0),
            entry_timing=_card("entry_timing", 55.0),
            volume_accumulation=_card("volume_accumulation", 65.0),
            volatility_risk=_card("volatility_risk", 50.0),
            relative_strength=_card("relative_strength", 75.0),
            growth=_card("growth", 80.0),
            valuation=_card("valuation", 40.0),
            quality=_card("quality", 70.0),
            ownership=_card("ownership", 60.0),
            catalyst=_card("catalyst", 55.0),
        )

    def test_has_all_11_cards(self):
        sc = self._make_signal_cards()
        for attr in [
            "momentum", "trend", "entry_timing", "volume_accumulation",
            "volatility_risk", "relative_strength", "growth", "valuation",
            "quality", "ownership", "catalyst",
        ]:
            assert hasattr(sc, attr), f"Missing SignalCards.{attr}"

    def test_each_card_is_signal_card_instance(self):
        sc = self._make_signal_cards()
        assert isinstance(sc.momentum, SignalCard)
        assert isinstance(sc.growth, SignalCard)
        assert isinstance(sc.catalyst, SignalCard)

    def test_serialization_includes_all_cards(self):
        sc = self._make_signal_cards()
        d = sc.model_dump()
        for key in [
            "momentum", "trend", "entry_timing", "volume_accumulation",
            "volatility_risk", "relative_strength", "growth", "valuation",
            "quality", "ownership", "catalyst",
        ]:
            assert key in d

    def test_scores_preserved_in_cards(self):
        sc = self._make_signal_cards()
        assert sc.momentum.score == 70.0
        assert sc.growth.score == 80.0
        assert sc.valuation.score == 40.0


# ---------------------------------------------------------------------------
# StockAnalysisResult has signal_cards field
# ---------------------------------------------------------------------------

class TestStockAnalysisResultSignalCards:
    def test_has_signal_cards_field(self):
        from app.models.response import StockAnalysisResult
        import inspect
        fields = StockAnalysisResult.model_fields
        assert "signal_cards" in fields

    def test_signal_cards_defaults_none(self):
        # We can't instantiate StockAnalysisResult easily due to required fields,
        # but we can check that signal_cards is Optional with default None
        from app.models.response import StockAnalysisResult
        field = StockAnalysisResult.model_fields["signal_cards"]
        assert field.default is None


# ---------------------------------------------------------------------------
# HorizonRecommendation has signal_cards_weights field
# ---------------------------------------------------------------------------

class TestHorizonRecommendationWeights:
    def test_has_signal_cards_weights_field(self):
        fields = HorizonRecommendation.model_fields
        assert "signal_cards_weights" in fields

    def test_signal_cards_weights_default_empty_dict(self):
        field = HorizonRecommendation.model_fields["signal_cards_weights"]
        # Default should be empty dict (or a factory returning {})
        # Check via instantiation
        from app.models.market import MarketData, TechnicalIndicators
        # Just verify field exists and accepts a dict
        hr = HorizonRecommendation(
            horizon="short",
            decision="BUY_NOW_MOMENTUM",
            score=75.0,
            confidence="HIGH",
            summary="Strong momentum buy.",
            entry_plan={},
            exit_plan={},
            risk_reward={},
            position_sizing={},
            signal_cards_weights={"momentum": 0.25, "volume_accumulation": 0.20},
        )
        assert hr.signal_cards_weights == {"momentum": 0.25, "volume_accumulation": 0.20}

    def test_signal_cards_weights_defaults_to_empty(self):
        hr = HorizonRecommendation(
            horizon="long",
            decision="ACCUMULATE_ON_WEAKNESS",
            score=60.0,
            confidence="MEDIUM",
            summary="Long-term accumulate.",
            entry_plan={},
            exit_plan={},
            risk_reward={},
            position_sizing={},
        )
        assert hr.signal_cards_weights == {}
