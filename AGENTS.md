# TrumpSentimentIndex Agent Notes

## Purpose

This repo contains a validated event study on Donald Trump Truth Social posting activity during his second term and the corresponding market reaction in:

- `SPY`
- `QQQ`
- `GLD`
- `SLV`
- `USO`
- `UNG`

The current study window is:

- Start: `2025-01-20 08:17:00 America/New_York`
- End: `2026-04-18 21:07:00 America/New_York`

## Environment

Always use the repo-local virtual environment:

- Python: `/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python`
- Pip: `/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/pip`

Installed dependencies are recorded in [requirements.txt](/Users/jblo/jblo_repos/TrumpSentimentIndex/requirements.txt).

Do not use the old scratch `.deps` directory from the projectless workspace. This repo is now the working copy.

## Repo Layout

- [truth_event_study.py](/Users/jblo/jblo_repos/TrumpSentimentIndex/truth_event_study.py): scraper, IBKR fetcher, and analysis pipeline
- [data/trump_truth_posts.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/data/trump_truth_posts.csv): scraped archive rows
- [data/market_5m](/Users/jblo/jblo_repos/TrumpSentimentIndex/data/market_5m): 5-minute IBKR market bars
- [outputs/event_level_market_reaction.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs/event_level_market_reaction.csv): event-level market reactions
- [outputs/authored_bursts.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs/authored_bursts.csv): 15-minute burst definitions
- [outputs/weekday_hour_cluster.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs/weekday_hour_cluster.csv): timing cluster summary
- [outputs/summary.json](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs/summary.json): high-level summary stats
- [outputs_topics_v1/topic_symbol_timing_summary.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_topics_v1/topic_symbol_timing_summary.csv): topic x symbol x timing regime summary table
- [outputs_topics_v1/topic_tagging_rules.json](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_topics_v1/topic_tagging_rules.json): deterministic topic-tagging rulebook used for the topic study
- [TOPIC_STUDY_V1.md](/Users/jblo/jblo_repos/TrumpSentimentIndex/TOPIC_STUDY_V1.md): human-readable topic-study results and caveats
- [outputs_strategy_v1/reference_event_level_market_reaction.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/reference_event_level_market_reaction.csv): corrected reference event-study output used by the strategy backtest
- [outputs_strategy_v1/strategy_timing_summary.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/strategy_timing_summary.csv): strategy x timing x threshold summary
- [outputs_strategy_v1/strategy_topic_symbol_summary.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/strategy_topic_symbol_summary.csv): strategy x topic x symbol x timing summary
- [outputs_strategy_v1/strategy_trade_log.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/strategy_trade_log.csv): event-level strategy proxy trade log
- [STRATEGY_BACKTEST_V1.md](/Users/jblo/jblo_repos/TrumpSentimentIndex/STRATEGY_BACKTEST_V1.md): human-readable strategy backtest findings and caveats
- [outputs_strategy_v1/futures_execution_v1/execution_config_summary.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/futures_execution_v1/execution_config_summary.csv): stricter delayed-event execution summary for `MNQ` / `MES` / `CL` proxy trades
- [outputs_strategy_v1/futures_execution_v1/futures_options_structure_map.csv](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_strategy_v1/futures_execution_v1/futures_options_structure_map.csv): heuristic futures-options structure mapping tied to the recommended execution configs
- [FUTURES_EXECUTION_MODEL_V1.md](/Users/jblo/jblo_repos/TrumpSentimentIndex/FUTURES_EXECUTION_MODEL_V1.md): human-readable stricter execution-model findings and caveats
- [realtime_post_bot/trump_post_signal_bot.py](/Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/trump_post_signal_bot.py): jittered polling bot for new original Trump posts with Gemini topic tagging and study-derived alert thresholds
- [realtime_post_bot/README.md](/Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/README.md): run notes and caveats for the realtime post bot
- [realtime_post_bot/trump_post_signal_bot.log](/Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/trump_post_signal_bot.log): append-only runtime logfile for bot polling, suppression, classification, TWS checks, and errors
- [outputs_test](/Users/jblo/jblo_repos/TrumpSentimentIndex/outputs_test): earlier SPY/QQQ validation run
- [STUDY_RESULTS_AND_NEXT_STEPS.md](/Users/jblo/jblo_repos/TrumpSentimentIndex/STUDY_RESULTS_AND_NEXT_STEPS.md): human-readable handoff

## Validated Study Definitions

- Truth Social source: `trumpstruth.org`
- Archive date filters are unreliable in the HTML listing
- The scraper therefore seeds pagination using a base64 cursor at the requested start date
- Authored post universe includes only Trump originals and quotes
- Reblogs are excluded from the timed event study because the archive does not expose reliable retruth action timestamps
- Bursts are defined by a `15-minute` inactivity gap
- Sentiment is computed from post text only using `vaderSentiment`
- Market data is pulled from TWS API in `5-minute` bars
- Event impact is measured from the first tradable bar after the burst, not from the wall-clock post timestamp
- Reversion is measured after the event's `24h` peak move, using the first cross back through the pre-event baseline, capped at `5 days`

## Important Data Caveats

