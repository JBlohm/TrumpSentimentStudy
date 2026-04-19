# TrumpSentimentStudy

Event-study and trading-research repo for Donald Trump Truth Social posting activity during his second term, with downstream topic analysis, strategy backtests, stricter futures-style execution templates, and a realtime alert bot.

## What This Repo Contains

- a validated baseline event study on Trump Truth Social posting bursts and market reaction
- a deterministic topic study that keeps the baseline event definitions unchanged
- a rules-based strategy backtest built on the corrected reference event outputs
- a stricter delayed-event execution study for `MNQ`, `MES`, and `CL` using ETF proxies
- a realtime jittered polling bot for new original Trump posts with Gemini topic and escalation classification

## Current Study Window

- Start: `2025-01-20 08:17:00 America/New_York`
- End: `2026-04-18 21:07:00 America/New_York`

Studied market proxies:

- `SPY`
- `QQQ`
- `GLD`
- `SLV`
- `USO`
- `UNG`

## Core Findings

- Generic text sentiment is weak as a standalone signal.
- Timing regime matters much more than generic sentiment.
- Posts that arrive while the market is closed create substantially larger first-tradable-bar reactions than posts during live trading.
- Topic tagging is useful inside the delayed-open regime, especially for `tariffs_trade`, `war_geopolitics`, `immigration_border`, and `domestic_politics_attacks`.
- The strongest backtested setup so far is a short-horizon delayed-event fade after a large first-hour shock, especially in `QQQ` / `MNQ`.

The main human-readable summaries are:

- [STUDY_RESULTS_AND_NEXT_STEPS.md](STUDY_RESULTS_AND_NEXT_STEPS.md)
- [TOPIC_STUDY_V1.md](TOPIC_STUDY_V1.md)
- [STRATEGY_BACKTEST_V1.md](STRATEGY_BACKTEST_V1.md)
- [FUTURES_EXECUTION_MODEL_V1.md](FUTURES_EXECUTION_MODEL_V1.md)

## Environment

Use the repo-local virtual environment only:

- Python: `/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python`
- Pip: `/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/pip`

Installed packages are recorded in:

- [requirements.txt](requirements.txt)
- [packages.txt](packages.txt)

## Repo Layout

Code and docs:

- [truth_event_study.py](truth_event_study.py): scraper, TWS market fetcher, baseline analysis, topic analysis, strategy backtest, and futures execution study
- [AGENTS.md](AGENTS.md): repo-specific operating notes and command reference
- [realtime_post_bot/trump_post_signal_bot.py](realtime_post_bot/trump_post_signal_bot.py): live polling and alert bot
- [realtime_post_bot/README.md](realtime_post_bot/README.md): bot-specific behavior and caveats

Input data:

- [data/trump_truth_posts.csv](data/trump_truth_posts.csv): scraped Trump archive rows
- `data/market_5m/`: TWS `5-minute` bars

Validated baseline outputs:

- [outputs/event_level_market_reaction.csv](outputs/event_level_market_reaction.csv)
- [outputs/authored_bursts.csv](outputs/authored_bursts.csv)
- [outputs/weekday_hour_cluster.csv](outputs/weekday_hour_cluster.csv)
- [outputs/summary.json](outputs/summary.json)

Topic-study outputs:

- [outputs_topics_v1/topic_symbol_timing_summary.csv](outputs_topics_v1/topic_symbol_timing_summary.csv)
- [outputs_topics_v1/topic_tagging_rules.json](outputs_topics_v1/topic_tagging_rules.json)

Strategy-backtest outputs:

- [outputs_strategy_v1/strategy_timing_summary.csv](outputs_strategy_v1/strategy_timing_summary.csv)
- [outputs_strategy_v1/strategy_topic_symbol_summary.csv](outputs_strategy_v1/strategy_topic_symbol_summary.csv)
- [outputs_strategy_v1/strategy_trade_log.csv](outputs_strategy_v1/strategy_trade_log.csv)

Futures execution outputs:

