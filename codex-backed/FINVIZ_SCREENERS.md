# Finviz Screeners — Derived from codex-backed Configs

These screeners are approximations of the entry routes defined in `configs/technical_setup_config.json` and `configs/entry_signal_config.json`. Each screener surfaces candidates; manual chart review is still required for signals Finviz cannot express.

---

## Screener 1: GROWTH_LEADER_PULLBACK

**Route:** `pullback_entry_route` | **Setup:** `GROWTH_LEADER_PULLBACK`

**Logic:** Price above SMA50 + SMA200 (uptrend), RSI 40–60 (healthy pullback zone), low relative volume (sellers drying up).

```
https://finviz.com/screener.ashx?v=111&f=ta_sma50_pa,ta_sma200_pa,ta_rsi_o40,ta_rsi_u60,sh_relvol_u0.5
```

**Gap — verify manually on chart:**
- SMA50 pullback zone (within ±5%): Finviz only filters above/below, not proximity
- SMA50 slope rising: no Finviz filter

---

## Screener 2: BREAKOUT_MOMENTUM

**Route:** `breakout_entry_route` | **Setup:** `BREAKOUT_MOMENTUM`

**Logic:** Near 52w high (proxy for near 20d high), relative volume ≥ 2× average, price above SMA50.

```
https://finviz.com/screener.ashx?v=111&f=ta_sma50_pa,ta_highlow52w_b0to3h,sh_relvol_o2
```

**Gap — verify manually on chart:**
- Your config checks `dist_from_20d_high >= -1`; Finviz only has 52w high proximity (`b0to3h`)
- RS vs SPY: sort results by 1-month performance as a manual proxy

---

## Screener 3: OVERSOLD_REVERSAL / DOWNTREND_REBOUND

**Routes:** `oversold_rebound_route`, `quality_dislocation_route` | **Setups:** `OVERSOLD_REVERSAL`, `DOWNTREND_REBOUND_CANDIDATE`, `BROKEN_CHART_QUALITY_RECOVERY`

**Logic:** RSI 30–40 zone (oversold but not crashed).

```
https://finviz.com/screener.ashx?v=111&f=ta_rsi_o30,ta_rsi_u40
```

**Gap — verify manually on chart:**
- `rsi_slope > 0` (RSI turning up): no Finviz filter — this is the most important condition; visually confirm RSI curl on the daily chart
- For `dist_from_52w_high <= -30`, add filter `ta_highlow52w_b20to50h` to the URL

---

## Screener 4: BULL_LEADERSHIP

**Route:** `bull_leadership_route`

**Logic:** Uptrend (above SMA50 + SMA200), RSI 50–70 (momentum without being overextended).

```
https://finviz.com/screener.ashx?v=111&f=ta_sma50_pa,ta_sma200_pa,ta_rsi_o50,ta_rsi_u70
```

**Gap — verify manually on chart:**
- `rs_vs_spy_20d >= 3.0`: no per-stock RS% vs SPY filter in Finviz — sort results by 1-month performance column as a proxy
- `sma50_slope >= 0`: no slope filter — visually confirm SMA50 is rising
- `sma20_relative <= 8`: confirm price is not more than 8% above the 20d SMA

---

## Finviz Filter Limitations vs Config Signals

| Config signal | Finviz limitation |
|---|---|
| `sma50_relative` between ±5% | Only above/below; no proximity range |
| `sma50_slope >= 0` | No slope filter exists |
| `rs_vs_spy_20d >= 3.0` | No per-stock RS% vs SPY — use performance sort manually |
| `rsi_slope > 0` | No RSI direction filter — must visually inspect chart |
| `volume_dryup_ratio <= 0.8` | Closest: `sh_relvol_u0.5` (today's rel vol, not multi-day avg ratio) |
| `dist_from_20d_high >= -1` | Only 52w high proximity available |

---

## Notes

- These screeners surface **candidate lists only** — the strategy's scoring and regime-gating logic cannot be replicated in Finviz.
- Market regime (`BULL_RISK_ON`, `BEAR_RISK_OFF`, etc.) is evaluated by `codex-backed` against SPY/VIX data and has no Finviz equivalent.
- The **excluded ticker list** in `entry_signal_config.json` (`weak_ticker_exclusion_route`) should be filtered out manually from any Finviz results.
- Verify the `ta_highlow52w_b0to3h` and `sh_relvol_u0.5` filter names in the Finviz UI — these are less standardized and may differ.
