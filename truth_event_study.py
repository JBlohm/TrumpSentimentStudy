#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from zoneinfo import ZoneInfo


ARCHIVE_ROOT = "https://trumpstruth.org"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TZ_ET = ZoneInfo("America/New_York")
TZ_BERLIN = ZoneInfo("Europe/Berlin")
DEFAULT_SYMBOLS = ["SPY", "QQQ", "GLD", "SLV", "USO", "UNG"]
RTH_OPEN_ET = (9, 30)
RTH_CLOSE_ET = (16, 0)
TOPIC_OTHER = "other"
TOPIC_RULE_VERSION = "strict_regex_unique_match_v1"
TOPIC_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "tariffs_trade": (
        ("tariff", r"\btariff(?:s)?\b"),
        ("trade_deal", r"\btrade deal(?:s)?\b"),
        ("trade_deficit", r"\btrade deficit(?:s)?\b"),
        ("trade_barrier", r"\btrade barrier(?:s)?\b"),
        ("trade_war", r"\btrade war\b"),
        ("international_trade", r"\binternational trade\b"),
        ("reciprocal_tariffs", r"\breciprocal tariff(?:s)?\b"),
        ("reciprocal_trade", r"\breciprocal trade\b"),
        ("customs", r"\bcustoms\b"),
        ("duties", r"\bdut(?:y|ies)\b"),
        ("imports_from", r"\bimports?\s+from\b"),
    ),
    "war_geopolitics": (
        ("ukraine", r"\brukrain(?:e|ian)\b"),
        ("russia", r"\brussia(?:n)?\b"),
        ("putin", r"\bputin\b"),
        ("zelensky", r"\bzelensky(?:y)?\b"),
        ("iran", r"\biran(?:ian)?\b"),
        ("israel", r"\bisrael(?:i)?\b"),
        ("gaza", r"\bgaza\b"),
        ("hamas", r"\bhamas\b"),
        ("hezbollah", r"\bhezbollah\b"),
        ("houthis", r"\bhouthis?\b"),
        ("middle_east", r"\bmiddle east\b"),
        ("hostages", r"\bhostages?\b"),
        ("missiles", r"\bmissiles?\b"),
        ("ceasefire", r"\bceasefire\b"),
        ("nuclear", r"\bnuclear\b"),
    ),
    "oil_gas_energy": (
        ("oil", r"\boil\b"),
        ("crude", r"\bcrude\b"),
        ("gas_prices", r"\bgas prices\b"),
        ("gasoline", r"\bgasoline\b"),
        ("natural_gas", r"\bnatural gas\b"),
        ("lng", r"\blng\b"),
        ("drill", r"\bdrill(?:ing)?\b"),
        ("frack", r"\bfrack(?:ing)?\b"),
        ("pipeline", r"\bpipeline(?:s)?\b"),
        ("petroleum", r"\bpetroleum\b"),
        ("spr", r"\bstrategic petroleum reserve\b"),
        ("energy_production", r"\benergy production\b"),
        ("american_energy", r"\bamerican energy\b"),
        ("windmills", r"\bwindmills?\b"),
        ("opec", r"\bopec\b"),
    ),
    "fed_inflation_rates": (
        ("fed", r"\bfed\b"),
        ("federal_reserve", r"\bfederal reserve\b"),
        ("jay_powell", r"\bjay powell\b"),
        ("powell", r"\bpowell\b"),
        ("inflation", r"\binflation\b"),
        ("interest_rates", r"\binterest rates?\b"),
        ("rate_cuts", r"\brate cuts?\b"),
        ("rate_hikes", r"\brate hikes?\b"),
        ("mortgage_rates", r"\bmortgage rates?\b"),
        ("cpi", r"\bcpi\b"),
        ("pce", r"\bpce\b"),
    ),
    "immigration_border": (
        ("border", r"\bborder(?:s)?\b"),
        ("immigration", r"\bimmigration\b"),
        ("immigrants", r"\bimmigrant(?:s)?\b"),
        ("migrants", r"\bmigrant(?:s)?\b"),
        ("illegal_aliens", r"\billegal alien(?:s)?\b"),
        ("deport", r"\bdeport(?:ation|ed|ing)?\b"),
        ("asylum", r"\basylum\b"),
        ("border_patrol", r"\bborder patrol\b"),
        ("fentanyl", r"\bfentanyl\b"),
        ("cartels", r"\bcartel(?:s)?\b"),
        ("tren_de_aragua", r"\btren de aragua\b"),
        ("repatriation", r"\brepatriation\b"),
    ),
    "domestic_politics_attacks": (
        ("crooked_joe", r"\bcrooked joe\b"),
        ("sleepy_joe", r"\bsleepy joe\b"),
        ("radical_left", r"\bradical left\b"),
        ("witch_hunt", r"\bwitch hunt\b"),
        ("fake_news", r"\bfake news\b"),
        ("enemy_of_the_people", r"\benemy of the people\b"),
        ("msdnc", r"\bmsdnc\b"),
        ("msnbc", r"\bmsnbc\b"),
        ("cnn", r"\bcnn\b"),
        ("rachel_maddow", r"\brachel maddow\b"),
        ("jim_acosta", r"\bjim acosta\b"),
        ("jack_smith", r"\bjack smith\b"),
        ("letitia_james", r"\bletitia james\b"),
        ("alvin_bragg", r"\balvin bragg\b"),
        ("fani_willis", r"\bfani willis\b"),
        ("rigged_election", r"\brigged election\b"),
        ("election_fraud", r"\belection fraud\b"),
    ),
}
TOPIC_BUCKET_ORDER = [*TOPIC_RULES.keys(), TOPIC_OTHER]
TIMING_REGIME_ORDER = ["immediate", "delayed"]
BACKTEST_CONFIRM_MINUTES = 60
BACKTEST_THRESHOLD_ORDER: tuple[tuple[str, float], ...] = (
    ("all", 0.0),
    ("p80", 0.8),
    ("p90", 0.9),
)
BACKTEST_EXIT_HOURS: tuple[int, ...] = (24, 72)
BACKTEST_LONG_STRADDLE_CAP_R = 5.0
BACKTEST_CREDIT_SHORT_UNITS = 0.5
BACKTEST_CREDIT_WIDTH_UNITS = 1.0
BACKTEST_CREDIT_PREMIUM_UNITS = 0.35
BACKTEST_STRATEGY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "strategy_name": "fade_debit_24h",
        "metric_col": "fade_debit_r_24h",
        "horizon_hours": 24,
        "family": "debit_spread_proxy",
        "thesis": "Fade the first-hour shock and exit after 24 hours.",
    },
    {
        "strategy_name": "fade_credit_24h",
        "metric_col": "fade_credit_r_24h",
        "horizon_hours": 24,
        "family": "credit_spread_proxy",
        "thesis": "Sell a farther-out fade spread and mark it after 24 hours.",
    },
    {
        "strategy_name": "follow_debit_24h",
        "metric_col": "follow_debit_r_24h",
        "horizon_hours": 24,
        "family": "debit_spread_proxy",
        "thesis": "Control: follow the first-hour shock and exit after 24 hours.",
    },
    {
        "strategy_name": "fade_debit_72h",
        "metric_col": "fade_debit_r_72h",
        "horizon_hours": 72,
        "family": "debit_spread_proxy",
        "thesis": "Fade the first-hour shock and exit after 72 hours.",
    },
    {
        "strategy_name": "fade_credit_72h",
        "metric_col": "fade_credit_r_72h",
        "horizon_hours": 72,
        "family": "credit_spread_proxy",
        "thesis": "Sell a farther-out fade spread and mark it after 72 hours.",
    },
    {
        "strategy_name": "long_straddle_24h",
        "metric_col": "long_straddle_r_24h",
        "horizon_hours": 24,
        "family": "long_vol_proxy",
        "thesis": "Control: buy a long-vol sleeve after the first-hour shock and mark it after 24 hours.",
    },
    {
        "strategy_name": "long_straddle_72h",
        "metric_col": "long_straddle_r_72h",
        "horizon_hours": 72,
        "family": "long_vol_proxy",
        "thesis": "Control: buy a long-vol sleeve after the first-hour shock and mark it after 72 hours.",
    },
)
FUTURES_EXECUTION_PROXY_MAP: dict[str, dict[str, str]] = {
    "QQQ": {
        "futures_symbol": "MNQ",
        "futures_product": "Micro E-mini Nasdaq-100 futures",
        "options_product": "Options on Micro E-mini Nasdaq-100 futures",
        "contract_unit": "1 MNQ futures contract",
        "product_url": "https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.options.html",
        "hours_url": "https://www.cmegroup.com/trading/equity-index/us-index/micro-e-mini-options.html",
        "hours_note": "CME Globex nearly 24x5 with a daily maintenance halt; confirm holiday hours before trading.",
        "expirations_note": "Weekly, end-of-month, and quarterly expirations are available.",
    },
    "SPY": {
        "futures_symbol": "MES",
        "futures_product": "Micro E-mini S&P 500 futures",
        "options_product": "Options on Micro E-mini S&P 500 futures",
        "contract_unit": "1 MES futures contract",
        "product_url": "https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.contractSpecs.options.html",
        "hours_url": "https://www.cmegroup.com/trading/equity-index/us-index/micro-e-mini-options.html",
        "hours_note": "CME Globex nearly 24x5 with a daily maintenance halt; confirm holiday hours before trading.",
        "expirations_note": "Weekly, end-of-month, and quarterly expirations are available.",
    },
    "USO": {
        "futures_symbol": "CL",
        "futures_product": "NYMEX WTI Crude Oil futures",
        "options_product": "WTI Crude Oil options",
        "contract_unit": "1,000 barrels",
        "product_url": "https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.options.html",
        "hours_url": "https://www.cmegroup.com/articles/faqs/faq-tuesday-and-thursday-weekly-wti-options.html",
        "hours_note": "CME Globex trades Sunday-Friday with a daily maintenance halt; confirm holiday hours before trading.",
        "expirations_note": "Monthly and weekly expirations are available.",
    },
}
FUTURES_EXECUTION_BY_FUTURES = {
    meta["futures_symbol"]: {"proxy_symbol": proxy_symbol, **meta}
    for proxy_symbol, meta in FUTURES_EXECUTION_PROXY_MAP.items()
}
FUTURES_EXECUTION_ENTRY_WINDOWS_MINUTES: tuple[int, ...] = (30, 60, 90)
FUTURES_EXECUTION_THRESHOLD_ORDER: tuple[tuple[str, float], ...] = BACKTEST_THRESHOLD_ORDER
FUTURES_EXECUTION_STOP_UNITS: tuple[float, ...] = (0.75, 1.0)
FUTURES_EXECUTION_TIME_STOPS_HOURS: tuple[int, ...] = (12, 24)
FUTURES_EXECUTION_MIN_TRADES = 30
FUTURES_EXECUTION_OUTPUT_SUBDIR = "futures_execution_v1"
COMPILED_TOPIC_RULES: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    topic: tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in rules)
    for topic, rules in TOPIC_RULES.items()
}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def build_archive_url(
    start_date: str | None = None,
    per_page: int = 200,
    sort: str = "asc",
) -> str:
    params = [f"sort={sort}", f"per_page={per_page}", "removed=include"]
    if start_date:
        payload = {"status_created_at": f"{start_date} 00:00:00", "_pointsToNextItems": True}
        cursor = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        params.append(f"cursor={cursor}")
    return f"{ARCHIVE_ROOT}/?{'&'.join(params)}"


