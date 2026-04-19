# Topic Study V1

## Scope

This topic-study pass keeps the validated event-study mechanics unchanged:

- Study window: `2025-01-20 08:17:00 America/New_York` through `2026-04-18 21:07:00 America/New_York`
- Same authored-post universe: Trump originals and quotes only
- Same reblog exclusion from the timed market study
- Same `15-minute` burst definition
- Same TWS `5-minute` market bars
- Same event anchor: first tradable bar after the burst
- Same timing split:
  - `immediate`: `anchor_delay_minutes <= 5`
  - `delayed`: `anchor_delay_minutes > 5`

New outputs for this pass are in `outputs_topics_v1/`.

## Deterministic Tagging

Topic tagging is intentionally conservative:

- The classifier uses deterministic regex rules on `burst_text` only
- A burst gets a named topic only when exactly one topic family matches
- If zero topic families match, or more than one topic family matches, the burst is assigned to `other`
- The exact rulebook used here is in `outputs_topics_v1/topic_tagging_rules.json`

Named buckets in this pass:

- `tariffs_trade`
- `war_geopolitics`
- `oil_gas_energy`
- `fed_inflation_rates`
- `immigration_border`
- `domestic_politics_attacks`
- `other`

## Baseline Reconciliation

The new run reconciles to the validated baseline exactly on the core counts:

- Archive rows: `8,676`
- Authored Trump posts: `8,146`
- Empty-text authored posts: `2,638`
- Authored `15-minute` bursts: `3,272`
- Fully analyzable bursts: `3,256`
- Boundary-dropped bursts: `16`
- Timing split:
  - Immediate: `1,872`
  - Delayed: `1,384`
- Event rows per symbol remain unchanged:
  - `SPY`: `3,256`
  - `QQQ`: `3,256`
  - `GLD`: `3,256`
  - `SLV`: `3,256`
  - `USO`: `3,256`
  - `UNG`: `3,256`

## Topic Coverage And Sample Size

The conservative ruleset leaves most bursts in `other`, which is appropriate for a first deterministic pass but limits subgroup power.

- Only `826 / 3,272` bursts (`25.2%`) received a named topic
- `479` bursts (`14.6%`) matched more than one topic family and were forced into `other`
- `1,967` bursts (`60.1%`) had no named-topic match
- `534` bursts (`16.3%`) had completely empty extracted text

Burst counts by assigned topic:

| Topic | Bursts | Share | Immediate | Delayed |
| --- | --- | --- | --- | --- |
| tariffs_trade | 133 | 4.1% | 95 | 38 |
| war_geopolitics | 271 | 8.3% | 162 | 107 |
| oil_gas_energy | 31 | 0.9% | 24 | 7 |
| fed_inflation_rates | 58 | 1.8% | 46 | 12 |
| immigration_border | 127 | 3.9% | 84 | 43 |
| domestic_politics_attacks | 206 | 6.3% | 96 | 109 |
| other | 2446 | 74.8% | 1365 | 1068 |

`event_count` in the symbol tables below is the analyzable burst count for that topic/timing slice. It repeats across symbols because each burst is evaluated against each ETF.

## Main Findings

### 1. Timing regime still matters more than topic alone

Topic tagging adds signal, but it does not replace the original timing-regime result.

- Immediate `other` events are still ordinary:
  - mean absolute `60-minute` slot percentile ranges from `48.9` to `53.5`
- Delayed `other` events are still elevated:
  - mean absolute `60-minute` slot percentile ranges from `83.1` to `92.8`

Interpretation:

- The core validated result still holds: market-closed bursts dominate live-session bursts
- Topic slicing is most useful inside the delayed-open regime

### 2. The strongest named-topic slices are delayed-open volatility/reversion setups, not clean directional trades

The most actionable combinations are mostly delayed and mostly look like magnitude-plus-reversion effects, not simple “buy positive sentiment” or “short negative sentiment” rules.

Best delayed slices with at least `30` events:

