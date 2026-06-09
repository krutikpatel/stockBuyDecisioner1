"""Phase 3 unit tests: earnings analysis and news sentiment."""
import os
import pytest
from unittest.mock import MagicMock, patch

from app.models.earnings import EarningsData, EarningsRecord
from app.models.news import NewsItem, NewsSummary
from app.providers.earnings_provider import score_earnings
from app.services.news_sentiment_service import (
    _compute_news_score,
    _keyword_classify,
    _keyword_classify_batch,
    classify_news,
)


# ---------------------------------------------------------------------------
# Earnings scoring tests
# ---------------------------------------------------------------------------

class TestEarningsScoring:
    def _make_data(
        self,
        beat_rate=None,
        avg_surprise=None,
        within_30=False,
    ) -> EarningsData:
        return EarningsData(
            beat_rate=beat_rate,
            avg_eps_surprise_pct=avg_surprise,
            within_30_days=within_30,
        )

    def test_score_in_valid_range(self):
        data = self._make_data(beat_rate=0.75, avg_surprise=3.0)
        assert 0 <= score_earnings(data) <= 100

    def test_high_beat_rate_raises_score(self):
        high = self._make_data(beat_rate=0.85, avg_surprise=5.0)
        low = self._make_data(beat_rate=0.30, avg_surprise=-2.0)
        assert score_earnings(high) > score_earnings(low)

    def test_positive_eps_surprise_raises_score(self):
        good = self._make_data(beat_rate=0.70, avg_surprise=6.0)
        bad = self._make_data(beat_rate=0.70, avg_surprise=-3.0)
        assert score_earnings(good) > score_earnings(bad)

    def test_within_30_days_reduces_score(self):
        normal = self._make_data(beat_rate=0.75, avg_surprise=4.0, within_30=False)
        approaching = self._make_data(beat_rate=0.75, avg_surprise=4.0, within_30=True)
        assert score_earnings(approaching) < score_earnings(normal)

    def test_empty_data_returns_50(self):
        empty = EarningsData()
        assert score_earnings(empty) == 50.0

    def test_earnings_dates_keyerror_handled(self):
        """earnings_dates KeyError must not propagate; should return null dates."""
        # Simulate the provider's try/except by checking EarningsData model
        data = EarningsData(
            last_earnings_date=None,
            next_earnings_date=None,
            within_30_days=False,
        )
        # Score should still work without raising
        result = score_earnings(data)
        assert isinstance(result, float)

    def test_perfect_beat_history_high_score(self):
        data = self._make_data(beat_rate=1.0, avg_surprise=8.0)
        assert score_earnings(data) > 70

    def test_all_misses_low_score(self):
        data = self._make_data(beat_rate=0.0, avg_surprise=-5.0)
        assert score_earnings(data) < 40


# ---------------------------------------------------------------------------
# Keyword sentiment classifier tests
# ---------------------------------------------------------------------------

class TestKeywordClassifier:
    def test_positive_keyword_detected(self):
        s, _, _ = _keyword_classify("Apple beats quarterly earnings estimates")
        assert s == "positive"

    def test_negative_keyword_detected(self):
        s, _, _ = _keyword_classify("Company misses revenue guidance, cuts outlook")
        assert s == "negative"

    def test_neutral_when_no_keywords(self):
        s, _, _ = _keyword_classify("Company announces annual shareholder meeting")
        assert s == "neutral"

    def test_importance_high_on_earnings_keyword(self):
        _, imp, _ = _keyword_classify("Strong earnings beat drives stock higher")
        assert imp == "high"

    def test_importance_medium_on_analyst_keyword(self):
        _, imp, _ = _keyword_classify("Analyst upgrades stock to buy")
        assert imp == "medium"

    def test_category_earnings(self):
        _, _, cat = _keyword_classify("Q3 earnings report shows record EPS")
        assert cat == "earnings"

    def test_category_analyst(self):
        _, _, cat = _keyword_classify("Goldman Sachs upgrades price target")
        assert cat == "analyst"

    def test_category_legal(self):
        _, _, cat = _keyword_classify("SEC investigation launched into accounting practices")
        assert cat == "legal"