def infer_market_session(ts_et: pd.Timestamp) -> str:
    hm = (ts_et.hour, ts_et.minute)
    if hm < RTH_OPEN_ET:
        return "pre_rth"
    if hm < RTH_CLOSE_ET:
        return "rth"
    return "post_rth"


def ceil_to_5m(ts: pd.Timestamp) -> pd.Timestamp:
    ts_utc = ts.tz_convert("UTC")
    floored = ts_utc.floor("5min")
    rounded = floored if floored == ts_utc else floored + pd.Timedelta(minutes=5)
    return rounded.tz_convert(TZ_ET)


def first_direct_cursor_link(
    statuses: Tag,
    page_url: str,
) -> str | None:
    soup = statuses.find_parent("html")
    if soup is None:
        return None
    cursor_links: list[str] = []
    for anchor in soup.select('a[href*="cursor="]'):
        href = anchor.get("href")
        if not href:
            continue
        full = urljoin(page_url, href)
        parsed = urlparse(full)
        qs = parse_qs(parsed.query)
        if "cursor" in qs and qs.get("sort", [""])[0] == "asc":
            qs["sort"] = ["asc"]
            qs["per_page"] = ["200"]
            qs["removed"] = ["include"]
            rebuilt = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(qs, doseq=True),
                    parsed.fragment,
                )
            )
            cursor_links.append(rebuilt)
    if not cursor_links:
        return None
    return cursor_links[-1]