| Topic | Symbol | Timing | N | Med 60m | Med Abs 60m | Mean Abs Pctl | Med 24h Peak Abs | Rev 5d | Med Rev Mins Trade | Med Rev Mins Event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| domestic_politics_attacks | GLD | delayed | 109 | 0.20% | 0.54% | 100.0 | 1.34% | 59.63% | 1540 | 2375 |
| immigration_border | SPY | delayed | 43 | 0.05% | 0.30% | 100.0 | 0.89% | 62.79% | 1860 | 3957 |
| tariffs_trade | GLD | delayed | 38 | 0.16% | 0.55% | 100.0 | 1.31% | 52.63% | 1442 | 2680 |
| tariffs_trade | SLV | delayed | 38 | 0.53% | 0.96% | 100.0 | 2.03% | 68.42% | 1440 | 2742 |
| tariffs_trade | USO | delayed | 38 | -0.20% | 0.79% | 100.0 | 1.93% | 76.32% | 1440 | 2183 |
| immigration_border | SLV | delayed | 43 | 0.52% | 0.92% | 98.4 | 2.37% | 55.81% | 1475 | 3464 |
| immigration_border | UNG | delayed | 43 | -0.49% | 2.08% | 98.4 | 5.35% | 44.19% | 2900 | 3640 |
| tariffs_trade | QQQ | delayed | 38 | 0.14% | 0.40% | 98.4 | 1.11% | 73.68% | 1615 | 2783 |
| tariffs_trade | SPY | delayed | 38 | 0.05% | 0.29% | 98.4 | 0.91% | 68.42% | 1665 | 2940 |
| war_geopolitics | UNG | delayed | 107 | 0.15% | 1.07% | 98.3 | 4.12% | 45.79% | 1650 | 3647 |
| immigration_border | GLD | delayed | 43 | 0.21% | 0.68% | 96.7 | 1.71% | 46.51% | 1442 | 2746 |
| immigration_border | USO | delayed | 43 | -0.20% | 0.76% | 96.7 | 1.98% | 67.44% | 1665 | 3994 |

Interpretation by topic:

- `tariffs_trade`, delayed:
  - Most consistent high-magnitude delayed topic across `GLD`, `SLV`, `SPY`, `QQQ`, and `USO`
  - Reversion is reasonably common in `QQQ`, `SLV`, `SPY`, and `USO` (`68%` to `76%`)
  - Direction is not stable across symbols, so this looks better as a volatility/reversion sleeve than a directional sleeve
- `immigration_border`, delayed:
  - Strong magnitude in `GLD`, `SLV`, `USO`, and especially `UNG`
  - Reversion is decent in `QQQ`, `SPY`, and `USO`, but weaker in `GLD` and `UNG`
  - `UNG` reacts the most in absolute size, but its `44%` five-day reversion rate makes it less clean as a mean-reversion trade
- `domestic_politics_attacks`, delayed:
  - Best combination of named-topic sample size and elevated delayed-open effect
  - `GLD`, `SLV`, and `QQQ` all screen well, with `109` events each and mean absolute percentile above `95`
  - `SPY` and `USO` are still elevated, but less dramatic
- `war_geopolitics`, delayed:
  - `UNG` is the clear standout
  - `GLD` and `QQQ` are secondary candidates
  - `USO` is less impressive than the topic label might suggest

### 3. Most immediate named-topic slices are not actionable

Once the first tradable bar is already available within `5` minutes, most topic buckets look ordinary relative to their weekday/time-of-day baselines.

Weakest immediate slices with at least `30` events:

