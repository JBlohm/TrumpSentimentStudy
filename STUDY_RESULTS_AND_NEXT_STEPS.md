# Trump Truth Social Event Study

## Scope

This study covers Donald Trump Truth Social activity from the start of his second term:

- Start: `2025-01-20 08:17:00 America/New_York`
- End: `2026-04-18 21:07:00 America/New_York`

Data sources used:

- Truth Social archive: `trumpstruth.org`
- Market data: TWS API, 5-minute bars, all sessions

Studied markets:

- `SPY`
- `QQQ`
- `GLD`
- `SLV`
- `USO`
- `UNG`

## Validated Universe

- Archive rows scraped: `8,676`
- Authored Trump posts used: `8,146`
- Reblogs excluded from timed study: `342`
- Authored 15-minute bursts: `3,272`
- Fully analyzable bursts: `3,256`

Cross-check:

- The archive's own stats page for `2025-01-20` through `2026-04-18` reports:
  - `7,552` originals
  - `594` quotes
  - `8,146` authored posts total

That exactly matches the deduped authored universe used here.

## Methodology

- Reblogs were excluded because the archive does not expose reliable retruth action timestamps
- Bursts are defined by a `15-minute` gap
- Sentiment is text-only and computed with `vaderSentiment`
- Market impact is measured from the first tradable 5-minute bar after the burst
- Reversion is measured after the event's 24-hour peak move, using the first cross back through the pre-event baseline, capped at 5 days

Important caveats:

- `2,638` authored posts have empty extracted text, so generic text sentiment is incomplete
- `16` bursts were dropped because they sat at the boundaries of the market sample
- Near-immediate tradable events and delayed-open events behave differently and should not be pooled casually

## Timing Structure

Burst counts by market session:

- `post_rth`: `1,417`
- `rth`: `1,184`
- `pre_rth`: `671`

Immediate vs delayed first-trade split:

- Immediate: `1,872` bursts, median anchor delay `2.0` minutes
- Delayed: `1,384` bursts, median anchor delay `844.5` minutes

Most active weekdays by burst count:

- Tuesday: `516`
- Friday: `504`
- Thursday: `498`
- Monday: `496`
- Wednesday: `494`

Most active hours by burst count:

- `18:00 ET`: `232`
- `09:00 ET`: `218`
- `16:00 ET`: `198`
- `10:00 ET`: `195`
- `17:00 ET`: `195`

Highest-volume authored days:

- `2025-12-01`: `168` authored posts
- `2025-03-10`: `140`
- `2025-12-25`: `126`
- `2026-01-23`: `110`
- `2026-01-05`: `97`

## Main Findings

### 1. Generic text sentiment is weak as a standalone signal

For immediate-tradable events, the correlation between burst sentiment and 60-minute return was small:

- `SPY`: `0.038`
- `QQQ`: `0.044`
- `GLD`: `0.006`
- `SLV`: `0.014`
- `USO`: `-0.038`
- `UNG`: `0.004`

Interpretation:

- Timing regime matters more than generic sentiment tone
- The missing-text rate is too high for a pure text-sentiment model to be trusted as the main signal

### 2. Delayed-open events matter much more than live-session posts

Median absolute 60-minute move after first trade:

| Symbol | Immediate | Delayed |
| --- | ---: | ---: |
| SPY | 0.099% | 0.336% |
| QQQ | 0.127% | 0.489% |
| GLD | 0.130% | 0.588% |
| SLV | 0.205% | 0.999% |
| USO | 0.242% | 0.720% |
| UNG | 0.418% | 1.371% |

Mean absolute 60-minute move percentile versus matched weekday/time-of-day baseline:

| Symbol | Immediate | Delayed |
| --- | ---: | ---: |
| SPY | 0.519 | 0.845 |
| QQQ | 0.512 | 0.874 |
| GLD | 0.501 | 0.929 |
| SLV | 0.494 | 0.918 |
| USO | 0.523 | 0.836 |
| UNG | 0.532 | 0.870 |

Interpretation:

- Immediate events are usually ordinary to mildly elevated
- Delayed-open events are substantially larger than normal
- The strongest delayed-open sensitivity is in `GLD`, `SLV`, `USO`, and `UNG`

