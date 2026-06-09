# Implementation Progress

| Story | Status | Tests Written | Tests Passing | Notes |
|-------|--------|--------------|---------------|-------|
| US-001 Stock Archetype | DONE | 19 | 19 | stock_archetype_service.py |
| US-002 Market Regime | DONE | 18 | 18 | market_regime_service.py |
| US-003 Growth-Adj Valuation | DONE | 8 | 8 | score_valuation_with_archetype() |
| US-004 Scoring Overhaul | DONE | 7 | 7 | New weight dicts, regime multipliers |
| US-005 Decision Labels | DONE | 12 | 12 | 14 labels, regime-aware decide functions |
| US-006 Data Completeness | DONE | 16 | 16 | data_completeness_service.py |
| US-007 Signal Profile | DONE | 22 | 22 | signal_profile_service.py |
| US-008 Sector Macro Score | DONE | — | — | Router wired, no isolated tests needed |
| US-009 Backtest Segments | DONE | 14 | 14 | by_regime + by_archetype in metrics.py |
| US-010 Frontend Upgrade | DONE | — | — | 0 TS errors, SignalProfileCard + RegimeArchetypeBar |

**Total: 241 Python tests passing · 0 TypeScript errors**

## Test Command
```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v --tb=short
```

## Regression Gate
All previously passing tests must still pass after each story.