| Topic | Symbol | N | Med 60m | Med Abs 60m | Mean Abs Pctl | Med 24h Peak Abs | Rev 5d | Med Rev Mins Trade | Med Rev Mins Event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| domestic_politics_attacks | GLD | 96 | 0.03% | 0.09% | 42.9 | 0.92% | 62.50% | 1635 | 1636 |
| fed_inflation_rates | USO | 46 | 0.03% | 0.20% | 47.6 | 1.64% | 67.39% | 1305 | 1305 |
| domestic_politics_attacks | SLV | 96 | 0.06% | 0.20% | 48.2 | 1.87% | 62.50% | 1898 | 1900 |
| domestic_politics_attacks | SPY | 96 | 0.02% | 0.09% | 48.6 | 0.78% | 60.42% | 2525 | 2526 |
| tariffs_trade | SLV | 95 | 0.00% | 0.24% | 49.5 | 1.79% | 65.26% | 1538 | 1538 |
| war_geopolitics | UNG | 162 | -0.03% | 0.38% | 49.6 | 2.86% | 66.05% | 2380 | 2383 |
| domestic_politics_attacks | QQQ | 96 | 0.04% | 0.13% | 49.6 | 1.10% | 63.54% | 2400 | 2401 |
| immigration_border | UNG | 84 | 0.03% | 0.34% | 49.8 | 2.68% | 79.76% | 1690 | 1691 |
| immigration_border | SLV | 84 | 0.11% | 0.21% | 49.8 | 1.28% | 76.19% | 1738 | 1740 |
| fed_inflation_rates | QQQ | 46 | -0.03% | 0.13% | 50.5 | 1.07% | 69.57% | 2762 | 2764 |
| war_geopolitics | GLD | 162 | 0.01% | 0.13% | 51.8 | 0.87% | 68.52% | 1465 | 1465 |
| domestic_politics_attacks | USO | 96 | -0.03% | 0.26% | 52.1 | 1.48% | 71.88% | 2245 | 2249 |

Interpretation:

- `domestic_politics_attacks`, immediate, is especially weak in `GLD`, `SPY`, `QQQ`, and `SLV`
- `war_geopolitics`, immediate, is basically baseline-like across most symbols
- `immigration_border`, immediate, also looks ordinary despite decent five-day reversion rates
- The immediate regime remains a poor place to hunt for a strong topic effect

### 4. Energy and Fed delayed slices are still exploratory, not validated

- `oil_gas_energy`, delayed: only `7` events
- `fed_inflation_rates`, delayed: only `12` events

Some of the metrics are extreme, but the sample sizes are too small for confident ranking. Those slices should be treated as provisional until the topic rules are expanded or the study window grows.

## Actionability Assessment

Most actionable now, subject to the sample sizes shown above:

- `tariffs_trade`, delayed:
  - Best broad cross-asset delayed topic
  - Strongest in `GLD`, `SLV`, `USO`
  - Also credible in `QQQ` and `SPY`
- `immigration_border`, delayed:
  - Strong absolute moves across all six symbols
  - Most useful in `SLV`, `GLD`, `USO`, and `SPY`
  - `UNG` is high-magnitude but lower-quality on reversion
- `domestic_politics_attacks`, delayed:
  - Best larger-sample named topic
  - `GLD`, `SLV`, and `QQQ` look most defensible
- `war_geopolitics`, delayed:
  - `UNG` is the main candidate
  - `GLD` and `QQQ` are weaker but still plausible

Not actionable now:

- Most immediate named-topic slices
- `oil_gas_energy`, delayed, because `n = 7`
- `fed_inflation_rates`, delayed, because `n = 12`

Important nuance:

- Topic does not produce a clean directional map
- Timing still dominates
- The more defensible extension is a topic-conditioned delayed-open volatility and reversion framework, not a naive directional sentiment strategy

## Full Delayed Named-Topic Matrix

Complete machine-readable table: `outputs_topics_v1/topic_symbol_timing_summary.csv`