### 3. Reversion happens often, but not quickly

Median reversion time after first trade:

| Symbol | Median Minutes | Approx. Hours |
| --- | ---: | ---: |
| GLD | 1540.0 | 25.7 |
| SLV | 1545.0 | 25.8 |
| USO | 1610.0 | 26.8 |
| UNG | 1650.0 | 27.5 |
| QQQ | 1770.0 | 29.5 |
| SPY | 1780.0 | 29.7 |

5-day reversion rate:

| Symbol | Rate |
| --- | ---: |
| GLD | 60.96% |
| QQQ | 70.92% |
| SLV | 63.82% |
| SPY | 69.16% |
| UNG | 63.45% |
| USO | 68.46% |

Interpretation:

- Reversion is common
- It is usually not a same-session trade
- The typical path is roughly one to one-and-a-quarter days after first trade

## Actionable Interpretation

The strongest validated takeaway is:

- Do not treat this as a pure text-sentiment problem
- Treat it as a timing and regime problem

More specifically:

- Immediate posts during tradable hours produce modest, mostly ordinary 60-minute reactions
- Posts that hit while the market is closed produce meaningfully larger next-tradable-bar moves
- Those delayed-open reactions frequently revert, but usually over roughly `26-30` hours rather than minutes

That means the most promising continuation is not:

- "buy positive sentiment"
- "short negative sentiment"

The more defensible continuation is:

- identify market-closed bursts
- classify them by topic
- measure open-gap reaction and 1-2 day reversion by topic and asset

## Files To Use

- [truth_event_study.py](truth_event_study.py)
- [outputs/event_level_market_reaction.csv](outputs/event_level_market_reaction.csv)
- [outputs/authored_bursts.csv](outputs/authored_bursts.csv)
- [outputs/weekday_hour_cluster.csv](outputs/weekday_hour_cluster.csv)
- [outputs/summary.json](outputs/summary.json)

## Recommended Next Steps

### 1. Add topic tagging

The next study should classify bursts into explicit topics, at minimum:

- tariffs and trade
- Iran, Russia, war, military action
- oil and gas
- Fed, inflation, rates
- domestic political attacks
- immigration and border

This is the highest-value extension because the current generic sentiment factor is weak.

### 2. Split the analysis by timing regime

Run all downstream stats separately for:

- immediate events: `anchor_delay_minutes <= 5`
- delayed-open events: `anchor_delay_minutes > 5`

That split is already strongly justified by the current results.

### 3. Add market-open gap metrics

For delayed-open events, add:

- first bar open gap versus prior close
- first 30 minutes after open
- same-day close
- next-day close

The current 60-minute horizon is useful, but open-gap decomposition is likely better.

### 4. Add significance testing at the strategy slice level

The current baseline percentile framework is useful, but the next pass should add:

- permutation tests by timing bucket
- bootstrapped confidence intervals by topic and timing regime
- sample-size thresholds before reporting a subgroup as actionable

### 5. Preserve the validated baseline

Do not overwrite the current `outputs/` directory casually.
Create new output directories for:

- topic-tagged runs
- immediate-only runs
- delayed-open runs
- asset-specific extensions

## Rerun Commands

Use the repo-local environment:
Replace `<REPO_ROOT>` below with your local checkout path, for example `/Users/<your-username>/path/to/TrumpSentimentStudy`.

```bash
<REPO_ROOT>/.venv/bin/python truth_event_study.py scrape-posts \
  --output data/trump_truth_posts.csv \
  --start-date 2025-01-20
```

```bash
<REPO_ROOT>/.venv/bin/python truth_event_study.py fetch-market \
  --output-dir data/market_5m \
  --symbols SPY QQQ GLD SLV USO UNG \
  --start-date-et 2025-01-20 \
  --end-date-et 2026-04-18 \
  --client-id 9301 \
  --duration '2 M' \
  --min-interval-seconds 10.5
```

```bash
<REPO_ROOT>/.venv/bin/python truth_event_study.py analyze \
  --posts-csv data/trump_truth_posts.csv \
  --market-dir data/market_5m \
  --output-dir outputs \
  --symbols SPY QQQ GLD SLV USO UNG
```