- `2638` of `8146` authored posts have empty extracted text in the archive, so text-only sentiment is incomplete by construction
- `16` of `3272` bursts were outside the fully analyzable market window because they sat at the very beginning or end of the sampled bar history
- The TWS historical bar timestamps observed in this setup were in `Europe/Berlin`; the script converts them to `America/New_York` before analysis
- Overnight and weekend posts create delayed first-trade reactions; those should be analyzed separately from near-immediate tradable events
- Older topic-study outputs in `outputs_topics_v1` contain a delayed-event slot-percentile bug: delayed events were compared to the rounded event timestamp instead of the first tradable bar. The corrected logic now uses `anchor_bar_ts_et`; use fresh reruns or `outputs_strategy_v1/reference_*` for corrected delayed slot percentiles
- The stricter `MNQ` / `MES` / `CL` execution model still uses `QQQ` / `SPY` / `USO` ETF bars as execution proxies; it is not a true futures-tick or options-chain backtest
- The futures-options structure map is heuristic sizing guidance tied to the backtest logic; it is not validated with live IV, bid/ask, slippage, or assignment data
- The realtime post bot uses Gemini 3 for live category assignment but still inherits the archive-text caveat: if `trumpstruth.org` exposes no usable body or card text for a new post, the bot can only classify it as `other`
- The realtime post bot also asks Gemini for a live `ESCALATION` / `DE-ESCALATION` / `NEUTRAL` assessment with its own confidence; if Gemini is unavailable, that escalation field falls back conservatively to `NEUTRAL` with `0.0` confidence
- The realtime bot's `60-minute` validation levels are study-derived watch thresholds, not live market-data signals or broker-tested execution triggers
- The realtime bot suppresses no-text posts from stdout, but still records them in the logfile and advances its seen-post state
- The realtime bot speaks a macOS-only phrase via the native `say` command: `Alert Escalation`, `Alert Deescalation`, or `Alert Neutral`; on non-mac hosts that speech path is skipped

## Commands

Use the repo-local environment explicitly.

Scrape posts from a cursor-seeded start date:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py scrape-posts \
  --output data/trump_truth_posts.csv \
  --start-date 2025-01-20
```

Fetch market data from TWS:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py fetch-market \
  --output-dir data/market_5m \
  --symbols SPY QQQ GLD SLV USO UNG \
  --start-date-et 2025-01-20 \
  --end-date-et 2026-04-18 \
  --client-id 9301 \
  --duration '2 M' \
  --min-interval-seconds 10.5
```

Run the analysis:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py analyze \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the deterministic topic study without overwriting the validated baseline:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py analyze \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_topics_v1 \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the topic-aware strategy backtest without overwriting the validated baseline:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py backtest-strategy \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_strategy_v1 \
  --symbols SPY QQQ GLD SLV USO UNG
```

Run the stricter delayed-event `MNQ` / `MES` / `CL` execution study into its own subfolder:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python truth_event_study.py backtest-futures-execution \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs_strategy_v1/futures_execution_v1 \
  --symbols SPY QQQ USO
```

Run the realtime Trump post bot:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python \
  /Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/trump_post_signal_bot.py
```

## How To Continue

- Prefer working from `outputs/event_level_market_reaction.csv` for downstream modeling
- Keep immediate events (`anchor_delay_minutes <= 5`) separate from delayed-open events
- Next likely improvement is topic tagging, not more generic sentiment engineering
- Highest-value topic buckets to add first:
  - tariffs and trade
  - war and geopolitics
  - oil and gas
  - Fed, inflation, and rates
- The first deterministic topic pass now writes its own outputs to `outputs_topics_v1`
- Use `outputs_topics_v1/topic_symbol_timing_summary.csv` for downstream topic x symbol x timing work
- Topic tags are conservative by design: a burst gets a named topic only when exactly one topic family matches the burst text, otherwise it stays in `other`
- For corrected delayed slot-percentile work, prefer the fresh reference outputs in `outputs_strategy_v1/reference_*` or rerun `analyze` into a new directory
- The strategy backtest uses a `60-minute` confirmation entry, threshold buckets at `all`, `p80`, and `p90`, and fixed `24h` / `72h` exits
- The stricter futures execution model is delayed-only, tests `30m` / `60m` / `90m` entries, `0.75x` / `1.0x` shock-unit stops, baseline-cross profit targets, and `12h` / `24h` time stops
- Use `outputs_strategy_v1/futures_execution_v1/execution_recommended_configs.csv` for the recommended `MNQ` / `MES` / `CL` templates and `futures_options_structure_map.csv` for the matching heuristic options structures
- The realtime bot polls on a default jittered `60-180` second cadence, uses `GOOGLE_API_KEY`, prints the latest post with usable text on startup, emits the normal actionable alert path for an actionable startup preview, prints both Gemini topic and Gemini escalation assessments with separate confidences, suppresses no-text posts from stdout, emits a `.` heartbeat after each successful poll cycle, bootstraps without replaying old posts on first run, persists `last_seen_status_id` in `realtime_post_bot/bot_state.json`, appends detailed actions to `realtime_post_bot/trump_post_signal_bot.log`, and on macOS speaks `Alert Escalation`, `Alert Deescalation`, or `Alert Neutral` for actionable posts
- If you add a new study variant, write outputs to a new directory rather than overwriting the current validated baseline unless the user asks

## Repo State

- This directory is now a local Git repository
- No remote is configured yet