| Topic | Symbol | N | Med 60m | Med Abs 60m | Mean Abs Pctl | Med 24h Peak Abs | Rev 5d | Med Rev Mins Trade | Med Rev Mins Event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tariffs_trade | GLD | 38 | 0.16% | 0.55% | 100.0 | 1.31% | 52.63% | 1442 | 2680 |
| tariffs_trade | QQQ | 38 | 0.14% | 0.40% | 98.4 | 1.11% | 73.68% | 1615 | 2783 |
| tariffs_trade | SLV | 38 | 0.53% | 0.96% | 100.0 | 2.03% | 68.42% | 1440 | 2742 |
| tariffs_trade | SPY | 38 | 0.05% | 0.29% | 98.4 | 0.91% | 68.42% | 1665 | 2940 |
| tariffs_trade | UNG | 38 | -0.32% | 1.26% | 75.4 | 3.49% | 60.53% | 630 | 2560 |
| tariffs_trade | USO | 38 | -0.20% | 0.79% | 100.0 | 1.93% | 76.32% | 1440 | 2183 |
| war_geopolitics | GLD | 107 | 0.03% | 0.63% | 90.3 | 1.56% | 56.07% | 1440 | 2842 |
| war_geopolitics | QQQ | 107 | 0.24% | 0.62% | 86.9 | 1.14% | 70.09% | 1615 | 3073 |
| war_geopolitics | SLV | 107 | 0.43% | 1.09% | 75.6 | 2.72% | 68.22% | 1440 | 2515 |
| war_geopolitics | SPY | 107 | 0.12% | 0.40% | 83.5 | 0.92% | 63.55% | 570 | 2794 |
| war_geopolitics | UNG | 107 | 0.15% | 1.07% | 98.3 | 4.12% | 45.79% | 1650 | 3647 |
| war_geopolitics | USO | 107 | 0.41% | 1.13% | 68.5 | 2.90% | 70.09% | 1805 | 2850 |
| oil_gas_energy | GLD | 7 | 0.32% | 0.47% | 87.1 | 0.85% | 71.43% | 1460 | 3565 |
| oil_gas_energy | QQQ | 7 | 0.52% | 0.73% | 96.0 | 1.01% | 42.86% | 1615 | 5255 |
| oil_gas_energy | SLV | 7 | 0.32% | 0.88% | 91.1 | 1.15% | 100.00% | 850 | 3955 |
| oil_gas_energy | SPY | 7 | 0.38% | 0.39% | 91.9 | 0.59% | 42.86% | 1615 | 5255 |
| oil_gas_energy | UNG | 7 | 0.18% | 0.74% | 24.2 | 2.56% | 85.71% | 422 | 3550 |
| oil_gas_energy | USO | 7 | -0.10% | 1.47% | 99.2 | 2.49% | 57.14% | 335 | 4184 |
| fed_inflation_rates | GLD | 12 | -0.23% | 0.68% | 86.1 | 1.77% | 41.67% | 4510 | 5586 |
| fed_inflation_rates | QQQ | 12 | -0.31% | 0.31% | 74.1 | 1.05% | 58.33% | 430 | 1894 |
| fed_inflation_rates | SLV | 12 | 0.19% | 2.04% | 93.4 | 3.92% | 25.00% | 905 | 1302 |
| fed_inflation_rates | SPY | 12 | -0.32% | 0.32% | 94.5 | 0.81% | 58.33% | 4680 | 5178 |
| fed_inflation_rates | UNG | 12 | 2.16% | 2.16% | 94.0 | 3.77% | 41.67% | 3210 | 3629 |
| fed_inflation_rates | USO | 12 | 0.78% | 0.78% | 79.0 | 2.51% | 66.67% | 1448 | 1968 |
| immigration_border | GLD | 43 | 0.21% | 0.68% | 96.7 | 1.71% | 46.51% | 1442 | 2746 |
| immigration_border | QQQ | 43 | -0.01% | 0.39% | 90.2 | 1.10% | 74.42% | 1712 | 3272 |
| immigration_border | SLV | 43 | 0.52% | 0.92% | 98.4 | 2.37% | 55.81% | 1475 | 3464 |
| immigration_border | SPY | 43 | 0.05% | 0.30% | 100.0 | 0.89% | 62.79% | 1860 | 3957 |
| immigration_border | UNG | 43 | -0.49% | 2.08% | 98.4 | 5.35% | 44.19% | 2900 | 3640 |
| immigration_border | USO | 43 | -0.20% | 0.76% | 96.7 | 1.98% | 67.44% | 1665 | 3994 |
| domestic_politics_attacks | GLD | 109 | 0.20% | 0.54% | 100.0 | 1.34% | 59.63% | 1540 | 2375 |
| domestic_politics_attacks | QQQ | 109 | 0.14% | 0.49% | 95.3 | 1.40% | 72.48% | 1785 | 3407 |
| domestic_politics_attacks | SLV | 109 | 0.29% | 0.88% | 95.5 | 2.37% | 72.48% | 1440 | 2333 |
| domestic_politics_attacks | SPY | 109 | 0.07% | 0.33% | 80.5 | 0.99% | 68.81% | 1920 | 2687 |
| domestic_politics_attacks | UNG | 109 | -0.69% | 1.47% | 92.7 | 4.47% | 55.05% | 1695 | 2642 |
| domestic_politics_attacks | USO | 109 | -0.08% | 0.76% | 86.7 | 1.87% | 63.30% | 1660 | 2709 |

