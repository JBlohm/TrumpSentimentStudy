# Strategy Backtest V1

## Scope

This pass turns the topic study into a rules-based event-driven backtest while keeping the validated event-study mechanics unchanged:

- Same second-term study window
- Same authored-post universe
- Same exclusion of reblogs from the timed market study
- Same `15-minute` burst logic
- Same TWS `5-minute` bar data
- Same first-tradable-bar event anchor
- Same immediate vs delayed split using `anchor_delay_minutes <= 5` vs `> 5`

New outputs for this pass are in `outputs_strategy_v1/`.

## Important Correction

While building the backtest, I found and fixed a real delayed-event percentile bug in `truth_event_study.py`.

- Older `outputs_topics_v1` delayed slot percentiles were computed against the rounded event timestamp
- Delayed events must be benchmarked against the first tradable bar instead
- The corrected logic now uses `anchor_bar_ts_et`

Impact:

- Old delayed `abs_ret_60m_slot_percentile` non-null coverage: `396 / 8304` event rows (`4.8%`)
- Corrected delayed `abs_ret_60m_slot_percentile` non-null coverage: `8304 / 8304` event rows (`100.0%`)

This does not change the validated burst definitions, event counts, or the core delayed-vs-immediate event construction. It fixes the delayed baseline-comparison metric used for ranking shock size.

## Count Reconciliation

The corrected reference study in `outputs_strategy_v1/reference_*` still reconciles exactly to the validated baseline:

- Archive rows: `8,676`
- Authored Trump posts: `8,146`
- Empty-text authored posts: `2,638`
- Authored `15-minute` bursts: `3,272`
- Fully analyzable bursts: `3,256`
- Boundary-dropped bursts: `16`
- Timing split:
  - Immediate: `1,872`
  - Delayed: `1,384`
- Event rows per symbol: `3,256`

## Backtest Design

### Entry

- Wait `60 minutes` after the first tradable bar
- Measure the first-hour shock from the pre-event baseline to the `+60m` confirmation price
- Use threshold buckets on corrected `abs_ret_60m_slot_percentile`:
  - `all`
  - `p80`
  - `p90`

### Proxies Tested

These are option-style payoff proxies, not chain-level options backtests.

- `fade_debit_24h` / `fade_debit_72h`
  - Direction: opposite the first-hour shock
  - Width proxy: one initial shock unit
  - Payout clipped to `[-1R, +1R]`
- `fade_credit_24h` / `fade_credit_72h`
  - Direction: opposite the first-hour shock
  - Assumed short strike: `0.5` shock units beyond entry
  - Assumed spread width: `1.0` shock unit
  - Assumed credit: `0.35` of width
  - Reported in max-loss `R` units
- `follow_debit_24h`
  - Control: go with the first-hour move
- `long_straddle_24h` / `long_straddle_72h`
  - Control: long-vol realized-move proxy
  - Premium proxy: one initial shock unit
  - Capped at `+5R` to stop tiny-denominator outliers from dominating the means

### Limits

- No options chain, IV, bid/ask, slippage, borrow, commission, or assignment modeling
- ETF bars are still the underlying source, so this is not a true futures-options overnight fill study
- The long-straddle proxy is the least trustworthy because premium is not observed

## Main Results

### 1. Closed-market delayed events do look monetizable, but mostly as short-horizon fades

The strongest robust result is a delayed-event fade after the first `60` minutes, especially with stronger-than-usual first-hour shocks.

Delayed strategy summary:

| Strategy | Threshold | Trades | Win Rate | Median R | Mean R |
| --- | --- | ---: | ---: | ---: | ---: |
| fade_credit_24h | `all` | 8,266 | 71.6% | 0.538 | 0.124 |
| fade_credit_24h | `p80` | 6,057 | 76.4% | 0.538 | 0.202 |
| fade_credit_24h | `p90` | 4,874 | 77.3% | 0.538 | 0.223 |
| fade_debit_24h | `all` | 8,266 | 52.8% | 0.135 | 0.066 |
| fade_debit_24h | `p80` | 6,057 | 52.8% | 0.106 | 0.064 |
| fade_debit_24h | `p90` | 4,874 | 51.7% | 0.080 | 0.047 |
| follow_debit_24h | `all` | 8,266 | 46.5% | -0.135 | -0.066 |

