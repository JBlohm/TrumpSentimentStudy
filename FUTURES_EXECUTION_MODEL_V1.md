# Futures Execution Model V1

## Scope

This pass adds a stricter execution layer on top of the corrected `v1` event study and strategy work.

- Same second-term study window
- Same authored-post universe
- Same `15-minute` burst logic
- Same exclusion of reblogs from the timed market study
- Same `5-minute` TWS market data
- Same first-tradable-bar anchor
- Same delayed-event focus for market-closed Trump bursts

New outputs are in `outputs_strategy_v1/futures_execution_v1/`.

## What Changed

Instead of a coarse end-of-horizon options proxy, this pass models explicit delayed-event fade execution rules for:

- `QQQ -> MNQ`
- `SPY -> MES`
- `USO -> CL`

Execution assumptions:

- delayed events only
- entry windows: `30m`, `60m`, `90m` after the first tradable bar
- entry filters: `all`, `p80`, `p90` using entry-window-specific same-slot absolute-return percentiles
- stop logic: `0.75x` and `1.0x` of the initial shock, evaluated on `5-minute` `high/low`
- profit target: first cross back through the pre-event baseline
- time stops: `12h` and `24h`
- conservative tie-break: if stop and target are both touched in the same `5-minute` bar, count it as a stop
- fill convention: enter at the close of the chosen entry bar; evaluate stops and targets from the next bar onward

This is still a proxy study. It does **not** use actual `MNQ` / `MES` / `CL` futures trades or options chains.

## Count Reconciliation

Reference counts still reconcile exactly to the validated baseline:

- archive rows: `8,676`
- authored posts: `8,146`
- empty-text authored posts: `2,638`
- authored `15-minute` bursts: `3,272`
- analyzable bursts: `3,256`
- boundary-dropped bursts: `16`
- timing split: `1,872` immediate, `1,384` delayed

Execution-study row counts:

- delayed entry signals: `12,428`
- stop/target/time-stop trade rows: `49,694`

The slight shortfall from `1,384 x 3 x 3 = 12,456` comes from end-of-sample events that do not have enough forward bars for every entry window.

## Main Findings

### 1. `MNQ` is still the cleanest sleeve

Best `MNQ` config:

| Threshold | Entry | Stop | Time Stop | Trades | Win Rate | Median R | Mean R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p90` | `60m` | `0.75x` | `24h` | `847` | `66.7%` | `1.333` | `0.528` |

`MNQ` top configs cluster tightly around:

- `60m` entry
- `p80` / `p90` filters
- `0.75x` stop
- `24h` time stop

The close runner-up is the same setup at `p80` with `1,063` trades and mean `0.512R`. A `12h` stop still works, but it is slightly weaker than `24h`.

### 2. `MES` works, but the edge is materially smaller

Best `MES` config:

| Threshold | Entry | Stop | Time Stop | Trades | Win Rate | Median R | Mean R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p90` | `60m` | `0.75x` | `24h` | `807` | `53.9%` | `0.736` | `0.280` |

`MES` is still tradable, but the distribution is less forgiving than `MNQ`.

- second-best `MES` setup is `p90`, `90m`, `0.75x`, `24h`, mean `0.274R`
- `1.0x` stops raise win rate, but usually lower mean `R`
- the `MES` edge looks like a moderate mean-reversion sleeve, not an outsized one

### 3. `CL` is weaker and more timing-sensitive

Best `CL` config:

