# Iterative Improvements Log

This log tracks five requested improvement loops.

Each loop follows:

1. Run full native backtest.
2. Investigate result.
3. Record proposed improvement.
4. Implement improvement.

All full runs use `--workers 1` because multiprocessing is blocked in the current sandbox.

Baseline before this loop:

- `my_run_02`: 51,176 trades, avg return 0.7717%, win rate 35.6984%, profit factor 1.3511, stop rate 61.0423%.
- `my_run_03_workers1`: 41,522 trades, avg return 0.9325%, win rate 36.4843%, profit factor 1.4201, stop rate 60.0429%.

## Iteration 1

Run:

- `iter_01`
- 161,842 decisions
- 41,522 trades
- avg return 0.9325%
- median return 0.0%
- win rate 36.4843%
- profit factor 1.4201

Investigation:

- Weakest active strategy was `oversold_rebound`.
- `oversold_rebound`: 3,236 trades, avg return 0.2644%, median -1.5046%, profit factor 1.1204.
- It fired mostly in `BULL_RISK_ON` and `LIQUIDITY_RALLY`, where stop-loss rates were about 65%.
- The better rebound edge is already captured by `quality_dislocation` in `BEAR_RISK_OFF` and `SIDEWAYS_CHOPPY`.

Improvement Implemented:

- Changed `oversold_rebound` to watchlist-only by removing its actionable `BUY_STARTER` threshold.
- This should reduce weak tactical rebound trades without touching the stronger quality-dislocation setup.

## Iteration 2

Run:

- `iter_02`
- 161,842 decisions
- 38,286 trades
- avg return 0.9889%
- median return 0.0%
- win rate 36.9299%
- profit factor 1.4452

Investigation:

- Iteration 1 change helped: fewer trades, higher average return, higher win rate, higher profit factor, lower stop rate.
- Weakest remaining large strategy was broad `bull_leadership`.
- `bull_leadership`: 17,534 trades, avg return 0.5254%, profit factor 1.2389, stop rate 61.4064%.
- Concrete bull-market setups should be handled by `BREAKOUT_MOMENTUM`, `GROWTH_LEADER_PULLBACK`, or `extended_starter`; broad leadership without a concrete setup is still too noisy.

Improvement Implemented:

- Changed broad `bull_leadership` to watchlist-only.
- This removes broad non-setup leadership trades while preserving stronger concrete setup routes.

## Iteration 3

Run:

- `iter_03`
- 161,842 decisions
- 20,752 trades
- avg return 1.3806%
- median return 0.0%
- win rate 38.7914%
- profit factor 1.6162

Investigation:

- Iteration 2 change helped strongly: trade count dropped while average return, win rate, profit factor, and stop rate all improved.
- Weakest remaining large strategy is `pullback_entry`.
- `pullback_entry`: 11,206 trades, avg return 0.5747%, profit factor 1.2930, stop rate 61.1815%.
- All pullback trades are `BUY_FULL`, so label threshold changes will not split the bucket.
- Setup quality is the better lever.

Improvement Implemented:

- Tightened `GROWTH_LEADER_PULLBACK` from one optional confirmation to two optional confirmations.
- Pullbacks now require both `VOLUME_DRY_UP` and `RS_LEADER_VS_SPY`.

## Iteration 4

Run:

- `iter_04`
- 161,842 decisions
- 11,274 trades
- avg return 2.0576%
- median return 0.0%
- win rate 40.7220%
- profit factor 1.8312

Investigation:

- Iteration 3 change helped strongly: trade count dropped while average return, win rate, profit factor, and stop rate all improved.
- Remaining `GROWTH_LEADER_PULLBACK` trades are much smaller but still mixed.
- `GROWTH_LEADER_PULLBACK` in `SIDEWAYS_CHOPPY`: 590 trades, avg return 0.0024%, profit factor 1.0011, stop rate 62.3729%.
- Pullbacks in `BEAR_RISK_OFF` are better and pullbacks in `BULL_RISK_ON` are still modestly positive.

Improvement Implemented:

- Blocked `GROWTH_LEADER_PULLBACK` in `SIDEWAYS_CHOPPY`.
- Pullback route now allows only `BEAR_RISK_OFF` and `BULL_RISK_ON`.

## Iteration 5

Run:

- `iter_05`
- 161,842 decisions
- 10,684 trades
- avg return 2.1711%
- median return 0.0%
- win rate 41.0614%
- profit factor 1.8721

Investigation:

- Iteration 4 change helped again: fewer trades, higher average return, higher win rate, higher profit factor, and lower stop rate.
- Remaining `GROWTH_LEADER_PULLBACK` edge is concentrated in `BEAR_RISK_OFF`.
- `GROWTH_LEADER_PULLBACK` in `BEAR_RISK_OFF`: 308 trades, avg return 1.6900%, profit factor 2.0102.
- `GROWTH_LEADER_PULLBACK` in `BULL_RISK_ON`: 820 trades, avg return 0.5797%, profit factor 1.3093, stop rate 61.9512%.

Improvement Implemented:

- Restricted `GROWTH_LEADER_PULLBACK` to `BEAR_RISK_OFF` only.
- This final loop implementation is not yet measured by a sixth backtest; the next run should validate it.

## Five-Loop Result Summary

| run | trades | avg_return_pct | median_return_pct | win_rate_pct | profit_factor | stop_rate_pct |
| --- | --- | --- | --- | --- | --- | --- |
| iter_01 | 41522 | 0.9325 | 0.0 | 36.4843 | 1.4201 | 60.0429 |
| iter_02 | 38286 | 0.9889 | 0.0 | 36.9299 | 1.4452 | 59.6406 |
| iter_03 | 20752 | 1.3806 | 0.0 | 38.7914 | 1.6162 | 58.1486 |
| iter_04 | 11274 | 2.0576 | 0.0 | 40.722 | 1.8312 | 55.5969 |
| iter_05 | 10684 | 2.1711 | 0.0 | 41.0614 | 1.8721 | 55.2228 |

Net measured change from `iter_01` to `iter_05`:

- Trade count reduced by 30,838.
- Average return improved from 0.9325% to 2.1711%.
- Win rate improved from 36.4843% to 41.0614%.
- Profit factor improved from 1.4201 to 1.8721.
- Stop-loss rate improved from 60.0429% to 55.2228%.

The final loop implementation, restricting `GROWTH_LEADER_PULLBACK` to `BEAR_RISK_OFF`, is intentionally not included in these measured numbers because it was applied after `iter_05`.