## Full Immediate Named-Topic Matrix

| Topic | Symbol | N | Med 60m | Med Abs 60m | Mean Abs Pctl | Med 24h Peak Abs | Rev 5d | Med Rev Mins Trade | Med Rev Mins Event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tariffs_trade | GLD | 95 | 0.04% | 0.15% | 56.0 | 0.91% | 64.21% | 1485 | 1487 |
| tariffs_trade | QQQ | 95 | -0.05% | 0.20% | 60.1 | 1.08% | 68.42% | 2410 | 2410 |
| tariffs_trade | SLV | 95 | 0.00% | 0.24% | 49.5 | 1.79% | 65.26% | 1538 | 1538 |
| tariffs_trade | SPY | 95 | -0.04% | 0.16% | 61.1 | 0.78% | 67.37% | 2415 | 2416 |
| tariffs_trade | UNG | 95 | 0.00% | 0.46% | 54.6 | 3.38% | 81.05% | 2555 | 2555 |
| tariffs_trade | USO | 95 | -0.01% | 0.30% | 54.8 | 1.52% | 63.16% | 1745 | 1747 |
| war_geopolitics | GLD | 162 | 0.01% | 0.13% | 51.8 | 0.87% | 68.52% | 1465 | 1465 |
| war_geopolitics | QQQ | 162 | 0.00% | 0.15% | 52.9 | 1.01% | 66.67% | 1582 | 1584 |
| war_geopolitics | SLV | 162 | -0.03% | 0.30% | 53.0 | 1.91% | 67.28% | 1880 | 1883 |
| war_geopolitics | SPY | 162 | 0.01% | 0.13% | 54.5 | 0.77% | 66.67% | 1460 | 1460 |
| war_geopolitics | UNG | 162 | -0.03% | 0.38% | 49.6 | 2.86% | 66.05% | 2380 | 2383 |
| war_geopolitics | USO | 162 | 0.00% | 0.35% | 58.2 | 2.03% | 64.81% | 1460 | 1461 |
| oil_gas_energy | GLD | 24 | -0.00% | 0.10% | 43.6 | 1.04% | 45.83% | 1355 | 1359 |
| oil_gas_energy | QQQ | 24 | -0.00% | 0.10% | 52.8 | 1.31% | 66.67% | 1665 | 1668 |
| oil_gas_energy | SLV | 24 | 0.08% | 0.15% | 49.4 | 2.26% | 58.33% | 2168 | 2168 |
| oil_gas_energy | SPY | 24 | -0.02% | 0.14% | 60.3 | 0.81% | 66.67% | 4185 | 4186 |
| oil_gas_energy | UNG | 24 | -0.20% | 0.51% | 61.2 | 3.93% | 66.67% | 1420 | 1423 |
| oil_gas_energy | USO | 24 | 0.01% | 0.39% | 60.0 | 1.66% | 62.50% | 1430 | 1434 |
| fed_inflation_rates | GLD | 46 | 0.01% | 0.17% | 53.4 | 1.21% | 58.70% | 1415 | 1419 |
| fed_inflation_rates | QQQ | 46 | -0.03% | 0.13% | 50.5 | 1.07% | 69.57% | 2762 | 2764 |
| fed_inflation_rates | SLV | 46 | -0.03% | 0.40% | 53.7 | 1.90% | 47.83% | 1275 | 1276 |
| fed_inflation_rates | SPY | 46 | -0.02% | 0.11% | 52.5 | 0.81% | 76.09% | 2640 | 2641 |
| fed_inflation_rates | UNG | 46 | -0.12% | 0.52% | 58.5 | 3.10% | 73.91% | 1532 | 1536 |
| fed_inflation_rates | USO | 46 | 0.03% | 0.20% | 47.6 | 1.64% | 67.39% | 1305 | 1305 |
| immigration_border | GLD | 84 | 0.04% | 0.16% | 54.6 | 1.04% | 71.43% | 1685 | 1686 |
| immigration_border | QQQ | 84 | 0.07% | 0.14% | 55.3 | 1.01% | 69.05% | 2400 | 2404 |
| immigration_border | SLV | 84 | 0.11% | 0.21% | 49.8 | 1.28% | 76.19% | 1738 | 1740 |
| immigration_border | SPY | 84 | 0.05% | 0.13% | 54.5 | 0.81% | 67.86% | 1555 | 1557 |
| immigration_border | UNG | 84 | 0.03% | 0.34% | 49.8 | 2.68% | 79.76% | 1690 | 1691 |
| immigration_border | USO | 84 | 0.06% | 0.22% | 52.1 | 1.66% | 72.62% | 2620 | 2621 |
| domestic_politics_attacks | GLD | 96 | 0.03% | 0.09% | 42.9 | 0.92% | 62.50% | 1635 | 1636 |
| domestic_politics_attacks | QQQ | 96 | 0.04% | 0.13% | 49.6 | 1.10% | 63.54% | 2400 | 2401 |
| domestic_politics_attacks | SLV | 96 | 0.06% | 0.20% | 48.2 | 1.87% | 62.50% | 1898 | 1900 |
| domestic_politics_attacks | SPY | 96 | 0.02% | 0.09% | 48.6 | 0.78% | 60.42% | 2525 | 2526 |
| domestic_politics_attacks | UNG | 96 | -0.08% | 0.46% | 52.5 | 2.69% | 75.00% | 1522 | 1524 |
| domestic_politics_attacks | USO | 96 | -0.03% | 0.26% | 52.1 | 1.48% | 71.88% | 2245 | 2249 |