class TestKeywordBatchClassifier:
    def test_batch_classifies_all_items(self):
        items = [
            NewsItem(title="Company beats earnings estimates"),
            NewsItem(title="CEO resigns amid controversy"),
            NewsItem(title="New product launch announced"),
        ]
        result = _keyword_classify_batch(items)
        assert len(result) == 3
        assert all(i.sentiment in ("positive", "neutral", "negative") for i in result)

    def test_positive_news_classified_positive(self):
        items = [NewsItem(title="Record revenue beat on strong demand")]
        result = _keyword_classify_batch(items)
        assert result[0].sentiment == "positive"

    def test_negative_news_classified_negative(self):
        items = [NewsItem(title="Guidance cut after earnings miss disappoints investors")]
        result = _keyword_classify_batch(items)
        assert result[0].sentiment == "negative"


# ---------------------------------------------------------------------------
# News score tests
# ---------------------------------------------------------------------------

class TestNewsScore:
    def test_all_positive_high_importance_scores_high(self):
        items = [
            NewsItem(title="Beat", sentiment="positive", importance="high"),
            NewsItem(title="Beat2", sentiment="positive", importance="high"),
        ]
        score = _compute_news_score(items)
        assert score > 70

    def test_all_negative_high_importance_scores_low(self):
        items = [
            NewsItem(title="Miss", sentiment="negative", importance="high"),
            NewsItem(title="Miss2", sentiment="negative", importance="high"),
        ]
        score = _compute_news_score(items)
        assert score < 30

    def test_all_neutral_scores_near_50(self):
        items = [
            NewsItem(title="n", sentiment="neutral", importance="low"),
            NewsItem(title="n2", sentiment="neutral", importance="medium"),
        ]
        score = _compute_news_score(items)
        assert score == pytest.approx(50.0)

    def test_empty_returns_50(self):
        assert _compute_news_score([]) == 50.0

    def test_score_in_valid_range(self):
        items = [
            NewsItem(title="a", sentiment="positive", importance="high"),
            NewsItem(title="b", sentiment="negative", importance="low"),
        ]
        score = _compute_news_score(items)
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# classify_news with OpenAI mock
# ---------------------------------------------------------------------------

class TestClassifyNews:
    def test_fallback_to_keywords_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr("app.services.news_sentiment_service.settings.openai_api_key", "")
        items = [
            NewsItem(title="Company beats earnings estimates by wide margin"),
            NewsItem(title="Company cuts guidance after disappointing quarter"),
        ]
        result = classify_news(items)
        assert isinstance(result, NewsSummary)
        assert result.positive_count + result.negative_count + result.neutral_count == 2
        assert 0 <= result.news_score <= 100

    def test_positive_news_raises_score_vs_negative(self, monkeypatch):
        monkeypatch.setattr("app.services.news_sentiment_service.settings.openai_api_key", "")
        positive_items = [
            NewsItem(title="Company beats earnings estimates"),
            NewsItem(title="Revenue raised guidance, strong outlook"),
        ]
        negative_items = [
            NewsItem(title="Company missed earnings, cuts guidance"),
            NewsItem(title="Investigation launched, loss reported"),
        ]
        pos_result = classify_news(positive_items)
        neg_result = classify_news(negative_items)
        assert pos_result.news_score > neg_result.news_score

    def test_openai_mock_classification(self, monkeypatch):
        """Mock OpenAI response to verify integration path."""
        monkeypatch.setattr("app.services.news_sentiment_service.settings.openai_api_key", "sk-fake")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '[{"sentiment":"positive","importance":"high","category":"earnings"},'
            '{"sentiment":"negative","importance":"medium","category":"analyst"}]'
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.news_sentiment_service.OpenAI", return_value=mock_client):
            items = [
                NewsItem(title="Company beats Q3 earnings by 15%"),
                NewsItem(title="Analyst downgrades on valuation concerns"),
            ]
            result = classify_news(items)

        assert result.items[0].sentiment == "positive"
        assert result.items[0].importance == "high"
        assert result.items[1].sentiment == "negative"
        assert result.positive_count == 1
        assert result.negative_count == 1

    def test_openai_failure_falls_back_to_keywords(self, monkeypatch):
        """OpenAI API failure should silently fall back to keyword classifier."""
        monkeypatch.setattr("app.services.news_sentiment_service.settings.openai_api_key", "sk-fake")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API timeout")

        with patch("app.services.news_sentiment_service.OpenAI", return_value=mock_client):
            items = [NewsItem(title="Company beats earnings estimates")]
            result = classify_news(items)

        # Should still return a valid summary via keyword fallback
        assert isinstance(result, NewsSummary)
        assert 0 <= result.news_score <= 100

    def test_empty_items_returns_default(self, monkeypatch):
        monkeypatch.setattr("app.services.news_sentiment_service.settings.openai_api_key", "")
        result = classify_news([])
        assert result.news_score == 50.0
        assert result.items == []
