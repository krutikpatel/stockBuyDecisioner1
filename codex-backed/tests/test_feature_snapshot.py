from codex_backed.features.builder import build_feature_snapshot_from_mapping
from codex_backed.features.snapshot import FeatureSnapshot


def test_feature_snapshot_contains_signal_card_fields():
    snapshot = FeatureSnapshot(
        ticker="AAPL",
        date="2024-01-02",
        price=100.0,
        sc_volatility_risk=72.0,
        sc_growth=85.0,
    )

    as_dict = snapshot.to_dict()

    assert as_dict["sc_volatility_risk"] == 72.0
    assert as_dict["sc_growth"] == 85.0
    assert "sc_trend" in as_dict


def test_build_feature_snapshot_from_mapping_ignores_unknown_keys():
    snapshot = build_feature_snapshot_from_mapping(
        {
            "ticker": "MSFT",
            "date": "2024-01-02",
            "price": 120.0,
            "rsi14": 35.0,
            "unknown": "ignored",
        }
    )

    assert snapshot.ticker == "MSFT"
    assert snapshot.rsi14 == 35.0
    assert not hasattr(snapshot, "unknown")