Interpretation:

- The `24h` fade works better than the `72h` fade
- The credit-spread proxy is the cleanest “worked most of the time” setup
- The debit-spread fade has a smaller edge and is more selective
- Following the shock is a bad delayed-event control

### 2. Holding too long degrades the edge

The delayed fade is mostly a next-day phenomenon, not a multi-day hold.

- `fade_credit_24h`, delayed `p80`: mean `+0.202R`
- `fade_credit_72h`, delayed `p80`: mean `+0.034R`
- `fade_debit_24h`, delayed `p80`: mean `+0.064R`
- `fade_debit_72h`, delayed `p80`: mean `-0.009R`

Practical read:

- If you fade these events, the edge is front-loaded
- Extending to `72h` gives back too much of the advantage, especially in metals

### 3. Weekend and market-closed events are stronger than weekday delayed events

This is the part you were seeing correctly.

Delayed `p80` `fade_credit_24h`:

| Bucket | Symbol | Trades | Win Rate | Mean R |
| --- | --- | ---: | ---: | ---: |
| Weekend | QQQ | 626 | 94.9% | 0.431 |
| Weekday | QQQ | 437 | 77.3% | 0.186 |
| Weekend | SPY | 642 | 87.5% | 0.370 |
| Weekday | SPY | 413 | 76.8% | 0.207 |
| Weekend | USO | 418 | 76.1% | 0.247 |
| Weekday | USO | 312 | 75.0% | 0.179 |

Delayed `p80` `fade_debit_24h` shows the same direction, but less cleanly:

- Weekend `QQQ`: `65.3%` win, mean `+0.240R`
- Weekday `QQQ`: `59.0%` win, mean `+0.084R`
- Weekend `SPY`: `54.8%` win, mean `+0.217R`
- Weekday `SPY`: `50.4%` win, mean `+0.095R`

So yes: market-closed Trump bursts, especially weekend ones, are materially stronger volatility-and-fade setups than ordinary live-session bursts.

### 4. Immediate events are much less attractive

Immediate controls are weak.

- `fade_credit_24h`, immediate `all`: mean `-0.107R`
- `fade_debit_24h`, immediate `all`: mean `+0.009R`
- `follow_debit_24h`, immediate `all`: mean `-0.009R`

Interpretation:

- Once the market is already trading the post in real time, the edge mostly disappears
- The study still favors delayed-open events over near-immediate events

## Best Actionable Slices

Best delayed `p80` named-topic slices for `fade_credit_24h`, minimum `30` trades:

| Topic | Symbol | Trades | Win Rate | Mean R |
| --- | --- | ---: | ---: | ---: |
| immigration_border | SPY | 30 | 90.0% | 0.377 |
| immigration_border | QQQ | 31 | 93.5% | 0.359 |
| war_geopolitics | QQQ | 90 | 88.9% | 0.333 |
| domestic_politics_attacks | QQQ | 85 | 85.9% | 0.316 |
| tariffs_trade | QQQ | 30 | 86.7% | 0.311 |
| war_geopolitics | SLV | 84 | 83.3% | 0.311 |
| war_geopolitics | SPY | 90 | 78.9% | 0.298 |
| war_geopolitics | USO | 65 | 78.5% | 0.286 |

Best delayed `p80` named-topic slices for `fade_debit_24h`, minimum `30` trades:

| Topic | Symbol | Trades | Win Rate | Mean R |
| --- | --- | ---: | ---: | ---: |
| war_geopolitics | SLV | 84 | 65.5% | 0.310 |
| tariffs_trade | QQQ | 30 | 66.7% | 0.196 |
| immigration_border | QQQ | 31 | 71.0% | 0.176 |
| war_geopolitics | USO | 65 | 64.6% | 0.175 |
| immigration_border | SPY | 30 | 40.0% | 0.107 |

