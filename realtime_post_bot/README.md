# Realtime Post Bot

This bot polls the public `trumpstruth.org` archive every `5 minutes`, looks for new original `@realDonaldTrump` posts, classifies them into the study topic buckets, and emits a bell alert only for categories that cleared the study's delayed-event filters.

## What It Does

- checks for new original Trump posts every `300` seconds
- uses Gemini 3 over the official REST `generateContent` endpoint with `GOOGLE_API_KEY`
- keeps the study's exact topic buckets:
  - `tariffs_trade`
  - `war_geopolitics`
  - `oil_gas_energy`
  - `fed_inflation_rates`
  - `immigration_border`
  - `domestic_politics_attacks`
  - `other`
- falls back to the repo's deterministic study rules if the Gemini call fails
- rings a single terminal bell only when the final category is one of the categories that looked actionable in the existing delayed-event study
- if TWS is reachable, prints the approximate `60-minute` validation move required in the relevant underlying(s)

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
- `--state-file`

## Behavior Notes

- first run bootstraps from the current latest seen post and does not replay old posts
- every process start prints a startup summary for the latest original Trump post with usable text
- posts with no usable body/card/link text are suppressed from stdout
- every successful poll writes a single `.` to stdout without a newline as a heartbeat
- the bot persists `last_seen_status_id` in `realtime_post_bot/bot_state.json`
- the bot appends a timestamped action log to `realtime_post_bot/trump_post_signal_bot.log`
- the `60-minute` validation move is an approximate study-derived watch level, not a live chain-level trade trigger
- the futures/options mapping still inherits the study caveat: `QQQ`, `SPY`, and `USO` are proxies for `MNQ`, `MES`, and `CL`
