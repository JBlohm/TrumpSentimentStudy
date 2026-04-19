# Realtime Post Bot

This bot polls the public `trumpstruth.org` archive on a randomized `1-3 minute` cadence, looks for new original `@realDonaldTrump` posts, classifies them into the study topic buckets, and emits an alert only for categories that cleared the study's delayed-event filters.

## What It Does

- checks for new original Trump posts on a jittered cadence of `60` seconds plus a random `0-120` second delay
- on startup, prints the latest original Trump post with usable text from the current archive page
- uses Gemini 3 over the official REST `generateContent` endpoint with `GOOGLE_API_KEY`
- asks Gemini for both a topic bucket and an `ESCALATION` / `DE-ESCALATION` / `NEUTRAL` situation assessment with separate confidence levels
- keeps the study's exact topic buckets:
  - `tariffs_trade`
  - `war_geopolitics`
  - `oil_gas_energy`
  - `fed_inflation_rates`
  - `immigration_border`
  - `domestic_politics_attacks`
  - `other`
- falls back to the repo's deterministic study rules if the Gemini call fails
- emits the alert path only when the final category is one of the categories that looked actionable in the existing delayed-event study
- the alert path is a single terminal bell plus, on macOS only, a spoken phrase via the native `say` command:
  - `Alert Escalation`
  - `Alert Deescalation`
  - `Alert Neutral`
- if TWS is reachable, prints the approximate `60-minute` validation move required in the relevant underlying(s)
- appends an action log to `realtime_post_bot/trump_post_signal_bot.log`

## Current Actionable Categories

Derived from `outputs_strategy_v1/strategy_topic_symbol_summary.csv` using delayed `fade_credit_24h`, `p80`, `n >= 30`, and positive mean `R`:

- `tariffs_trade`
- `war_geopolitics`
- `immigration_border`
- `domestic_politics_attacks`

## Run

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python \
  /Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/trump_post_signal_bot.py
```

One-shot test:

```bash
/Users/jblo/jblo_repos/TrumpSentimentIndex/.venv/bin/python \
  /Users/jblo/jblo_repos/TrumpSentimentIndex/realtime_post_bot/trump_post_signal_bot.py \
  --once
```

## Required Environment

- `GOOGLE_API_KEY`

Optional overrides:

- `--tws-host`
- `--tws-port`
- `--tws-client-id`
- `--gemini-model`
- `--log-file`
- `--state-file`
- `--per-page`
- `--poll-seconds`
- `--max-jitter-seconds`

## Behavior Notes

- first run bootstraps from the current latest seen post and does not replay old posts
- every process start prints a startup summary for the latest original Trump post with usable text
- if that startup preview is already in an actionable category, it also emits the same alert path as a new actionable post
- stdout includes both the Gemini topic classification and the Gemini escalation assessment with separate confidences
- posts with no usable body/card/link text are suppressed from stdout
- posts with no usable text are still logged and still advance the seen-post state
- if multiple new original Trump posts appear within one polling interval, the bot processes all unseen posts in chronological order within the fetched page
- every successful poll writes a single `.` to stdout without a newline as a heartbeat
- the default sleep window after each poll is `60-180` seconds
- the bot persists `last_seen_status_id` in `realtime_post_bot/bot_state.json`
- the bot appends a timestamped action log to `realtime_post_bot/trump_post_signal_bot.log`
- spoken macOS output is derived from the Gemini escalation label and is ignored on non-mac hosts
- internet/archive/Gemini/TWS failures do not terminate the bot; the failure is logged and the bot retries on the next poll cycle
- the current fetch depth is the latest `40` original posts per poll by default, so a burst larger than that between polls could exceed the fetch window
- the `60-minute` validation move is an approximate study-derived watch level, not a live chain-level trade trigger
- the futures/options mapping still inherits the study caveat: `QQQ`, `SPY`, and `USO` are proxies for `MNQ`, `MES`, and `CL`

## `validation_watch` Notes

- `validation_watch=` is a trader checklist, not a direct trade signal
- it appears only for topic buckets that passed the delayed-event strategy filters in the study
- each printed percentage is the historical `90th percentile` of absolute `60-minute` return for that topic and proxy symbol in the current study outputs
- the watch lines are built from `outputs_strategy_v1/strategy_topic_symbol_summary.csv`, `outputs_strategy_v1/reference_event_level_market_reaction.csv`, and `outputs_strategy_v1/futures_execution_v1/execution_recommended_configs.csv`
- the bot loads those files once at startup, so the percentages do not update continuously while the bot is running
- to change them, extend the study data, rerun the strategy/execution study, and restart the bot or point it at a newer outputs directory with `--outputs-root`