def scrape_archive(
    output_csv: Path,
    max_pages: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sleep_seconds: float = 0.3,
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    records: list[dict[str, Any]] = []
    url = build_archive_url(start_date=start_date)
    visited: set[str] = set()
    pages = 0
    scrape_row = 0

    while url and url not in visited:
        visited.add(url)
        response = session.get(url, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        statuses = soup.select_one(".statuses")
        if statuses is None:
            raise RuntimeError(f"Could not find status container in {url}")

        pending_reblog = False
        for child in statuses.find_all(recursive=False):
            if not isinstance(child, Tag):
                continue
            classes = child.get("class", [])
            if "status__reblog-indicator" in classes:
                pending_reblog = True
                continue
            if "status" not in classes:
                continue

            meta_items = child.select(".status-info__meta-item")
            handle = normalize_space(meta_items[0].get_text(" ", strip=True)) if len(meta_items) >= 1 else ""
            time_text = normalize_space(meta_items[1].get_text(" ", strip=True)) if len(meta_items) >= 2 else ""
            if not time_text:
                pending_reblog = False
                continue

            content_node = child.select_one(".status__content")
            external_link = child.select_one(".status__external-link")
            status_card = child.select_one(".status-card")
            archive_status_url = normalize_space(child.get("data-status-url", ""))
            archive_status_id = None
            if archive_status_url:
                match = re.search(r"/statuses/(\d+)", archive_status_url)
                if match:
                    archive_status_id = int(match.group(1))

            account_name_node = child.select_one(".status-info__account-name")

            record = {
                "scrape_row": scrape_row,
                "archive_status_id": archive_status_id,
                "archive_status_url": archive_status_url.strip(),
                "page_url": url,
                "account_name": normalize_space(account_name_node.get_text(" ", strip=True)) if account_name_node else "",
                "handle": handle,
                "displayed_time_et": time_text,
                "is_reblog_event": bool(pending_reblog),
                "external_link_label": normalize_space(external_link.get_text(" ", strip=True)) if external_link else "",
                "external_link_url": external_link.get("href", "").strip() if external_link else "",
                "content_text": normalize_space(content_node.get_text(" ", strip=True)) if content_node else "",
                "has_status_card": bool(status_card),
                "status_card_url": status_card.get("href", "").strip() if status_card else "",
                "status_card_text": normalize_space(status_card.get_text(" ", strip=True)) if status_card else "",
                "attachment_count": len(child.select(".status-attachment")),
            }
            records.append(record)
            scrape_row += 1
            pending_reblog = False

        pages += 1
        print(f"[scrape] page={pages} rows={len(records)} url={url}", flush=True)
        if max_pages and pages >= max_pages:
            break

        next_url = first_direct_cursor_link(statuses, url)
        if not next_url or next_url == url:
            break
        url = next_url
        time.sleep(sleep_seconds)

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("Archive scrape returned no rows")
    ensure_parent(output_csv)
    df.to_csv(output_csv, index=False)
    return df


@dataclass
class HistoricalResult:
    bars: list[dict[str, Any]]
    errors: list[tuple[int, int, str]]


class IBHistoricalClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self._bars: list[dict[str, Any]] = []
        self._errors: list[tuple[int, int, str]] = []
        self._done = threading.Event()
        self._lock = threading.Lock()

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        with self._lock:
            self._errors.append((reqId, errorCode, errorString))
        if errorCode not in (2104, 2106, 2158):
            self._done.set()

    def historicalData(self, reqId: int, bar: Any) -> None:
        with self._lock:
            self._bars.append(
                {
                    "date": bar.date,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": float(bar.volume),
                }
            )

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        self._done.set()

    def reset_request(self) -> None:
        with self._lock:
            self._bars = []
            self._errors = []
        self._done.clear()

    def wait_for_result(self, timeout: float = 90.0) -> HistoricalResult:
        finished = self._done.wait(timeout)
        with self._lock:
            bars = list(self._bars)
            errors = list(self._errors)
        if not finished:
            raise TimeoutError("IBKR historical request timed out")
        return HistoricalResult(bars=bars, errors=errors)


def make_stock_contract(symbol: str) -> Contract:
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    contract.primaryExchange = "ARCA"
    return contract


def request_5m_month(
    client: IBHistoricalClient,
    req_id: int,
    contract: Contract,
    end_dt_et: pd.Timestamp,
    duration: str = "2 M",
    use_rth: int = 0,
) -> HistoricalResult:
    client.reset_request()
    end_str = end_dt_et.tz_convert(TZ_ET).strftime("%Y%m%d %H:%M:%S US/Eastern")
    client.reqHistoricalData(
        req_id,
        contract,
        end_str,
        duration,
        "5 mins",
        "TRADES",
        use_rth,
        1,
        False,
        [],
    )
    return client.wait_for_result(timeout=180.0)


def fetch_market_history(
    output_dir: Path,
    symbols: list[str],
    start_date_et: str,
    end_date_et: str,
    host: str = "127.0.0.1",
    port: int = 7496,
    client_id: int = 9200,
    use_rth: int = 0,
    duration: str = "2 M",
    min_interval_seconds: float = 10.5,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    client = IBHistoricalClient()
    client.connect(host, port, clientId=client_id)
    thread = threading.Thread(target=client.run, daemon=True)
    thread.start()
    time.sleep(1.5)

    start_ts = pd.Timestamp(start_date_et).tz_localize(TZ_ET)
    end_ts = pd.Timestamp(end_date_et).tz_localize(TZ_ET) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    recent_requests: deque[float] = deque()
    req_id = 1

    try:
        for symbol in symbols:
            contract = make_stock_contract(symbol)
            all_chunks: list[pd.DataFrame] = []
            cursor = end_ts
            chunk_no = 0
            print(f"[market] symbol={symbol} start cursor={cursor.isoformat()} duration={duration}", flush=True)

            while cursor > start_ts:
                now = time.monotonic()
                while recent_requests and now - recent_requests[0] > 600:
                    recent_requests.popleft()
                if len(recent_requests) >= 58:
                    sleep_for = max(0.0, 600 - (now - recent_requests[0]) + 1)
                    time.sleep(sleep_for)
                elif recent_requests:
                    gap = now - recent_requests[-1]
                    if gap < min_interval_seconds:
                        time.sleep(min_interval_seconds - gap)

                result = request_5m_month(
                    client,
                    req_id,
                    contract,
                    cursor,
                    duration=duration,
                    use_rth=use_rth,
                )
                recent_requests.append(time.monotonic())
                req_id += 1
                if not result.bars:
                    break

                chunk = pd.DataFrame(result.bars)
                chunk["symbol"] = symbol
                chunk["timestamp_berlin"] = pd.to_datetime(
                    chunk["date"],
                    format="%Y%m%d  %H:%M:%S",
                ).dt.tz_localize(TZ_BERLIN)
                chunk["timestamp_et"] = chunk["timestamp_berlin"].dt.tz_convert(TZ_ET)
                chunk = chunk.drop(columns=["date"])
                all_chunks.append(chunk)
                chunk_no += 1

                earliest = chunk["timestamp_et"].min()
                latest = chunk["timestamp_et"].max()
                print(
                    f"[market] symbol={symbol} chunk={chunk_no} rows={len(chunk)} "
                    f"earliest={earliest.isoformat()} latest={latest.isoformat()}",
                    flush=True,
                )
                cursor = earliest - pd.Timedelta(minutes=5)
                if earliest <= start_ts:
                    break

            if not all_chunks:
                raise RuntimeError(f"No market data returned for {symbol}")

            combined = (
                pd.concat(all_chunks, ignore_index=True)
                .drop_duplicates(subset=["symbol", "timestamp_berlin"])
                .sort_values("timestamp_berlin")
            )
            combined = combined[combined["timestamp_et"] >= start_ts]
            csv_path = output_dir / f"{symbol.lower()}_5m.csv"
            ensure_parent(csv_path)
            combined.to_csv(csv_path, index=False)
            print(f"[market] symbol={symbol} wrote rows={len(combined)} path={csv_path}", flush=True)
    finally:
        client.disconnect()


def add_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    analyzer = SentimentIntensityAnalyzer()

    def score(text: str) -> dict[str, float]:
        return analyzer.polarity_scores(text or "")

    scores = df["content_text"].fillna("").map(score)
    out = df.copy()
    out["sentiment_neg"] = scores.map(lambda x: x["neg"])
    out["sentiment_neu"] = scores.map(lambda x: x["neu"])
    out["sentiment_pos"] = scores.map(lambda x: x["pos"])
    out["sentiment_compound"] = scores.map(lambda x: x["compound"])
    out["is_text_empty"] = out["content_text"].fillna("").str.len().eq(0)
    out["content_len"] = out["content_text"].fillna("").str.len()
    out["ambiguous_time_fallback"] = False

    naive = pd.to_datetime(out["displayed_time_et"], format="%B %d, %Y, %I:%M %p", errors="coerce")
    parsed = naive.dt.tz_localize(TZ_ET, ambiguous="NaT", nonexistent="shift_forward")
    out["parsed_time_et"] = parsed

    authored_mask = (~out["is_reblog_event"]) & (out["handle"] == "@realDonaldTrump")
    authored_idx = out.loc[authored_mask].sort_values("scrape_row").index
    if len(authored_idx):
        authored_naive = pd.to_datetime(
            out.loc[authored_idx, "displayed_time_et"],
            format="%B %d, %Y, %I:%M %p",
            errors="coerce",
        )
        authored_parsed = pd.Series(
            authored_naive.dt.tz_localize(TZ_ET, ambiguous="NaT", nonexistent="shift_forward").to_numpy(),
            index=authored_idx,
        )
        unresolved = authored_parsed.isna() & authored_naive.notna()
        if unresolved.any():
            fallback = authored_naive[unresolved].dt.tz_localize(
                TZ_ET,
                ambiguous=False,
                nonexistent="shift_forward",
            )
            fallback = pd.Series(fallback.to_numpy(), index=authored_idx[unresolved.to_numpy()])
            authored_parsed.loc[fallback.index] = fallback
            out.loc[fallback.index, "ambiguous_time_fallback"] = True
        out.loc[authored_idx, "parsed_time_et"] = authored_parsed.to_numpy()

    out["weekday_et"] = out["parsed_time_et"].dt.day_name()
    out["hour_et"] = out["parsed_time_et"].dt.hour
    out["market_session"] = out["parsed_time_et"].map(lambda x: infer_market_session(x) if pd.notna(x) else None)
    return out


def classify_burst_topic(text: str) -> dict[str, Any]:
    normalized = normalize_space(text)
    topic_hits: dict[str, list[str]] = {}
    for topic, rules in COMPILED_TOPIC_RULES.items():
        matched = [label for label, pattern in rules if pattern.search(normalized)]
        if matched:
            topic_hits[topic] = matched

    matched_topics = list(topic_hits)
    topic_bucket = matched_topics[0] if len(matched_topics) == 1 else TOPIC_OTHER

    trigger_terms = "; ".join(f"{topic}:{','.join(labels)}" for topic, labels in topic_hits.items())
    return {
        "topic_bucket": topic_bucket,
        "topic_match_count": len(matched_topics),
        "topic_is_ambiguous": len(matched_topics) > 1,
        "topic_matched_topics": ",".join(matched_topics),
        "topic_trigger_terms": trigger_terms,
    }


def add_topic_tags(bursts: pd.DataFrame) -> pd.DataFrame:
    if bursts.empty:
        out = bursts.copy()
        out["topic_bucket"] = pd.Series(dtype="object")
        out["topic_match_count"] = pd.Series(dtype="int64")
        out["topic_is_ambiguous"] = pd.Series(dtype="bool")
        out["topic_matched_topics"] = pd.Series(dtype="object")
        out["topic_trigger_terms"] = pd.Series(dtype="object")
        return out

    topic_meta = pd.DataFrame.from_records(
        [classify_burst_topic(text) for text in bursts["burst_text"].fillna("")],
        index=bursts.index,
    )
    return pd.concat([bursts, topic_meta], axis=1)


def build_bursts(posts: pd.DataFrame, gap_minutes: int = 15) -> pd.DataFrame:
    authored = posts.copy()
    authored["content_text"] = authored["content_text"].fillna("").astype(str)
    authored["posted_at_et"] = pd.to_datetime(authored["parsed_time_et"], utc=True).dt.tz_convert(TZ_ET)
    authored = authored.sort_values("posted_at_et").reset_index(drop=True)
    authored["gap_minutes"] = authored["posted_at_et"].diff().dt.total_seconds().div(60)
    authored["burst_start_flag"] = authored["gap_minutes"].isna() | authored["gap_minutes"].gt(gap_minutes)
    authored["burst_id"] = authored["burst_start_flag"].cumsum()

    grouped = authored.groupby("burst_id", sort=True)
    bursts = grouped.agg(
        burst_start_et=("posted_at_et", "min"),
        burst_end_et=("posted_at_et", "max"),
        n_posts=("burst_id", "size"),
        n_empty_text=("is_text_empty", "sum"),
        mean_post_sentiment=("sentiment_compound", "mean"),
        median_post_sentiment=("sentiment_compound", "median"),
        text_char_count=("content_len", "sum"),
    )
    bursts["burst_text"] = grouped["content_text"].apply(lambda s: "\n\n".join(x for x in s if x))
    analyzer = SentimentIntensityAnalyzer()
    burst_scores = bursts["burst_text"].fillna("").map(analyzer.polarity_scores)
    bursts["burst_sentiment_compound"] = burst_scores.map(lambda x: x["compound"])
    bursts["burst_sentiment_pos"] = burst_scores.map(lambda x: x["pos"])
    bursts["burst_sentiment_neg"] = burst_scores.map(lambda x: x["neg"])
    bursts["weekday_et"] = bursts["burst_start_et"].dt.day_name()
    bursts["hour_et"] = bursts["burst_start_et"].dt.hour
    bursts["market_session"] = bursts["burst_start_et"].map(infer_market_session)
    bursts["anchor_5m_et"] = bursts["burst_start_et"].map(ceil_to_5m)
    bursts = add_topic_tags(bursts)
    return bursts.reset_index()


def load_market_data(market_dir: Path, symbols: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        csv_path = market_dir / f"{symbol.lower()}_5m.csv"
        df = pd.read_csv(csv_path)
        df["timestamp_berlin"] = pd.to_datetime(df["timestamp_berlin"], utc=True).dt.tz_convert(TZ_BERLIN)
        df["timestamp_et"] = pd.to_datetime(df["timestamp_et"], utc=True).dt.tz_convert(TZ_ET)
        df = df.sort_values("timestamp_et").reset_index(drop=True)
        out[symbol] = df
    return out


def empirical_percentile(sample: np.ndarray, value: float) -> float:
    if sample.size == 0 or np.isnan(value):
        return math.nan
    return float((sample <= value).mean())


def infer_timing_regime(anchor_delay_minutes: float) -> str:
    return TIMING_REGIME_ORDER[0] if pd.notna(anchor_delay_minutes) and float(anchor_delay_minutes) <= 5.0 else TIMING_REGIME_ORDER[1]


def build_slot_baselines(market: pd.DataFrame, horizons: dict[str, pd.Timedelta]) -> dict[str, dict[tuple[int, str], np.ndarray]]:
    baseline: dict[str, dict[tuple[int, str], np.ndarray]] = {}
    frame = market.copy()
    frame["slot_weekday"] = frame["timestamp_et"].dt.dayofweek
    frame["slot_time"] = frame["timestamp_et"].dt.strftime("%H:%M")
    index = frame["timestamp_et"]
    closes = frame["close"].to_numpy()

    for label, horizon in horizons.items():
        target_idx = index.searchsorted(index + horizon, side="left")
        valid = target_idx < len(frame)
        future_close = np.full(len(frame), np.nan)
        future_close[valid] = closes[target_idx[valid]]
        frame[f"ret_{label}"] = future_close / closes - 1.0
        groups: dict[tuple[int, str], np.ndarray] = {}
        for (weekday, slot_time), sub in frame.dropna(subset=[f"ret_{label}"]).groupby(["slot_weekday", "slot_time"]):
            groups[(int(weekday), str(slot_time))] = sub[f"ret_{label}"].to_numpy()
        baseline[label] = groups
    return baseline


def measure_events_for_symbol(
    bursts: pd.DataFrame,
    market: pd.DataFrame,
    symbol: str,
    peak_window: pd.Timedelta = pd.Timedelta(hours=24),
    reversion_window: pd.Timedelta = pd.Timedelta(days=5),
) -> pd.DataFrame:
    horizons = {
        "30m": pd.Timedelta(minutes=30),
        "60m": pd.Timedelta(minutes=60),
        "240m": pd.Timedelta(hours=4),
        "24h": pd.Timedelta(hours=24),
    }
    baselines = build_slot_baselines(market, {"60m": horizons["60m"], "240m": horizons["240m"], "24h": horizons["24h"]})

    index = market["timestamp_et"]
    closes = market["close"].to_numpy()
    results: list[dict[str, Any]] = []

    for event in bursts.itertuples(index=False):
        event_ts = getattr(event, "burst_start_et")
        anchor_ts = getattr(event, "anchor_5m_et")
        pre_idx = index.searchsorted(event_ts, side="left") - 1
        anchor_idx = index.searchsorted(anchor_ts, side="left")
        if pre_idx < 0 or anchor_idx >= len(market):
            continue

        baseline_px = closes[pre_idx]
        baseline_ts = index.iloc[pre_idx]
        anchor_bar_ts = index.iloc[anchor_idx]

        row: dict[str, Any] = {
            "burst_id": getattr(event, "burst_id"),
            "symbol": symbol,
            "event_ts_et": event_ts,
            "anchor_ts_et": anchor_ts,
            "anchor_bar_ts_et": anchor_bar_ts,
            "baseline_ts_et": baseline_ts,
            "baseline_price": baseline_px,
            "anchor_delay_minutes": float((anchor_bar_ts - event_ts).total_seconds() / 60.0),
        }

        for label, horizon in horizons.items():
            target_idx = index.searchsorted(anchor_bar_ts + horizon, side="left")
            row[f"ret_{label}"] = math.nan if target_idx >= len(market) else float(closes[target_idx] / baseline_px - 1.0)

        window_end_idx = index.searchsorted(anchor_bar_ts + peak_window, side="left")
        if window_end_idx <= anchor_idx:
            row["peak_ret_24h"] = math.nan
            row["peak_ts_et"] = pd.NaT
            row["time_to_peak_minutes_from_anchor"] = math.nan
            row["time_to_peak_minutes_from_event"] = math.nan
            row["reversion_minutes_from_event"] = math.nan
            row["reversion_minutes_from_anchor"] = math.nan
            row["reversion_minutes_from_peak"] = math.nan
            row["reverted_within_5d"] = False
        else:
            path_close = closes[anchor_idx:window_end_idx]
            path_index = index.iloc[anchor_idx:window_end_idx]
            path_ret = path_close / baseline_px - 1.0
            peak_pos = int(np.nanargmax(np.abs(path_ret)))
            peak_ret = float(path_ret[peak_pos])
            peak_ts = path_index.iloc[peak_pos]

            row["peak_ret_24h"] = peak_ret
            row["peak_ts_et"] = peak_ts
            row["time_to_peak_minutes_from_anchor"] = float((peak_ts - anchor_bar_ts).total_seconds() / 60.0)
            row["time_to_peak_minutes_from_event"] = float((peak_ts - event_ts).total_seconds() / 60.0)

            if abs(peak_ret) < 1e-12:
                row["reversion_minutes_from_event"] = 0.0
                row["reversion_minutes_from_anchor"] = 0.0
                row["reversion_minutes_from_peak"] = 0.0
                row["reverted_within_5d"] = True
            else:
                search_end_idx = index.searchsorted(anchor_bar_ts + reversion_window, side="left")
                post_peak_close = closes[anchor_idx + peak_pos : search_end_idx]
                post_peak_index = index.iloc[anchor_idx + peak_pos : search_end_idx]
                signed_ret = np.sign(peak_ret) * (post_peak_close / baseline_px - 1.0)
                cross = np.where(signed_ret <= 0)[0]
                if cross.size == 0:
                    row["reversion_minutes_from_event"] = math.nan
                    row["reversion_minutes_from_anchor"] = math.nan
                    row["reversion_minutes_from_peak"] = math.nan
                    row["reverted_within_5d"] = False
                else:
                    cross_ts = post_peak_index.iloc[int(cross[0])]
                    row["reversion_minutes_from_event"] = float((cross_ts - event_ts).total_seconds() / 60.0)
                    row["reversion_minutes_from_anchor"] = float((cross_ts - anchor_bar_ts).total_seconds() / 60.0)
                    row["reversion_minutes_from_peak"] = float((cross_ts - peak_ts).total_seconds() / 60.0)
                    row["reverted_within_5d"] = True

        anchor_weekday = anchor_bar_ts.dayofweek
        anchor_slot = anchor_bar_ts.strftime("%H:%M")
        for label in ("60m", "240m", "24h"):
            sample = baselines[label].get((anchor_weekday, anchor_slot), np.array([]))
            actual = row.get(f"ret_{label}", math.nan)
            row[f"ret_{label}_slot_median"] = math.nan if sample.size == 0 else float(np.median(sample))
            row[f"ret_{label}_slot_percentile"] = empirical_percentile(sample, actual)
            row[f"abs_ret_{label}_slot_percentile"] = empirical_percentile(np.abs(sample), abs(actual)) if sample.size else math.nan

        results.append(row)

    return pd.DataFrame(results)


def bootstrap_ci(values: np.ndarray, seed: int = 7, iterations: int = 2000) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return (math.nan, math.nan, math.nan)
    rng = np.random.default_rng(seed)
    means = np.empty(iterations)
    n = len(values)
    for i in range(iterations):
        sample = rng.choice(values, size=n, replace=True)
        means[i] = sample.mean()
    return float(values.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarize_event_slice(sub: pd.DataFrame) -> pd.Series:
    peak = sub["peak_ret_24h"].to_numpy(dtype=float)
    reverted = sub.loc[sub["reverted_within_5d"]]
    return pd.Series(
        {
            "event_count": int(len(sub)),
            "median_ret_60m": float(sub["ret_60m"].median()) if len(sub) else math.nan,
            "median_abs_ret_60m": float(np.nanmedian(np.abs(sub["ret_60m"].to_numpy(dtype=float)))) if len(sub) else math.nan,
            "mean_abs_ret_60m_slot_percentile": float(sub["abs_ret_60m_slot_percentile"].mean()) if len(sub) else math.nan,
            "median_peak_abs_ret_24h": float(np.nanmedian(np.abs(peak))) if len(peak) else math.nan,
            "reversion_rate_5d": float(sub["reverted_within_5d"].mean()) if len(sub) else math.nan,
            "median_reversion_minutes_after_first_trade": (
                float(reverted["reversion_minutes_from_anchor"].median()) if len(reverted) else math.nan
            ),
            "median_reversion_minutes_from_event": (
                float(reverted["reversion_minutes_from_event"].median()) if len(reverted) else math.nan
            ),
        }
    )


def build_topic_symbol_timing_summary(
    event_results: pd.DataFrame,
    symbols: list[str],
) -> pd.DataFrame:
    grouped = (
        event_results.groupby(["topic_bucket", "symbol", "timing_regime"], dropna=False)
        .apply(summarize_event_slice)
        .reset_index()
    )
    full_index = pd.MultiIndex.from_product(
        [TOPIC_BUCKET_ORDER, symbols, TIMING_REGIME_ORDER],
        names=["topic_bucket", "symbol", "timing_regime"],
    )
    summary = grouped.set_index(["topic_bucket", "symbol", "timing_regime"]).reindex(full_index).reset_index()
    summary["event_count"] = summary["event_count"].fillna(0).astype(int)
    summary["topic_bucket"] = pd.Categorical(summary["topic_bucket"], categories=TOPIC_BUCKET_ORDER, ordered=True)
    summary["timing_regime"] = pd.Categorical(summary["timing_regime"], categories=TIMING_REGIME_ORDER, ordered=True)
    return summary.sort_values(["topic_bucket", "timing_regime", "symbol"]).reset_index(drop=True)


def build_summary(
    posts: pd.DataFrame,
    bursts: pd.DataFrame,
    event_results: pd.DataFrame,
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    authored_posts = posts[(~posts["is_reblog_event"]) & (posts["handle"] == "@realDonaldTrump")].copy()
    if "archive_status_id" in authored_posts.columns:
        authored_posts = authored_posts.drop_duplicates(subset=["archive_status_id"])
    summary["archive_rows"] = int(len(posts))
    summary["authored_rows"] = int(len(authored_posts))
    summary["reblog_rows"] = int(len(posts.query("is_reblog_event == True")))
    summary["empty_text_rows"] = int(authored_posts["is_text_empty"].sum())
    summary["authored_bursts_15m"] = int(len(bursts))
    summary["analyzable_bursts"] = int(event_results["burst_id"].nunique()) if not event_results.empty else 0
    summary["dropped_bursts_market_window"] = (
        int(len(bursts) - event_results["burst_id"].nunique()) if not event_results.empty else int(len(bursts))
    )
    summary["study_range_et"] = {
        "start": bursts["burst_start_et"].min().isoformat() if not bursts.empty else None,
        "end": bursts["burst_start_et"].max().isoformat() if not bursts.empty else None,
    }
    summary["weekday_counts"] = (
        bursts.groupby("weekday_et").size().sort_values(ascending=False).astype(int).to_dict()
        if not bursts.empty
        else {}
    )
    summary["hour_counts"] = (
        bursts.groupby("hour_et").size().sort_index().astype(int).to_dict()
        if not bursts.empty
        else {}
    )
    summary["session_counts"] = (
        bursts.groupby("market_session").size().sort_values(ascending=False).astype(int).to_dict()
        if not bursts.empty
        else {}
    )

    symbol_summary: dict[str, Any] = {}
    for symbol, sub in event_results.groupby("symbol"):
        abs_pctl = sub["abs_ret_60m_slot_percentile"].to_numpy(dtype=float)
        mean_abs_pctl, abs_lo, abs_hi = bootstrap_ci(abs_pctl)
        peak = sub["peak_ret_24h"].to_numpy(dtype=float)
        symbol_summary[symbol] = {
            "event_count": int(len(sub)),
            "median_ret_60m": float(sub["ret_60m"].median()),
            "median_abs_ret_60m": float(sub["ret_60m"].abs().median()),
            "mean_abs_ret_60m_slot_percentile": mean_abs_pctl,
            "mean_abs_ret_60m_slot_percentile_ci95": [abs_lo, abs_hi],
            "median_peak_abs_ret_24h": float(np.nanmedian(np.abs(peak))) if len(peak) else math.nan,
            "reversion_rate_5d": float(sub["reverted_within_5d"].mean()),
            "median_anchor_delay_minutes": float(sub["anchor_delay_minutes"].median()),
            "median_reversion_minutes_after_first_trade": float(
                sub.loc[sub["reverted_within_5d"], "reversion_minutes_from_anchor"].median()
            )
            if sub["reverted_within_5d"].any()
            else math.nan,
            "median_reversion_minutes_from_event": float(
                sub.loc[sub["reverted_within_5d"], "reversion_minutes_from_event"].median()
            )
            if sub["reverted_within_5d"].any()
            else math.nan,
        }
    summary["symbol_summary"] = symbol_summary
    burst_timing = event_results[["burst_id", "timing_regime"]].drop_duplicates() if not event_results.empty else pd.DataFrame()
    topic_timing = (
        bursts[["burst_id", "topic_bucket"]]
        .merge(burst_timing, on="burst_id", how="inner")
        .groupby(["topic_bucket", "timing_regime"])
        .size()
        .unstack(fill_value=0)
        if not bursts.empty and not burst_timing.empty
        else pd.DataFrame()
    )
    summary["timing_regime_counts"] = (
        burst_timing["timing_regime"].value_counts().reindex(TIMING_REGIME_ORDER, fill_value=0).astype(int).to_dict()
        if not burst_timing.empty
        else {}
    )
    summary["topic_tagging"] = {
        "rule_version": TOPIC_RULE_VERSION,
        "burst_topic_counts": (
            bursts["topic_bucket"].value_counts().reindex(TOPIC_BUCKET_ORDER, fill_value=0).astype(int).to_dict()
            if not bursts.empty
            else {}
        ),
        "single_topic_bursts": int(bursts["topic_match_count"].eq(1).sum()) if not bursts.empty else 0,
        "ambiguous_topic_bursts": int(bursts["topic_match_count"].gt(1).sum()) if not bursts.empty else 0,
        "no_topic_match_bursts": int(bursts["topic_match_count"].eq(0).sum()) if not bursts.empty else 0,
        "all_text_empty_bursts": int(bursts["text_char_count"].eq(0).sum()) if not bursts.empty else 0,
        "topic_timing_counts": (
            {
                topic: {
                    timing: int(topic_timing.at[topic, timing])
                    if timing in topic_timing.columns and topic in topic_timing.index
                    else 0
                    for timing in TIMING_REGIME_ORDER
                }
                for topic in TOPIC_BUCKET_ORDER
            }
            if not topic_timing.empty
            else {}
        ),
    }

    sentiment_cut = bursts["burst_sentiment_compound"].quantile([0.1, 0.9]).to_dict() if not bursts.empty else {}
    summary["sentiment_cutoffs"] = {str(k): float(v) for k, v in sentiment_cut.items()}

    return summary


def build_topic_rules_payload() -> dict[str, Any]:
    return {
        "rule_version": TOPIC_RULE_VERSION,
        "assignment_policy": (
            "Assign a named topic only when exactly one topic family matches burst_text; otherwise classify as other."
        ),
        "topics": {
            topic: [{"label": label, "pattern": pattern} for label, pattern in rules]
            for topic, rules in TOPIC_RULES.items()
        },
    }


def attach_burst_metadata(event_results: pd.DataFrame, bursts: pd.DataFrame) -> pd.DataFrame:
    return event_results.merge(
        bursts[
            [
                "burst_id",
                "burst_start_et",
                "burst_end_et",
                "n_posts",
                "n_empty_text",
                "mean_post_sentiment",
                "median_post_sentiment",
                "burst_sentiment_compound",
                "weekday_et",
                "hour_et",
                "market_session",
                "text_char_count",
                "topic_bucket",
                "topic_match_count",
                "topic_is_ambiguous",
                "topic_matched_topics",
                "topic_trigger_terms",
                "burst_text",
            ]
        ],
        on="burst_id",
        how="left",
    )


def prepare_study_artifacts(
    posts_csv: Path,
    market_dir: Path,
    symbols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    posts = add_sentiment(pd.read_csv(posts_csv))
    authored = posts[(~posts["is_reblog_event"]) & (posts["handle"] == "@realDonaldTrump")].copy()
    authored = authored.drop_duplicates(subset=["archive_status_id"]).reset_index(drop=True)
    bursts = build_bursts(authored, gap_minutes=15)
    market = load_market_data(market_dir, symbols)

    all_results: list[pd.DataFrame] = []
    for symbol in symbols:
        measured = measure_events_for_symbol(bursts, market[symbol], symbol)
        all_results.append(measured)
        print(f"[analyze] symbol={symbol} events={len(measured)}", flush=True)

    event_results = pd.concat(all_results, ignore_index=True)
    event_results["timing_regime"] = event_results["anchor_delay_minutes"].map(infer_timing_regime)
    event_results = attach_burst_metadata(event_results, bursts)
    return posts, bursts, market, event_results


def write_study_outputs(
    output_dir: Path,
    posts: pd.DataFrame,
    bursts: pd.DataFrame,
    event_results: pd.DataFrame,
    symbols: list[str],
    prefix: str = "",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    name_prefix = f"{prefix}_" if prefix else ""

    event_level_csv = output_dir / f"{name_prefix}event_level_market_reaction.csv"
    bursts_csv = output_dir / f"{name_prefix}authored_bursts.csv"
    summary_json = output_dir / f"{name_prefix}summary.json"
    weekday_hour_csv = output_dir / f"{name_prefix}weekday_hour_cluster.csv"
    topic_summary_csv = output_dir / f"{name_prefix}topic_symbol_timing_summary.csv"
    topic_rules_json = output_dir / f"{name_prefix}topic_tagging_rules.json"

    ensure_parent(event_level_csv)
    event_results.to_csv(event_level_csv, index=False)
    bursts.to_csv(bursts_csv, index=False)

    weekday_hour = (
        bursts.groupby(["weekday_et", "hour_et"])
        .agg(
            burst_count=("burst_id", "size"),
            mean_sentiment=("burst_sentiment_compound", "mean"),
            median_posts_per_burst=("n_posts", "median"),
        )
        .reset_index()
        .sort_values(["weekday_et", "hour_et"])
    )
    weekday_hour.to_csv(weekday_hour_csv, index=False)
    build_topic_symbol_timing_summary(event_results, symbols).to_csv(topic_summary_csv, index=False)
    summary_json.write_text(json.dumps(build_summary(posts, bursts, event_results), indent=2))
    topic_rules_json.write_text(json.dumps(build_topic_rules_payload(), indent=2))


def event_day_bucket(ts_et: pd.Timestamp) -> str:
    return "weekend" if ts_et.dayofweek >= 5 else "weekday"


def build_strategy_trades(
    event_results: pd.DataFrame,
    market: dict[str, pd.DataFrame],
    confirm_minutes: int = BACKTEST_CONFIRM_MINUTES,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for symbol, sub in event_results.groupby("symbol", sort=False):
        market_df = market[symbol]
        index = market_df["timestamp_et"]
        closes = market_df["close"].to_numpy()

        for event in sub.itertuples(index=False):
            baseline_px = float(getattr(event, "baseline_price"))
            anchor_bar_ts = getattr(event, "anchor_bar_ts_et")
            event_ts = getattr(event, "event_ts_et")
            entry_idx = index.searchsorted(anchor_bar_ts + pd.Timedelta(minutes=confirm_minutes), side="left")
            if entry_idx >= len(market_df):
                continue

            entry_ts = index.iloc[entry_idx]
            entry_px = float(closes[entry_idx])
            shock_px = entry_px - baseline_px
            if abs(shock_px) < 1e-12:
                continue

            shock_sign = 1.0 if shock_px > 0 else -1.0
            trade_row: dict[str, Any] = {
                "burst_id": getattr(event, "burst_id"),
                "symbol": symbol,
                "timing_regime": getattr(event, "timing_regime"),
                "topic_bucket": getattr(event, "topic_bucket"),
                "event_day_bucket": event_day_bucket(event_ts),
                "is_weekend_event": event_day_bucket(event_ts) == "weekend",
                "event_ts_et": event_ts,
                "anchor_bar_ts_et": anchor_bar_ts,
                "entry_ts_et": entry_ts,
                "baseline_price": baseline_px,
                "entry_price": entry_px,
                "shock_direction": "up" if shock_sign > 0 else "down",
                "entry_abs_return_from_baseline": float(abs(entry_px / baseline_px - 1.0)),
                "entry_abs_ret_60m_slot_percentile": float(getattr(event, "abs_ret_60m_slot_percentile")),
                "anchor_delay_minutes": float(getattr(event, "anchor_delay_minutes")),
                "n_posts": int(getattr(event, "n_posts")),
                "topic_is_ambiguous": bool(getattr(event, "topic_is_ambiguous")),
            }

            for horizon_hours in BACKTEST_EXIT_HOURS:
                exit_idx = index.searchsorted(entry_ts + pd.Timedelta(hours=horizon_hours), side="left")
                if exit_idx >= len(market_df):
                    trade_row[f"exit_ts_et_{horizon_hours}h"] = pd.NaT
                    trade_row[f"exit_price_{horizon_hours}h"] = math.nan
                    trade_row[f"fade_debit_r_{horizon_hours}h"] = math.nan
                    trade_row[f"follow_debit_r_{horizon_hours}h"] = math.nan
                    trade_row[f"fade_credit_r_{horizon_hours}h"] = math.nan
                    trade_row[f"long_straddle_raw_r_{horizon_hours}h"] = math.nan
                    trade_row[f"long_straddle_r_{horizon_hours}h"] = math.nan
                    trade_row[f"adverse_extension_units_{horizon_hours}h"] = math.nan
                    trade_row[f"favorable_extension_units_{horizon_hours}h"] = math.nan
                    trade_row[f"contained_within_0_5x_shock_{horizon_hours}h"] = False
                    trade_row[f"contained_within_1_0x_shock_{horizon_hours}h"] = False
                    continue

                exit_ts = index.iloc[exit_idx]
                exit_px = float(closes[exit_idx])
                path_px = closes[entry_idx : exit_idx + 1]
                signed_extension_units = shock_sign * (path_px - entry_px) / abs(shock_px)
                adverse_extension_units = float(np.max(signed_extension_units))
                favorable_extension_units = float(np.max(-signed_extension_units))
                exit_extension_units = float(shock_sign * (exit_px - entry_px) / abs(shock_px))
                credit_intrinsic_units = float(
                    np.clip(exit_extension_units - BACKTEST_CREDIT_SHORT_UNITS, 0.0, BACKTEST_CREDIT_WIDTH_UNITS)
                )
                long_straddle_raw = float(abs(exit_px - entry_px) / abs(shock_px) - 1.0)

                trade_row[f"exit_ts_et_{horizon_hours}h"] = exit_ts
                trade_row[f"exit_price_{horizon_hours}h"] = exit_px
                trade_row[f"fade_debit_r_{horizon_hours}h"] = float(np.clip(-exit_extension_units, -1.0, 1.0))
                trade_row[f"follow_debit_r_{horizon_hours}h"] = float(np.clip(exit_extension_units, -1.0, 1.0))
                trade_row[f"fade_credit_r_{horizon_hours}h"] = float(
                    (BACKTEST_CREDIT_PREMIUM_UNITS - credit_intrinsic_units)
                    / (BACKTEST_CREDIT_WIDTH_UNITS - BACKTEST_CREDIT_PREMIUM_UNITS)
                )
                trade_row[f"long_straddle_raw_r_{horizon_hours}h"] = long_straddle_raw
                trade_row[f"long_straddle_r_{horizon_hours}h"] = float(
                    np.clip(long_straddle_raw, -1.0, BACKTEST_LONG_STRADDLE_CAP_R)
                )
                trade_row[f"adverse_extension_units_{horizon_hours}h"] = adverse_extension_units
                trade_row[f"favorable_extension_units_{horizon_hours}h"] = favorable_extension_units
                trade_row[f"contained_within_0_5x_shock_{horizon_hours}h"] = adverse_extension_units <= 0.5 + 1e-12
                trade_row[f"contained_within_1_0x_shock_{horizon_hours}h"] = adverse_extension_units <= 1.0 + 1e-12

            rows.append(trade_row)

    return pd.DataFrame(rows)


def summarize_strategy_subset(sub: pd.DataFrame, metric_col: str, horizon_hours: int) -> dict[str, Any]:
    metric = sub[metric_col].to_numpy(dtype=float)
    positive = metric[metric > 0]
    negative = metric[metric < 0]
    positive_sum = float(positive.sum()) if positive.size else 0.0
    negative_sum = float(np.abs(negative.sum())) if negative.size else 0.0

    return {
        "trade_count": int(len(sub)),
        "win_rate": float((metric > 0).mean()) if len(metric) else math.nan,
        "median_r": float(np.median(metric)) if len(metric) else math.nan,
        "mean_r": float(metric.mean()) if len(metric) else math.nan,
        "total_r": float(metric.sum()) if len(metric) else math.nan,
        "profit_factor": (positive_sum / negative_sum) if negative_sum > 0 else math.inf,
        "median_entry_abs_return": float(sub["entry_abs_return_from_baseline"].median()) if len(sub) else math.nan,
        "median_entry_abs_ret_60m_slot_percentile": (
            float(sub["entry_abs_ret_60m_slot_percentile"].median()) if len(sub) else math.nan
        ),
        f"contained_within_0_5x_shock_rate_{horizon_hours}h": (
            float(sub[f"contained_within_0_5x_shock_{horizon_hours}h"].mean()) if len(sub) else math.nan
        ),
        f"contained_within_1_0x_shock_rate_{horizon_hours}h": (
            float(sub[f"contained_within_1_0x_shock_{horizon_hours}h"].mean()) if len(sub) else math.nan
        ),
        f"median_adverse_extension_units_{horizon_hours}h": (
            float(sub[f"adverse_extension_units_{horizon_hours}h"].median()) if len(sub) else math.nan
        ),
        f"median_favorable_extension_units_{horizon_hours}h": (
            float(sub[f"favorable_extension_units_{horizon_hours}h"].median()) if len(sub) else math.nan
        ),
    }


def build_strategy_summary(
    trades: pd.DataFrame,
    group_cols: list[str],
    topic_bucket_order: list[str] | None = None,
) -> pd.DataFrame:
    if topic_bucket_order is None:
        topic_bucket_order = TOPIC_BUCKET_ORDER
    rows: list[dict[str, Any]] = []

    for threshold_label, threshold in BACKTEST_THRESHOLD_ORDER:
        thresholded = trades[trades["entry_abs_ret_60m_slot_percentile"].ge(threshold)].copy()
        for spec in BACKTEST_STRATEGY_SPECS:
            metric_col = spec["metric_col"]
            horizon_hours = int(spec["horizon_hours"])
            grouped = thresholded.dropna(subset=[metric_col]).groupby(group_cols, dropna=False)
            for keys, sub in grouped:
                if not isinstance(keys, tuple):
                    keys = (keys,)
                row = {
                    "strategy_name": spec["strategy_name"],
                    "family": spec["family"],
                    "horizon_hours": horizon_hours,
                    "threshold_label": threshold_label,
                    "min_entry_abs_ret_60m_slot_percentile": threshold,
                }
                row.update(dict(zip(group_cols, keys)))
                row.update(summarize_strategy_subset(sub, metric_col, horizon_hours))
                rows.append(row)

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    summary["threshold_label"] = pd.Categorical(
        summary["threshold_label"],
        categories=[label for label, _ in BACKTEST_THRESHOLD_ORDER],
        ordered=True,
    )
    if "timing_regime" in summary.columns:
        summary["timing_regime"] = pd.Categorical(
            summary["timing_regime"], categories=TIMING_REGIME_ORDER, ordered=True
        )
    if "topic_bucket" in summary.columns:
        summary["topic_bucket"] = pd.Categorical(summary["topic_bucket"], categories=topic_bucket_order, ordered=True)
    sort_cols = ["strategy_name", "threshold_label", *group_cols]
    return summary.sort_values(sort_cols).reset_index(drop=True)


def build_strategy_rankings(strategy_topic_symbol_summary: pd.DataFrame) -> pd.DataFrame:
    eligible = strategy_topic_symbol_summary[
        (strategy_topic_symbol_summary["timing_regime"] == "delayed")
        & (strategy_topic_symbol_summary["threshold_label"].isin(["p80", "p90"]))
        & (strategy_topic_symbol_summary["topic_bucket"] != TOPIC_OTHER)
        & (strategy_topic_symbol_summary["trade_count"] >= 30)
    ].copy()

    if eligible.empty:
        return eligible

    best = eligible.sort_values(["mean_r", "win_rate", "trade_count"], ascending=[False, False, False]).head(40).copy()
    best["ranking_bucket"] = "best"
    worst = eligible.sort_values(["mean_r", "win_rate", "trade_count"], ascending=[True, True, False]).head(40).copy()
    worst["ranking_bucket"] = "worst"
    return pd.concat([best, worst], ignore_index=True)


def build_futures_execution_signals(
    event_results: pd.DataFrame,
    market: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    delayed = event_results[
        (event_results["timing_regime"] == "delayed")
        & (event_results["symbol"].isin(FUTURES_EXECUTION_PROXY_MAP))
    ].copy()
    if delayed.empty:
        return pd.DataFrame()

    horizons = {
        f"{minutes}m": pd.Timedelta(minutes=minutes)
        for minutes in FUTURES_EXECUTION_ENTRY_WINDOWS_MINUTES
    }
    slot_baselines = {
        symbol: build_slot_baselines(market[symbol], horizons)
        for symbol in delayed["symbol"].drop_duplicates().tolist()
    }

    rows: list[dict[str, Any]] = []
    for proxy_symbol, sub in delayed.groupby("symbol", sort=False):
        market_df = market[proxy_symbol]
        meta = FUTURES_EXECUTION_PROXY_MAP[proxy_symbol]
        baselines = slot_baselines[proxy_symbol]
        index = market_df["timestamp_et"]
        closes = market_df["close"].to_numpy()

        for event in sub.itertuples(index=False):
            baseline_px = float(getattr(event, "baseline_price"))
            anchor_bar_ts = getattr(event, "anchor_bar_ts_et")
            event_ts = getattr(event, "event_ts_et")
            anchor_weekday = anchor_bar_ts.dayofweek
            anchor_slot = anchor_bar_ts.strftime("%H:%M")

            for entry_window_minutes in FUTURES_EXECUTION_ENTRY_WINDOWS_MINUTES:
                entry_label = f"{entry_window_minutes}m"
                entry_idx = index.searchsorted(anchor_bar_ts + pd.Timedelta(minutes=entry_window_minutes), side="left")
                if entry_idx >= len(market_df):
                    continue

                entry_ts = index.iloc[entry_idx]
                entry_px = float(closes[entry_idx])
                shock_px = entry_px - baseline_px
                if abs(shock_px) < 1e-12:
                    continue

                entry_ret = float(entry_px / baseline_px - 1.0)
                sample = baselines[entry_label].get((anchor_weekday, anchor_slot), np.array([]))

                rows.append(
                    {
                        "burst_id": getattr(event, "burst_id"),
                        "proxy_symbol": proxy_symbol,
                        "symbol": proxy_symbol,
                        "futures_symbol": meta["futures_symbol"],
                        "futures_product": meta["futures_product"],
                        "options_product": meta["options_product"],
                        "event_ts_et": event_ts,
                        "anchor_bar_ts_et": anchor_bar_ts,
                        "baseline_price": baseline_px,
                        "anchor_delay_minutes": float(getattr(event, "anchor_delay_minutes")),
                        "timing_regime": getattr(event, "timing_regime"),
                        "topic_bucket": getattr(event, "topic_bucket"),
                        "event_day_bucket": event_day_bucket(event_ts),
                        "is_weekend_event": event_day_bucket(event_ts) == "weekend",
                        "n_posts": int(getattr(event, "n_posts")),
                        "topic_is_ambiguous": bool(getattr(event, "topic_is_ambiguous")),
                        "entry_window_minutes": entry_window_minutes,
                        "entry_label": entry_label,
                        "entry_ts_et": entry_ts,
                        "entry_price": entry_px,
                        "shock_size_points": float(abs(shock_px)),
                        "shock_direction": "up" if shock_px > 0 else "down",
                        "fade_direction": "short" if shock_px > 0 else "long",
                        "entry_return_from_baseline": entry_ret,
                        "entry_abs_return_from_baseline": float(abs(entry_ret)),
                        "entry_ret_slot_median": math.nan if sample.size == 0 else float(np.median(sample)),
                        "entry_ret_slot_percentile": empirical_percentile(sample, entry_ret),
                        "entry_abs_ret_slot_percentile": (
                            empirical_percentile(np.abs(sample), abs(entry_ret)) if sample.size else math.nan
                        ),
                        "event_to_entry_minutes": float((entry_ts - event_ts).total_seconds() / 60.0),
                        "anchor_to_entry_minutes": float((entry_ts - anchor_bar_ts).total_seconds() / 60.0),
                    }
                )

    return pd.DataFrame(rows)


def evaluate_futures_execution_trade(
    market_df: pd.DataFrame,
    entry_ts: pd.Timestamp,
    baseline_px: float,
    entry_px: float,
    shock_direction: str,
    stop_units: float,
    time_stop_hours: int,
) -> dict[str, Any] | None:
    index = market_df["timestamp_et"]
    entry_idx = int(index.searchsorted(entry_ts, side="left"))
    if entry_idx >= len(market_df):
        return None

    shock_sign = 1.0 if shock_direction == "up" else -1.0
    shock_size = abs(entry_px - baseline_px)
    if shock_size < 1e-12:
        return None

    risk_distance = stop_units * shock_size
    target_price = baseline_px
    stop_price = entry_px + shock_sign * risk_distance
    planned_exit_idx = int(index.searchsorted(entry_ts + pd.Timedelta(hours=time_stop_hours), side="left"))
    if planned_exit_idx >= len(market_df):
        return None

    highs = market_df["high"].to_numpy()
    lows = market_df["low"].to_numpy()
    closes = market_df["close"].to_numpy()
    max_adverse_units = 0.0
    max_favorable_units = 0.0
    exit_reason = "time_stop"
    exit_ts = index.iloc[planned_exit_idx]
    exit_px = float(closes[planned_exit_idx])

    for idx in range(entry_idx + 1, planned_exit_idx + 1):
        bar_high = float(highs[idx])
        bar_low = float(lows[idx])
        bar_ts = index.iloc[idx]

        if shock_direction == "up":
            adverse_units = max(0.0, (bar_high - entry_px) / shock_size)
            favorable_units = max(0.0, (entry_px - bar_low) / shock_size)
            stop_hit = bar_high >= stop_price - 1e-12
            target_hit = bar_low <= target_price + 1e-12
        else:
            adverse_units = max(0.0, (entry_px - bar_low) / shock_size)
            favorable_units = max(0.0, (bar_high - entry_px) / shock_size)
            stop_hit = bar_low <= stop_price + 1e-12
            target_hit = bar_high >= target_price - 1e-12

        max_adverse_units = max(max_adverse_units, adverse_units)
        max_favorable_units = max(max_favorable_units, favorable_units)

        if stop_hit:
            exit_reason = "stop"
            exit_ts = bar_ts
            exit_px = float(stop_price)
            break
        if target_hit:
            exit_reason = "target"
            exit_ts = bar_ts
            exit_px = float(target_price)
            break

    fade_sign = -shock_sign
    r_multiple = float(fade_sign * (exit_px - entry_px) / risk_distance)
    return {
        "stop_units": float(stop_units),
        "time_stop_hours": int(time_stop_hours),
        "risk_distance_points": float(risk_distance),
        "risk_distance_abs_return": float(risk_distance / baseline_px),
        "stop_price": float(stop_price),
        "target_price": float(target_price),
        "reward_to_target_r": float(shock_size / risk_distance),
        "exit_reason": exit_reason,
        "exit_ts_et": exit_ts,
        "exit_price": float(exit_px),
        "hold_minutes": float((exit_ts - entry_ts).total_seconds() / 60.0),
        "r_multiple": r_multiple,
        "hit_target": exit_reason == "target",
        "hit_stop": exit_reason == "stop",
        "hit_time_stop": exit_reason == "time_stop",
        "max_adverse_units": float(max_adverse_units),
        "max_favorable_units": float(max_favorable_units),
    }


def build_futures_execution_trades(
    signals: pd.DataFrame,
    market: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for signal in signals.itertuples(index=False):
        market_df = market[getattr(signal, "proxy_symbol")]
        for stop_units in FUTURES_EXECUTION_STOP_UNITS:
            for time_stop_hours in FUTURES_EXECUTION_TIME_STOPS_HOURS:
                trade = evaluate_futures_execution_trade(
                    market_df=market_df,
                    entry_ts=getattr(signal, "entry_ts_et"),
                    baseline_px=float(getattr(signal, "baseline_price")),
                    entry_px=float(getattr(signal, "entry_price")),
                    shock_direction=str(getattr(signal, "shock_direction")),
                    stop_units=stop_units,
                    time_stop_hours=time_stop_hours,
                )
                if trade is None:
                    continue

                row = signal._asdict()
                row.update(trade)
                rows.append(row)

    return pd.DataFrame(rows)


def summarize_futures_execution_subset(sub: pd.DataFrame) -> dict[str, Any]:
    metric = sub["r_multiple"].to_numpy(dtype=float)
    positive = metric[metric > 0]
    negative = metric[metric < 0]
    positive_sum = float(positive.sum()) if positive.size else 0.0
    negative_sum = float(np.abs(negative.sum())) if negative.size else 0.0

    return {
        "trade_count": int(len(sub)),
        "win_rate": float((metric > 0).mean()) if len(metric) else math.nan,
        "median_r": float(np.median(metric)) if len(metric) else math.nan,
        "mean_r": float(metric.mean()) if len(metric) else math.nan,
        "total_r": float(metric.sum()) if len(metric) else math.nan,
        "profit_factor": (positive_sum / negative_sum) if negative_sum > 0 else math.inf,
        "target_rate": float(sub["hit_target"].mean()) if len(sub) else math.nan,
        "stop_rate": float(sub["hit_stop"].mean()) if len(sub) else math.nan,
        "time_stop_rate": float(sub["hit_time_stop"].mean()) if len(sub) else math.nan,
        "median_hold_minutes": float(sub["hold_minutes"].median()) if len(sub) else math.nan,
        "median_entry_abs_return": float(sub["entry_abs_return_from_baseline"].median()) if len(sub) else math.nan,
        "median_entry_abs_ret_slot_percentile": (
            float(sub["entry_abs_ret_slot_percentile"].median()) if len(sub) else math.nan
        ),
        "median_event_to_entry_minutes": float(sub["event_to_entry_minutes"].median()) if len(sub) else math.nan,
        "median_anchor_delay_minutes": float(sub["anchor_delay_minutes"].median()) if len(sub) else math.nan,
        "median_risk_distance_abs_return": float(sub["risk_distance_abs_return"].median()) if len(sub) else math.nan,
        "median_reward_to_target_r": float(sub["reward_to_target_r"].median()) if len(sub) else math.nan,
        "median_max_adverse_units": float(sub["max_adverse_units"].median()) if len(sub) else math.nan,
        "median_max_favorable_units": float(sub["max_favorable_units"].median()) if len(sub) else math.nan,
        "weekend_trade_share": float(sub["is_weekend_event"].mean()) if len(sub) else math.nan,
    }


def build_futures_execution_summary(
    trades: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for threshold_label, threshold in FUTURES_EXECUTION_THRESHOLD_ORDER:
        thresholded = trades[trades["entry_abs_ret_slot_percentile"].ge(threshold)].copy()
        grouped = thresholded.groupby(group_cols, dropna=False)
        for keys, sub in grouped:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {
                "threshold_label": threshold_label,
                "min_entry_abs_ret_slot_percentile": threshold,
            }
            row.update(dict(zip(group_cols, keys)))
            row.update(summarize_futures_execution_subset(sub))
            rows.append(row)

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    summary["threshold_label"] = pd.Categorical(
        summary["threshold_label"],
        categories=[label for label, _ in FUTURES_EXECUTION_THRESHOLD_ORDER],
        ordered=True,
    )
    if "event_day_bucket" in summary.columns:
        summary["event_day_bucket"] = pd.Categorical(
            summary["event_day_bucket"],
            categories=["weekday", "weekend"],
            ordered=True,
        )
    return summary.sort_values(["threshold_label", *group_cols]).reset_index(drop=True)


def build_futures_execution_rankings(config_summary: pd.DataFrame) -> pd.DataFrame:
    eligible = config_summary[
        (config_summary["threshold_label"].isin(["p80", "p90"]))
        & (config_summary["trade_count"] >= FUTURES_EXECUTION_MIN_TRADES)
    ].copy()
    if eligible.empty:
        return eligible

    best = eligible.sort_values(["mean_r", "win_rate", "trade_count"], ascending=[False, False, False]).head(24).copy()
    best["ranking_bucket"] = "best"
    worst = eligible.sort_values(["mean_r", "win_rate", "trade_count"], ascending=[True, True, False]).head(24).copy()
    worst["ranking_bucket"] = "worst"
    return pd.concat([best, worst], ignore_index=True)


def build_futures_execution_recommended_configs(config_summary: pd.DataFrame) -> pd.DataFrame:
    eligible = config_summary[
        (config_summary["threshold_label"].isin(["p80", "p90"]))
        & (config_summary["trade_count"] >= FUTURES_EXECUTION_MIN_TRADES)
    ].copy()
    if eligible.empty:
        return eligible

    recommended = (
        eligible.sort_values(
            [
                "futures_symbol",
                "mean_r",
                "win_rate",
                "trade_count",
                "time_stop_hours",
                "entry_window_minutes",
                "stop_units",
            ],
            ascending=[True, False, False, False, True, True, True],
        )
        .groupby("futures_symbol", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    recommended["selection_rule"] = "highest_mean_r_then_win_rate_then_trade_count_among_p80_p90_with_n>=30"
    return recommended


def build_futures_options_structure_map(recommended_configs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for rec in recommended_configs.itertuples(index=False):
        meta = FUTURES_EXECUTION_BY_FUTURES[getattr(rec, "futures_symbol")]
        time_stop_hours = int(getattr(rec, "time_stop_hours"))
        primary_family = "debit_spread" if time_stop_hours <= 12 else "credit_spread"
        secondary_family = "credit_spread" if primary_family == "debit_spread" else "debit_spread"

        rows.append(
            {
                "proxy_symbol": meta["proxy_symbol"],
                "futures_symbol": meta["futures_symbol"],
                "futures_product": meta["futures_product"],
                "options_product": meta["options_product"],
                "contract_unit": meta["contract_unit"],
                "study_proxy_note": f"Backtest uses {meta['proxy_symbol']} ETF bars as the tradable-price proxy for {meta['futures_symbol']}.",
                "recommended_threshold_label": getattr(rec, "threshold_label"),
                "recommended_entry_window_minutes": int(getattr(rec, "entry_window_minutes")),
                "recommended_stop_units": float(getattr(rec, "stop_units")),
                "recommended_time_stop_hours": time_stop_hours,
                "recommended_reward_to_target_r": float(getattr(rec, "median_reward_to_target_r")),
                "preferred_futures_trade_after_up_shock": f"Sell {meta['futures_symbol']} or use a bearish defined-risk structure.",
                "preferred_futures_trade_after_down_shock": f"Buy {meta['futures_symbol']} or use a bullish defined-risk structure.",
                "primary_options_structure_after_up_shock": (
                    "put_debit_spread" if primary_family == "debit_spread" else "call_credit_spread"
                ),
                "primary_options_structure_after_down_shock": (
                    "call_debit_spread" if primary_family == "debit_spread" else "put_credit_spread"
                ),
                "secondary_options_structure_after_up_shock": (
                    "call_credit_spread" if secondary_family == "credit_spread" else "put_debit_spread"
                ),
                "secondary_options_structure_after_down_shock": (
                    "put_credit_spread" if secondary_family == "credit_spread" else "call_debit_spread"
                ),
                "strike_mapping_note": (
                    "Heuristic only: align the defined-risk wing with the stop distance and aim the profit-taking wing at the pre-event baseline."
                ),
                "expiration_guidance": (
                    "Prefer the nearest liquid weekly or short-dated expiry with at least one full session remaining."
                    if time_stop_hours <= 12
                    else "Prefer the nearest liquid weekly or short-dated expiry with 2-7 calendar days remaining."
                ),
                "trading_hours_note": meta["hours_note"],
                "expirations_note": meta["expirations_note"],
                "product_url": meta["product_url"],
                "hours_url": meta["hours_url"],
                "mapping_is_backtested": False,
            }
        )

    return pd.DataFrame(rows)


def build_futures_execution_summary_payload(
    posts: pd.DataFrame,
    bursts: pd.DataFrame,
    event_results: pd.DataFrame,
    signals: pd.DataFrame,
    trades: pd.DataFrame,
    config_summary: pd.DataFrame,
    recommended_configs: pd.DataFrame,
    rankings: pd.DataFrame,
) -> dict[str, Any]:
    symbol_summary = (
        signals.groupby(["futures_symbol", "entry_window_minutes"])
        .size()
        .rename("signal_count")
        .reset_index()
        .sort_values(["futures_symbol", "entry_window_minutes"])
    )
    best = rankings[rankings["ranking_bucket"] == "best"].head(12).copy() if not rankings.empty else pd.DataFrame()
    worst = rankings[rankings["ranking_bucket"] == "worst"].head(12).copy() if not rankings.empty else pd.DataFrame()

    return {
        "reference_counts": build_summary(posts, bursts, event_results),
        "execution_assumptions": {
            "proxy_map": FUTURES_EXECUTION_PROXY_MAP,
            "timing_regime": "delayed only",
            "entry_windows_minutes": list(FUTURES_EXECUTION_ENTRY_WINDOWS_MINUTES),
            "thresholds": [
                {"label": label, "min_entry_abs_ret_slot_percentile": value}
                for label, value in FUTURES_EXECUTION_THRESHOLD_ORDER
            ],
            "stop_units": list(FUTURES_EXECUTION_STOP_UNITS),
            "time_stops_hours": list(FUTURES_EXECUTION_TIME_STOPS_HOURS),
            "profit_target": "first cross back through the pre-event baseline",
            "stop_priority": "If target and stop are both touched in the same 5-minute bar, count it as a stop.",
            "fill_model": "Enter at the close of the selected entry bar, then evaluate stops and targets from the next 5-minute bar onward.",
        },
        "signal_rows": int(len(signals)),
        "trade_rows": int(len(trades)),
        "signals_by_product_and_entry_window": symbol_summary.to_dict("records"),
        "recommended_configs": (
            recommended_configs[
                [
                    "futures_symbol",
                    "threshold_label",
                    "entry_window_minutes",
                    "stop_units",
                    "time_stop_hours",
                    "trade_count",
                    "win_rate",
                    "median_r",
                    "mean_r",
                ]
            ].to_dict("records")
            if not recommended_configs.empty
            else []
        ),
        "top_configs": (
            best[
                [
                    "futures_symbol",
                    "threshold_label",
                    "entry_window_minutes",
                    "stop_units",
                    "time_stop_hours",
                    "trade_count",
                    "win_rate",
                    "median_r",
                    "mean_r",
                ]
            ].to_dict("records")
            if not best.empty
            else []
        ),
        "worst_configs": (
            worst[
                [
                    "futures_symbol",
                    "threshold_label",
                    "entry_window_minutes",
                    "stop_units",
                    "time_stop_hours",
                    "trade_count",
                    "win_rate",
                    "median_r",
                    "mean_r",
                ]
            ].to_dict("records")
            if not worst.empty
            else []
        ),
    }


def build_backtest_summary(
    posts: pd.DataFrame,
    bursts: pd.DataFrame,
    event_results: pd.DataFrame,
    trades: pd.DataFrame,
    strategy_timing_summary: pd.DataFrame,
    strategy_rankings: pd.DataFrame,
) -> dict[str, Any]:
    timing_summary = strategy_timing_summary[
        (strategy_timing_summary["timing_regime"] == "delayed")
        & (strategy_timing_summary["threshold_label"].isin(["all", "p80", "p90"]))
    ].copy()
    timing_summary = timing_summary.sort_values(["mean_r", "win_rate", "trade_count"], ascending=[False, False, False])
    top_delayed = timing_summary.head(12).copy()

    rankings_best = strategy_rankings[strategy_rankings["ranking_bucket"] == "best"].head(12).copy()
    rankings_worst = strategy_rankings[strategy_rankings["ranking_bucket"] == "worst"].head(12).copy()

    return {
        "reference_counts": build_summary(posts, bursts, event_results),
        "backtest_assumptions": {
            "confirm_minutes": BACKTEST_CONFIRM_MINUTES,
            "thresholds": [{"label": label, "min_entry_abs_ret_60m_slot_percentile": value} for label, value in BACKTEST_THRESHOLD_ORDER],
            "exit_hours": list(BACKTEST_EXIT_HOURS),
            "credit_proxy": {
                "short_strike_distance_shock_units": BACKTEST_CREDIT_SHORT_UNITS,
                "spread_width_shock_units": BACKTEST_CREDIT_WIDTH_UNITS,
                "credit_fraction_of_width": BACKTEST_CREDIT_PREMIUM_UNITS,
            },
            "long_straddle_proxy": {
                "premium_proxy": "one initial shock unit",
                "capped_r_multiple": BACKTEST_LONG_STRADDLE_CAP_R,
            },
        },
        "strategy_trade_rows": int(len(trades)),
        "weekend_trade_share": float(trades["is_weekend_event"].mean()) if not trades.empty else math.nan,
        "top_delayed_strategy_configs": top_delayed[
            ["strategy_name", "threshold_label", "trade_count", "win_rate", "median_r", "mean_r"]
        ].to_dict("records"),
        "top_topic_symbol_slices": rankings_best[
            ["strategy_name", "threshold_label", "topic_bucket", "symbol", "trade_count", "win_rate", "median_r", "mean_r"]
        ].to_dict("records"),
        "worst_topic_symbol_slices": rankings_worst[
            ["strategy_name", "threshold_label", "topic_bucket", "symbol", "trade_count", "win_rate", "median_r", "mean_r"]
        ].to_dict("records"),
    }


def analyze_pipeline(
    posts_csv: Path,
    market_dir: Path,
    output_dir: Path,
    symbols: list[str],
) -> None:
    posts, bursts, _market, event_results = prepare_study_artifacts(posts_csv, market_dir, symbols)
    write_study_outputs(output_dir, posts, bursts, event_results, symbols)


def backtest_strategy_pipeline(
    posts_csv: Path,
    market_dir: Path,
    output_dir: Path,
    symbols: list[str],
) -> None:
    posts, bursts, market, event_results = prepare_study_artifacts(posts_csv, market_dir, symbols)
    write_study_outputs(output_dir, posts, bursts, event_results, symbols, prefix="reference")

    trades = build_strategy_trades(event_results, market, confirm_minutes=BACKTEST_CONFIRM_MINUTES)
    strategy_timing_summary = build_strategy_summary(trades, ["timing_regime"])
    strategy_symbol_summary = build_strategy_summary(trades, ["timing_regime", "symbol"])
    strategy_topic_symbol_summary = build_strategy_summary(
        trades,
        ["timing_regime", "topic_bucket", "symbol"],
    )
    strategy_weekend_summary = build_strategy_summary(
        trades,
        ["timing_regime", "event_day_bucket", "symbol"],
    )
    strategy_rankings = build_strategy_rankings(strategy_topic_symbol_summary)
    backtest_summary = build_backtest_summary(
        posts,
        bursts,
        event_results,
        trades,
        strategy_timing_summary,
        strategy_rankings,
    )

    trades.to_csv(output_dir / "strategy_trade_log.csv", index=False)
    strategy_timing_summary.to_csv(output_dir / "strategy_timing_summary.csv", index=False)
    strategy_symbol_summary.to_csv(output_dir / "strategy_symbol_summary.csv", index=False)
    strategy_topic_symbol_summary.to_csv(output_dir / "strategy_topic_symbol_summary.csv", index=False)
    strategy_weekend_summary.to_csv(output_dir / "strategy_weekend_summary.csv", index=False)
    strategy_rankings.to_csv(output_dir / "strategy_best_and_worst_slices.csv", index=False)
    (output_dir / "strategy_assumptions.json").write_text(
        json.dumps(
            {
                "confirm_minutes": BACKTEST_CONFIRM_MINUTES,
                "thresholds": [{"label": label, "min_entry_abs_ret_60m_slot_percentile": value} for label, value in BACKTEST_THRESHOLD_ORDER],
                "exit_hours": list(BACKTEST_EXIT_HOURS),
                "long_straddle_cap_r": BACKTEST_LONG_STRADDLE_CAP_R,
                "credit_proxy": {
                    "short_strike_distance_shock_units": BACKTEST_CREDIT_SHORT_UNITS,
                    "spread_width_shock_units": BACKTEST_CREDIT_WIDTH_UNITS,
                    "credit_fraction_of_width": BACKTEST_CREDIT_PREMIUM_UNITS,
                },
                "strategies": list(BACKTEST_STRATEGY_SPECS),
            },
            indent=2,
        )
    )
    (output_dir / "backtest_summary.json").write_text(json.dumps(backtest_summary, indent=2))


def backtest_futures_execution_pipeline(
    posts_csv: Path,
    market_dir: Path,
    output_dir: Path,
    symbols: list[str],
) -> None:
    posts, bursts, market, event_results = prepare_study_artifacts(posts_csv, market_dir, symbols)
    output_dir.mkdir(parents=True, exist_ok=True)

    signals = build_futures_execution_signals(event_results, market)
    trades = build_futures_execution_trades(signals, market)
    symbol_summary = build_futures_execution_summary(trades, ["futures_symbol"])
    config_summary = build_futures_execution_summary(
        trades,
        ["futures_symbol", "entry_window_minutes", "stop_units", "time_stop_hours"],
    )
    weekend_summary = build_futures_execution_summary(
        trades,
        ["futures_symbol", "event_day_bucket", "entry_window_minutes", "stop_units", "time_stop_hours"],
    )
    rankings = build_futures_execution_rankings(config_summary)
    recommended_configs = build_futures_execution_recommended_configs(config_summary)
    structure_map = build_futures_options_structure_map(recommended_configs)
    execution_summary = build_futures_execution_summary_payload(
        posts,
        bursts,
        event_results,
        signals,
        trades,
        config_summary,
        recommended_configs,
        rankings,
    )

    signals.to_csv(output_dir / "execution_signals.csv", index=False)
    trades.to_csv(output_dir / "execution_trade_log.csv", index=False)
    symbol_summary.to_csv(output_dir / "execution_symbol_summary.csv", index=False)
    config_summary.to_csv(output_dir / "execution_config_summary.csv", index=False)
    weekend_summary.to_csv(output_dir / "execution_weekend_summary.csv", index=False)
    rankings.to_csv(output_dir / "execution_best_and_worst_configs.csv", index=False)
    recommended_configs.to_csv(output_dir / "execution_recommended_configs.csv", index=False)
    structure_map.to_csv(output_dir / "futures_options_structure_map.csv", index=False)
    (output_dir / "reference_summary.json").write_text(json.dumps(build_summary(posts, bursts, event_results), indent=2))
    (output_dir / "execution_assumptions.json").write_text(
        json.dumps(
            {
                "proxy_map": FUTURES_EXECUTION_PROXY_MAP,
                "entry_windows_minutes": list(FUTURES_EXECUTION_ENTRY_WINDOWS_MINUTES),
                "thresholds": [
                    {"label": label, "min_entry_abs_ret_slot_percentile": value}
                    for label, value in FUTURES_EXECUTION_THRESHOLD_ORDER
                ],
                "stop_units": list(FUTURES_EXECUTION_STOP_UNITS),
                "time_stops_hours": list(FUTURES_EXECUTION_TIME_STOPS_HOURS),
                "profit_target": "pre-event baseline cross",
                "stop_logic": "5-minute high/low intrabar stop detection with stop-first tie-break",
            },
            indent=2,
        )
    )
    (output_dir / "execution_summary.json").write_text(json.dumps(execution_summary, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Trump's Truth archive and run an IBKR event study.")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape-posts", help="Scrape the public archive into CSV.")
    scrape.add_argument("--output", type=Path, default=Path("data/trump_truth_posts.csv"))
    scrape.add_argument("--max-pages", type=int, default=None)
    scrape.add_argument("--start-date", default=None)
    scrape.add_argument("--end-date", default=None)

    fetch = sub.add_parser("fetch-market", help="Fetch 5-minute ETF history from TWS.")
    fetch.add_argument("--output-dir", type=Path, default=Path("data/market_5m"))
    fetch.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    fetch.add_argument("--start-date-et", default="2022-02-14")
    fetch.add_argument("--end-date-et", default=pd.Timestamp.now(tz="UTC").tz_convert(TZ_ET).strftime("%Y-%m-%d"))
    fetch.add_argument("--host", default="127.0.0.1")
    fetch.add_argument("--port", type=int, default=7496)
    fetch.add_argument("--client-id", type=int, default=9200)
    fetch.add_argument("--use-rth", type=int, default=0)
    fetch.add_argument("--duration", default="2 M")
    fetch.add_argument("--min-interval-seconds", type=float, default=10.5)

    analyze = sub.add_parser("analyze", help="Run the event study from scraped posts and market data.")
    analyze.add_argument("--posts-csv", type=Path, default=Path("data/trump_truth_posts.csv"))
    analyze.add_argument("--market-dir", type=Path, default=Path("data/market_5m"))
    analyze.add_argument("--output-dir", type=Path, default=Path("outputs"))
    analyze.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)

    backtest = sub.add_parser(
        "backtest-strategy",
        help="Build a topic-aware event-driven strategy backtest from scraped posts and market data.",
    )
    backtest.add_argument("--posts-csv", type=Path, default=Path("data/trump_truth_posts.csv"))
    backtest.add_argument("--market-dir", type=Path, default=Path("data/market_5m"))
    backtest.add_argument("--output-dir", type=Path, default=Path("outputs_strategy_v1"))
    backtest.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)

    futures_execution = sub.add_parser(
        "backtest-futures-execution",
        help="Build a stricter delayed-event execution study for MNQ/MES/CL using ETF proxy bars.",
    )
    futures_execution.add_argument("--posts-csv", type=Path, default=Path("data/trump_truth_posts.csv"))
    futures_execution.add_argument("--market-dir", type=Path, default=Path("data/market_5m"))
    futures_execution.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs_strategy_v1") / FUTURES_EXECUTION_OUTPUT_SUBDIR,
    )
    futures_execution.add_argument("--symbols", nargs="*", default=["SPY", "QQQ", "USO"])

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "scrape-posts":
        scrape_archive(
            args.output,
            max_pages=args.max_pages,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        return 0
    if args.command == "fetch-market":
        fetch_market_history(
            output_dir=args.output_dir,
            symbols=args.symbols,
            start_date_et=args.start_date_et,
            end_date_et=args.end_date_et,
            host=args.host,
            port=args.port,
            client_id=args.client_id,
            use_rth=args.use_rth,
            duration=args.duration,
            min_interval_seconds=args.min_interval_seconds,
        )
        return 0
    if args.command == "analyze":
        analyze_pipeline(
            posts_csv=args.posts_csv,
            market_dir=args.market_dir,
            output_dir=args.output_dir,
            symbols=args.symbols,
        )
        return 0
    if args.command == "backtest-strategy":
        backtest_strategy_pipeline(
            posts_csv=args.posts_csv,
            market_dir=args.market_dir,
            output_dir=args.output_dir,
            symbols=args.symbols,
        )
        return 0
    if args.command == "backtest-futures-execution":
        backtest_futures_execution_pipeline(
            posts_csv=args.posts_csv,
            market_dir=args.market_dir,
            output_dir=args.output_dir,
            symbols=args.symbols,
        )
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