## `Other` Bucket Reference

This is useful for context because the delayed `other` bucket is still strong.

| Topic | Symbol | Timing | N | Med 60m | Med Abs 60m | Mean Abs Pctl | Med 24h Peak Abs | Rev 5d | Med Rev Mins Trade | Med Rev Mins Event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| other | GLD | immediate | 1365 | 0.02% | 0.13% | 49.7 | 1.01% | 64.32% | 1992 | 1996 |
| other | QQQ | immediate | 1365 | 0.01% | 0.12% | 50.3 | 0.97% | 70.18% | 1698 | 1701 |
| other | SLV | immediate | 1365 | 0.02% | 0.20% | 48.9 | 1.60% | 63.96% | 2175 | 2178 |
| other | SPY | immediate | 1365 | 0.01% | 0.09% | 50.9 | 0.73% | 69.23% | 1580 | 1583 |
| other | UNG | immediate | 1365 | 0.00% | 0.42% | 53.5 | 2.88% | 70.77% | 1625 | 1626 |
| other | USO | immediate | 1365 | 0.00% | 0.23% | 51.5 | 1.62% | 67.47% | 1905 | 1905 |
| other | GLD | delayed | 1068 | 0.20% | 0.57% | 92.8 | 1.35% | 56.37% | 1450 | 2712 |
| other | QQQ | delayed | 1068 | 0.01% | 0.47% | 87.0 | 1.24% | 73.69% | 1785 | 3251 |
| other | SLV | delayed | 1068 | 0.43% | 1.00% | 91.8 | 2.15% | 61.99% | 1445 | 2954 |
| other | SPY | delayed | 1068 | 0.02% | 0.31% | 83.5 | 0.92% | 71.44% | 1860 | 3271 |
| other | UNG | delayed | 1068 | -0.22% | 1.40% | 88.1 | 4.09% | 52.90% | 1650 | 2849 |
| other | USO | delayed | 1068 | 0.07% | 0.69% | 83.1 | 2.02% | 70.51% | 1595 | 2872 |

## New Caveats

- Topic tagging uses `burst_text` only, so empty extracted text still means no topic evidence
- The conservative unique-match rule intentionally pushes mixed-theme bursts into `other`
- As a result, `other` is large and still contains many economically important bursts
- `oil_gas_energy` and `fed_inflation_rates` delayed slices are underpowered
- Because topic direction is not stable across symbols, these results are more credible as regime/magnitude inputs than as standalone directional signals