Practical ranking from this study:

1. `QQQ` / `MNQ` delayed-event fade is the strongest broad candidate
2. `SPY` / `MES` delayed-event fade is second
3. `USO` / `CL` is usable, but weaker than the index sleeve
4. `SLV` can work in specific geopolitics slices, but it is less stable outside those

## What Does Not Look Good

### Avoid holding the fade too long

Bad delayed `p80` `72h` fades:

- `domestic_politics_attacks` x `SLV`
  - `fade_debit_72h`: mean `-0.454R`, win `28.9%`
  - `fade_credit_72h`: mean `-0.328R`, win `40.8%`
- `immigration_border` x `SLV`
  - `fade_debit_72h`: mean `-0.290R`, win `35.5%`
- `war_geopolitics` x `GLD`
  - `fade_debit_72h`: mean `-0.209R`, win `34.5%`

### UNG is still the least reliable default fade sleeve

Bad delayed `p80` `24h` debit fades:

- `war_geopolitics` x `UNG`: mean `-0.222R`, win `37.2%`
- `domestic_politics_attacks` x `UNG`: mean `-0.167R`, win `40.9%`
- `immigration_border` x `UNG`: mean `-0.099R`, win `45.7%`

This is consistent with the earlier study: `UNG` moves hard, but it is not the cleanest reversion instrument.

### Do not over-interpret the long-straddle proxy

The capped long-straddle proxy often prints large positive means, but that is not a validated options result.

Why not:

- The premium is a placeholder, not observed IV
- Tiny first-hour shocks can still create unstable `R` multiples
- Futures-options trading hours would change the real fill mechanics for weekend events

Treat the long-vol numbers as a direction-of-interest check, not as production evidence.

## Practical Translation To An Options Portfolio

The best-supported mapping from this backtest is:

- Wait for a delayed event
- Wait another `60 minutes` after the first tradable bar
- If the first-hour move is unusually large, prefer a fade over a continuation trade
- Use short-duration defined-risk spreads
- Default horizon: `24h`, not `72h`

Most defensible structures from this study:

- `QQQ` / `MNQ`: fade with a short-dated call credit spread after up-shocks or put credit spread after down-shocks
- `SPY` / `MES`: same playbook, slightly weaker than `QQQ`
- `USO` / `CL`: selective delayed fade sleeve, especially in geopolitics and tariffs/trade slices

Least defensible default structure from this dataset:

- Blind long-gamma or long-straddle buying after every delayed event

## Files Created

Created in this pass:

- `outputs_strategy_v1/reference_event_level_market_reaction.csv`
- `outputs_strategy_v1/reference_authored_bursts.csv`
- `outputs_strategy_v1/reference_topic_symbol_timing_summary.csv`
- `outputs_strategy_v1/reference_summary.json`
- `outputs_strategy_v1/reference_weekday_hour_cluster.csv`
- `outputs_strategy_v1/reference_topic_tagging_rules.json`
- `outputs_strategy_v1/strategy_trade_log.csv`
- `outputs_strategy_v1/strategy_timing_summary.csv`
- `outputs_strategy_v1/strategy_symbol_summary.csv`
- `outputs_strategy_v1/strategy_topic_symbol_summary.csv`
- `outputs_strategy_v1/strategy_weekend_summary.csv`
- `outputs_strategy_v1/strategy_best_and_worst_slices.csv`
- `outputs_strategy_v1/strategy_assumptions.json`
- `outputs_strategy_v1/backtest_summary.json`

Code and docs updated:

- `truth_event_study.py`
- `AGENTS.md`
- `STRATEGY_BACKTEST_V1.md`

## Caveats

- This is still a bar-based underlying backtest with option-like payoff proxies
- It is not a broker-fill backtest and not a live-trade recommendation
- Older `outputs_topics_v1` delayed percentile rankings should not be used for new threshold selection
- `2638` authored posts still have empty body text in the archive, so topic tagging remains text-limited by construction