- [outputs_strategy_v1/futures_execution_v1/execution_config_summary.csv](outputs_strategy_v1/futures_execution_v1/execution_config_summary.csv)
- [outputs_strategy_v1/futures_execution_v1/execution_recommended_configs.csv](outputs_strategy_v1/futures_execution_v1/execution_recommended_configs.csv)
- [outputs_strategy_v1/futures_execution_v1/futures_options_structure_map.csv](outputs_strategy_v1/futures_execution_v1/futures_options_structure_map.csv)

## Validated Event Definitions

These definitions should stay fixed unless intentionally replaced:

- Truth Social source: `trumpstruth.org`
- authored universe: Trump originals and quotes only
- reblogs excluded from the timed market study
- bursts defined by a `15-minute` inactivity gap
- market data from TWS in `5-minute` bars
- event impact anchored to the first tradable bar after the burst
- immediate vs delayed split:
  - `immediate`: `anchor_delay_minutes <= 5`
  - `delayed`: `anchor_delay_minutes > 5`

## Important Caveats

- `2,638` of `8,146` authored posts have empty extracted text in the archive.
- `16` bursts sit at the market-data boundaries and are not fully analyzable.
- Older delayed percentile values in `outputs_topics_v1` contain a known bug; use fresh reruns or the corrected `outputs_strategy_v1/reference_*` files for delayed slot-percentile work.
- The `MNQ` / `MES` / `CL` execution study still uses `QQQ` / `SPY` / `USO` ETF bars as execution proxies.
- The futures-options structure mapping is heuristic guidance, not a live options-chain backtest.
- The realtime bot’s `validation_watch` levels are static study-derived thresholds loaded from the current outputs at startup, not live-calculated trigger levels.

## Quick Start

Scrape archive rows:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py scrape-posts \
  --output data/trump_truth_posts.csv \
  --start-date 2025-01-20
```

Fetch market data from TWS:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py fetch-market \
  --output-dir data/market_5m \
  --symbols SPY QQQ GLD SLV USO UNG \
  --start-date-et 2025-01-20 \
  --end-date-et 2026-04-18 \
  --client-id 9301 \
  --duration '2 M' \
  --min-interval-seconds 10.5
```

Run the validated baseline analysis:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py analyze \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the deterministic topic study into a separate directory:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py analyze \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_topics_v1 \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the topic-aware strategy backtest:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py backtest-strategy \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_strategy_v1 \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the stricter futures execution study:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python truth_event_study.py backtest-futures-execution \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_strategy_v1/futures_execution_v1 \
  --symbols SPY QQQ USO
```

## Realtime Bot

Run the realtime post bot:

```bash
/Users/jblo/jblo_repos/TrumpSentimentStudy/.venv/bin/python \
  /Users/jblo/jblo_repos/TrumpSentimentStudy/realtime_post_bot/trump_post_signal_bot.py
```

What it does:

- polls the archive on a default `60-180` second jittered cadence
- looks for new original Trump posts
- uses Gemini to assign both topic and `ESCALATION` / `DE-ESCALATION` / `NEUTRAL`
- alerts only on historically actionable topic buckets
- checks whether TWS is reachable
- prints `validation_watch` thresholds for the mapped underlyings
- emits a `.` heartbeat after each successful poll

Bot requirements:

- `GOOGLE_API_KEY`

Bot notes:

- on startup it prints the latest post with usable text from the fetched page
- on macOS it speaks `Alert Escalation`, `Alert Deescalation`, or `Alert Neutral`
- on non-mac hosts the speech path is skipped
- `validation_watch` values come from the current strategy outputs and do not refresh continuously while the bot is running

See [realtime_post_bot/README.md](realtime_post_bot/README.md) for the bot-specific details.

## Reproducibility Notes

- Keep the validated baseline in `outputs/` intact unless you explicitly intend to replace it.
- Write new study variants into new directories rather than overwriting existing validated outputs.
- For delayed-event percentile work, prefer the corrected `outputs_strategy_v1/reference_*` files.

## Repository Status

- local Git repository initialized
- no remote configured yet