| Threshold | Entry | Stop | Time Stop | Trades | Win Rate | Median R | Mean R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p90` | `90m` | `1.0x` | `12h` | `481` | `70.9%` | `0.285` | `0.248` |

`CL` only gets respectable after the model becomes stricter:

- later entry: `90m`, not `30m`
- wider stop: `1.0x`, not `0.75x`
- shorter time stop: `12h`, not `24h`

That is not a sign of strength. It means `CL` is the noisiest sleeve in this study and needs more room plus later confirmation before the fade behaves.

### 4. Weekend strength survives in `MNQ`, but not uniformly in every config

Recommended-config weekend vs weekday split:

| Product | Bucket | Trades | Win Rate | Median R | Mean R |
| --- | --- | ---: | ---: | ---: | ---: |
| `MNQ` | weekday | `300` | `64.7%` | `1.333` | `0.504` |
| `MNQ` | weekend | `547` | `67.8%` | `1.333` | `0.541` |
| `MES` | weekday | `316` | `55.7%` | `1.333` | `0.321` |
| `MES` | weekend | `491` | `52.7%` | `0.515` | `0.254` |
| `CL` | weekday | `174` | `66.7%` | `0.304` | `0.225` |
| `CL` | weekend | `307` | `73.3%` | `0.285` | `0.262` |

Takeaway:

- `MNQ`: weekend advantage still holds
- `MES`: the best strict config is actually stronger on weekday delayed events than on weekend delayed events
- `CL`: weekends help, but much of the result still comes from time-stop exits rather than clean baseline reversion

## Recommended Templates

These are the most defensible templates from this pass.

| Product | Proxy | Threshold | Entry | Stop | Time Stop | Trades | Win Rate | Mean R | Read |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MNQ` | `QQQ` | `p90` | `60m` | `0.75x` | `24h` | `847` | `66.7%` | `0.528` | strongest and cleanest |
| `MES` | `SPY` | `p90` | `60m` | `0.75x` | `24h` | `807` | `53.9%` | `0.280` | usable, smaller edge |
| `CL` | `USO` | `p90` | `90m` | `1.0x` | `12h` | `481` | `70.9%` | `0.248` | selective only |

My ranking from this pass:

1. `MNQ`
2. `MES`
3. `CL`

## Futures-Options Mapping

The mapping in `futures_options_structure_map.csv` is heuristic, not chain-validated.

Primary structures:

- `MNQ`: after an up-shock, prefer a `call credit spread`; after a down-shock, prefer a `put credit spread`
- `MES`: same as `MNQ`
- `CL`: after an up-shock, prefer a `put debit spread`; after a down-shock, prefer a `call debit spread`

Secondary structures:

- `MNQ` / `MES`: use debit spreads when you want cleaner directional convexity and less reliance on containment
- `CL`: use credit spreads only if you intentionally want a containment trade and can tolerate the extra noise

Official product pages used for the structure map:

- [`MNQ` options](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.options.html)
- [`MES` options](https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.contractSpecs.options.html)
- [Micro E-mini options overview and hours](https://www.cmegroup.com/trading/equity-index/us-index/micro-e-mini-options.html)
- [`CL` options](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.options.html)
- [`CL` weekly options hours FAQ](https://www.cmegroup.com/articles/faqs/faq-tuesday-and-thursday-weekly-wti-options.html)

## Caveats

- This is still an ETF-proxy study. `QQQ`, `SPY`, and `USO` are standing in for `MNQ`, `MES`, and `CL`.
- There is no live futures order book, no slippage model, no spread crossing, and no roll logic.
- There is no options chain, no implied-volatility history, no bid/ask, and no assignment modeling.
- The options structure map is a translation layer for the futures signals, not a validated options P&L backtest.
- `CL` is the least trustworthy sleeve because the underlying backtest uses `USO` as the tradable-price proxy.

## Files Created

Created in this pass:

- `outputs_strategy_v1/futures_execution_v1/execution_signals.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_trade_log.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_symbol_summary.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_config_summary.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_weekend_summary.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_best_and_worst_configs.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_recommended_configs.csv`
- `outputs_strategy_v1/futures_execution_v1/futures_options_structure_map.csv`
- `outputs_strategy_v1/futures_execution_v1/execution_assumptions.json`
- `outputs_strategy_v1/futures_execution_v1/execution_summary.json`
- `outputs_strategy_v1/futures_execution_v1/reference_summary.json`

