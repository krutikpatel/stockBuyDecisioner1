from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_KEY_PATTERN = re.compile(r"([Aa]pi[_-]?[Kk]ey|apikey|token)=([^&\s\"']+)", re.IGNORECASE)

_SUMMARY_FILENAME = "run_metrics_data_layer.json"


def _redact(text: str) -> str:
    return _KEY_PATTERN.sub(lambda m: f"{m.group(1)}=***", text)


def _redact_dict(obj: Any) -> Any:
    if isinstance(obj, str):
        return _redact(obj)
    if isinstance(obj, dict):
        return {_redact(k) if isinstance(k, str) else k: _redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_dict(v) for v in obj]
    return obj


@dataclass
class ProviderStats:
    cache_hits: int = 0
    cache_misses: int = 0
    api_errors: dict[int, int] = field(default_factory=dict)
    latency_samples: list[float] = field(default_factory=list)
    throttle_events: int = 0


class StatsCollector:
    """Collects per-provider data-layer stats for a single run.

    Call record_* methods during the run; call build_summary() / write_summary()
    at the end to emit a JSON snapshot to the run directory.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderStats] = {}

    def _provider(self, name: str) -> ProviderStats:
        if name not in self._providers:
            self._providers[name] = ProviderStats()
        return self._providers[name]

    def record_cache_hit(self, provider: str) -> None:
        self._provider(provider).cache_hits += 1

    def record_cache_miss(self, provider: str) -> None:
        self._provider(provider).cache_misses += 1

    def record_latency(self, provider: str, seconds: float) -> None:
        self._provider(provider).latency_samples.append(seconds)

    def record_api_error(self, provider: str, status_code: int) -> None:
        errs = self._provider(provider).api_errors
        errs[status_code] = errs.get(status_code, 0) + 1

    def record_throttle(self, provider: str) -> None:
        self._provider(provider).throttle_events += 1

    def build_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for name, ps in self._providers.items():
            total_cache = ps.cache_hits + ps.cache_misses
            hit_rate = round(ps.cache_hits / total_cache, 4) if total_cache else None
            latencies = sorted(ps.latency_samples)
            summary[name] = {
                "cache_hits": ps.cache_hits,
                "cache_misses": ps.cache_misses,
                "cache_hit_rate": hit_rate,
                "api_errors_by_status": dict(ps.api_errors),
                "latency_p50_ms": _percentile(latencies, 50),
                "latency_p99_ms": _percentile(latencies, 99),
                "throttle_events": ps.throttle_events,
            }
        return _redact_dict(summary)

    def write_summary(self, run_dir: str | Path) -> Path:
        out = Path(run_dir) / _SUMMARY_FILENAME
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.build_summary(), indent=2) + "\n")
        return out


def _percentile(sorted_values: list[float], pct: int) -> float | None:
    if not sorted_values:
        return None
    idx = max(0, int(len(sorted_values) * pct / 100) - 1)
    return round(sorted_values[idx] * 1000, 3)  # convert to ms
