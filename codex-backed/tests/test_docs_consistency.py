"""S5.2 — Lightweight doc consistency tests.

Checks that key architectural terms exist in the canonical reference docs.
These tests catch documentation drift without verifying prose quality.
"""

from __future__ import annotations

from pathlib import Path

_CODEX = Path(__file__).resolve().parents[1]
_REPO_ROOT = _CODEX.parent

_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_HLD = _CODEX / "HLD.md"
_LLD = _CODEX / "LLD.md"
_BACKTEST_README = _CODEX / "BACKTEST_README.md"


def test_claude_md_mentions_data_provider_config_path():
    text = _CLAUDE_MD.read_text()
    assert "data_provider_config.json" in text, (
        "CLAUDE.md must mention data_provider_config.json in the config files section"
    )


def test_hld_describes_provider_protocol_layer():
    text = _HLD.read_text()
    assert "PriceProvider" in text and "FundamentalsProvider" in text, (
        "HLD.md must describe the PriceProvider and FundamentalsProvider protocol layer"
    )


def test_lld_describes_composite_and_field_overrides():
    text = _LLD.read_text()
    assert "CompositeFundamentalsProvider" in text, (
        "LLD.md must document CompositeFundamentalsProvider"
    )
    assert "field_overrides" in text, (
        "LLD.md must document field_overrides semantics"
    )


def test_backtest_readme_documents_data_mode_cli_flag():
    text = _BACKTEST_README.read_text()
    assert "--data-mode" in text, (
        "BACKTEST_README.md must document the --data-mode CLI flag"
    )
