#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from truth_event_study import (  # noqa: E402
    FUTURES_EXECUTION_PROXY_MAP,
    TOPIC_BUCKET_ORDER,
    TOPIC_OTHER,
    TZ_ET,
    USER_AGENT,
    build_archive_url,
    classify_burst_topic,
    empirical_percentile,
    ensure_parent,
    normalize_space,
)


DEFAULT_POLL_SECONDS = 300
DEFAULT_PER_PAGE = 40
DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MIN_GEMINI_CONFIDENCE = 0.75
DEFAULT_TWS_HOST = "127.0.0.1"
DEFAULT_TWS_PORT = 7496
DEFAULT_TWS_CLIENT_ID = 9471
DEFAULT_ACTIONABLE_STRATEGY_NAME = "fade_credit_24h"
DEFAULT_ACTIONABLE_THRESHOLD = "p80"
DEFAULT_ACTIONABLE_MIN_TRADES = 30
DEFAULT_ACTIONABLE_MIN_MEAN_R = 0.20
DEFAULT_VALIDATION_PERCENTILE = 0.90
DEFAULT_STATE_PATH = REPO_ROOT / "realtime_post_bot" / "bot_state.json"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs_strategy_v1"
DEFAULT_LOG_PATH = REPO_ROOT / "realtime_post_bot" / "trump_post_signal_bot.log"
EARLIEST_SORT_TS = pd.Timestamp("2000-01-01", tz=TZ_ET)

OUTPUT_SYMBOL_ORDER = ["QQQ", "SPY", "USO"]
LOGGER = logging.getLogger("trump_post_signal_bot")


@dataclass
class GeminiDecision:
    category: str
    confidence: float
    ambiguous: bool
    reasoning_short: str
    model: str
    raw_text: str
    used_fallback: bool = False


@dataclass
class TwsStatus:
    online: bool
    detail: str
    server_time_epoch: int | None = None


class IBPingClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.done = threading.Event()
        self.current_time_epoch: int | None = None
        self.errors: list[tuple[int, int, str]] = []

    def currentTime(self, time_: int) -> None:  # noqa: N802
        self.current_time_epoch = int(time_)
        self.done.set()

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        self.errors.append((reqId, errorCode, errorString))
        if errorCode not in (2104, 2106, 2158):
            self.done.set()


def setup_file_logger(log_file: Path) -> None:
    ensure_parent(log_file)
    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.propagate = False


def post_key(post: dict[str, Any]) -> str:
    return (
        f"status_id={post.get('archive_status_id')} "
        f"displayed_time_et={post.get('displayed_time_et')} "
        f"url={post.get('archive_status_url')}"
    )


def parse_displayed_time_et(displayed_time_et: str) -> pd.Timestamp | None:
    naive = pd.to_datetime(displayed_time_et, format="%B %d, %Y, %I:%M %p", errors="coerce")
    if pd.isna(naive):
        return None
    try:
        localized = naive.tz_localize(TZ_ET, ambiguous="raise", nonexistent="shift_forward")
    except Exception:
        localized = naive.tz_localize(TZ_ET, ambiguous=False, nonexistent="shift_forward")
    return pd.Timestamp(localized)


def fetch_latest_original_posts(session: requests.Session, per_page: int = DEFAULT_PER_PAGE) -> list[dict[str, Any]]:
    url = build_archive_url(per_page=per_page, sort="desc")
    response = session.get(url, timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    statuses = soup.select_one(".statuses")
    if statuses is None:
        raise RuntimeError("Could not find status container on archive page")

    records: list[dict[str, Any]] = []
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
        archive_status_id: int | None = None
        if archive_status_url:
            parts = archive_status_url.rstrip("/").split("/")
            try:
                archive_status_id = int(parts[-1])
            except (ValueError, IndexError):
                archive_status_id = None

        record = {
            "archive_status_id": archive_status_id,
            "archive_status_url": archive_status_url,
            "handle": handle,
            "displayed_time_et": time_text,
            "parsed_time_et": parse_displayed_time_et(time_text),
            "is_reblog_event": bool(pending_reblog),
            "content_text": normalize_space(content_node.get_text(" ", strip=True)) if content_node else "",
            "external_link_label": normalize_space(external_link.get_text(" ", strip=True)) if external_link else "",
            "external_link_url": external_link.get("href", "").strip() if external_link else "",
            "status_card_text": normalize_space(status_card.get_text(" ", strip=True)) if status_card else "",
            "status_card_url": status_card.get("href", "").strip() if status_card else "",
            "attachment_count": len(child.select(".status-attachment")),
        }
        pending_reblog = False
        if record["handle"] == "@realDonaldTrump" and not record["is_reblog_event"]:
            records.append(record)

    deduped: dict[int | str, dict[str, Any]] = {}
    for record in records:
        key = record["archive_status_id"] if record["archive_status_id"] is not None else record["archive_status_url"]
        deduped[key] = record

    out = list(deduped.values())
    out.sort(
        key=lambda row: (
            row["parsed_time_et"] if row["parsed_time_et"] is not None else EARLIEST_SORT_TS,
            row["archive_status_id"] or -1,
        ),
        reverse=True,
    )
    return out


def choose_classification_text(post: dict[str, Any]) -> tuple[str, str]:
    content_text = normalize_space(str(post.get("content_text", "")))
    status_card_text = normalize_space(str(post.get("status_card_text", "")))
    external_link_label = normalize_space(str(post.get("external_link_label", "")))
    if external_link_label.lower() == "original post":
        external_link_label = ""

    if content_text:
        return content_text, "content_text"
    if status_card_text:
        return status_card_text, "status_card_text"
    if external_link_label:
        return external_link_label, "external_link_label"
    return "", "empty"


def has_usable_text(post: dict[str, Any]) -> bool:
    text, _ = choose_classification_text(post)
    return bool(text)


def parse_gemini_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(t for t in texts if t).strip()


def classify_with_gemini(
    session: requests.Session,
    api_key: str,
    model: str,
    text: str,
    timeout_seconds: float,
) -> GeminiDecision:
    if not text:
        return GeminiDecision(
            category=TOPIC_OTHER,
            confidence=0.0,
            ambiguous=False,
            reasoning_short="No text was exposed by the archive page.",
            model=model,
            raw_text="",
            used_fallback=True,
        )

    prompt = (
        "Classify this Donald Trump Truth Social post into exactly one category.\n"
        "Valid categories: tariffs_trade, war_geopolitics, oil_gas_energy, fed_inflation_rates, "
        "immigration_border, domestic_politics_attacks, other.\n"
        "Use 'other' when the text is ambiguous, weakly related, or does not clearly fit one bucket.\n"
        "Return JSON only with keys: category, confidence, ambiguous, reasoning_short.\n\n"
        "Category guidance:\n"
        "- tariffs_trade: tariffs, duties, imports, trade deals, trade barriers, trade deficits.\n"
        "- war_geopolitics: Ukraine/Russia, Israel/Iran/Gaza, missiles, ceasefire, hostages, nuclear, broader war/geopolitics.\n"
        "- oil_gas_energy: oil, crude, gasoline, natural gas, LNG, drilling, pipelines, OPEC, energy production.\n"
        "- fed_inflation_rates: Fed, Powell, inflation, interest rates, CPI, PCE, mortgage rates.\n"
        "- immigration_border: border, immigration, migrants, asylum, deportation, cartels, fentanyl.\n"
        "- domestic_politics_attacks: attacks on domestic political/media/legal opponents, fake news, witch hunt, rigged election.\n"
        f"\nPost text:\n{text}"
    )
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are a conservative classifier for a financial event-study bot. "
                        "Do not guess. If the text is not clearly in one bucket, choose other."
                    )
                }
            ]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = session.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    response_json = response.json()
    raw_text = parse_gemini_text(response_json)
    parsed = json.loads(raw_text) if raw_text else {}

    category = str(parsed.get("category", TOPIC_OTHER)).strip()
    if category not in TOPIC_BUCKET_ORDER:
        category = TOPIC_OTHER

    confidence_raw = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    return GeminiDecision(
        category=category,
        confidence=confidence,
        ambiguous=bool(parsed.get("ambiguous", False)),
        reasoning_short=normalize_space(str(parsed.get("reasoning_short", ""))),
        model=model,
        raw_text=raw_text,
    )


def fallback_gemini_decision(text: str) -> GeminiDecision:
    deterministic = classify_burst_topic(text)
    return GeminiDecision(
        category=str(deterministic["topic_bucket"]),
        confidence=1.0 if deterministic["topic_bucket"] != TOPIC_OTHER else 0.0,
        ambiguous=bool(deterministic["topic_is_ambiguous"]),
        reasoning_short="Deterministic fallback from the study rules.",
        model="deterministic_rules",
        raw_text=json.dumps(deterministic),
        used_fallback=True,
    )


def finalize_category(
    gemini: GeminiDecision,
    deterministic_meta: dict[str, Any],
    min_confidence: float,
) -> str:
    if gemini.used_fallback:
        return gemini.category
    if gemini.ambiguous:
        return TOPIC_OTHER
    if gemini.category not in TOPIC_BUCKET_ORDER:
        return TOPIC_OTHER
    if gemini.category != TOPIC_OTHER and gemini.confidence < min_confidence:
        return TOPIC_OTHER
    if deterministic_meta["topic_bucket"] != TOPIC_OTHER and gemini.category == TOPIC_OTHER:
        return str(deterministic_meta["topic_bucket"])
    return gemini.category


def check_tws_online(
    host: str,
    port: int,
    client_id: int,
    timeout_seconds: float = 6.0,
) -> TwsStatus:
    client = IBPingClient()
    thread: threading.Thread | None = None
    try:
        client.connect(host, port, clientId=client_id)
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        time.sleep(1.0)
        if not client.isConnected():
            return TwsStatus(online=False, detail=f"connection to {host}:{port} failed")
        client.reqCurrentTime()
        finished = client.done.wait(timeout_seconds)
        if finished and client.current_time_epoch is not None:
            return TwsStatus(
                online=True,
                detail=f"connected to {host}:{port}",
                server_time_epoch=client.current_time_epoch,
            )
        if client.errors:
            last_error = client.errors[-1]
            return TwsStatus(online=False, detail=f"TWS error {last_error[1]}: {last_error[2]}")
        return TwsStatus(online=False, detail=f"timed out waiting for TWS response on {host}:{port}")
    except Exception as exc:
        return TwsStatus(online=False, detail=f"TWS check failed: {exc}")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    with state_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    ensure_parent(state_path)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    LOGGER.info("state_saved path=%s last_seen_status_id=%s", state_path, state.get("last_seen_status_id"))


def load_validation_watch_map(outputs_root: Path) -> dict[str, list[dict[str, Any]]]:
    strategy_summary = pd.read_csv(outputs_root / "strategy_topic_symbol_summary.csv")
    events = pd.read_csv(outputs_root / "reference_event_level_market_reaction.csv")
    recommended = pd.read_csv(outputs_root / "futures_execution_v1" / "execution_recommended_configs.csv")

    recommended_map = {
        row["futures_symbol"]: row
        for _, row in recommended.iterrows()
    }

    selected = strategy_summary[
        (strategy_summary["strategy_name"] == DEFAULT_ACTIONABLE_STRATEGY_NAME)
        & (strategy_summary["timing_regime"] == "delayed")
        & (strategy_summary["threshold_label"] == DEFAULT_ACTIONABLE_THRESHOLD)
        & (strategy_summary["trade_count"] >= DEFAULT_ACTIONABLE_MIN_TRADES)
        & (strategy_summary["mean_r"] >= DEFAULT_ACTIONABLE_MIN_MEAN_R)
        & (strategy_summary["topic_bucket"] != TOPIC_OTHER)
        & (strategy_summary["symbol"].isin(OUTPUT_SYMBOL_ORDER))
    ].copy()

    delayed_events = events[events["timing_regime"] == "delayed"].copy()
    watch_map: dict[str, list[dict[str, Any]]] = {}

    for row in selected.itertuples(index=False):
        topic = str(row.topic_bucket)
        proxy_symbol = str(row.symbol)
        event_slice = delayed_events[
            (delayed_events["topic_bucket"] == topic)
            & (delayed_events["symbol"] == proxy_symbol)
        ].copy()
        abs_ret = event_slice["ret_60m"].abs().dropna()
        if abs_ret.empty:
            continue

        meta = FUTURES_EXECUTION_PROXY_MAP[proxy_symbol]
        futures_symbol = meta["futures_symbol"]
        recommended_row = recommended_map.get(futures_symbol, {})
        watch = {
            "topic_bucket": topic,
            "proxy_symbol": proxy_symbol,
            "futures_symbol": futures_symbol,
            "trade_count": int(row.trade_count),
            "win_rate": float(row.win_rate),
            "mean_r": float(row.mean_r),
            "validation_abs_move_pct_60m": float(abs_ret.quantile(DEFAULT_VALIDATION_PERCENTILE) * 100.0),
            "median_abs_move_pct_60m": float(abs_ret.median() * 100.0),
            "recommended_entry_window_minutes": int(recommended_row.get("entry_window_minutes", 60)),
            "recommended_stop_units": float(recommended_row.get("stop_units", 0.75)),
            "recommended_time_stop_hours": int(recommended_row.get("time_stop_hours", 24)),
        }
        watch_map.setdefault(topic, []).append(watch)

    for topic, watches in watch_map.items():
        watches.sort(key=lambda item: (item["mean_r"], item["trade_count"]), reverse=True)
    return watch_map


def format_watch_line(watch: dict[str, Any]) -> str:
    suffix = (
        ""
        if watch["recommended_entry_window_minutes"] == 60
        else f" note: strict futures template preferred {watch['recommended_entry_window_minutes']}m entry"
    )
    return (
        f"- {watch['futures_symbol']} / {watch['proxy_symbol']}: need about "
        f"{watch['validation_abs_move_pct_60m']:.2f}% absolute move from the pre-event baseline "
        f"in the first 60m; strict template stop {watch['recommended_stop_units']:.2f}x shock, "
        f"time stop {watch['recommended_time_stop_hours']}h.{suffix}"
    )


def analyze_post(
    post: dict[str, Any],
    watch_map: dict[str, list[dict[str, Any]]],
    session: requests.Session,
    gemini_model: str,
    gemini_timeout_seconds: float,
    min_gemini_confidence: float,
    tws_host: str,
    tws_port: int,
    tws_client_id: int,
) -> dict[str, Any]:
    text, text_source = choose_classification_text(post)
    deterministic_meta = classify_burst_topic(text)
    try:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini classification")
        gemini = classify_with_gemini(
            session=session,
            api_key=api_key,
            model=gemini_model,
            text=text,
            timeout_seconds=gemini_timeout_seconds,
        )
    except Exception as exc:
        gemini = fallback_gemini_decision(text)
        gemini.reasoning_short = f"Gemini call failed, used deterministic fallback: {exc}"

    final_category = finalize_category(gemini, deterministic_meta, min_gemini_confidence)
    tradable_watches = watch_map.get(final_category, [])
    tws_status: TwsStatus | None = None
    if tradable_watches:
        tws_status = check_tws_online(
            host=tws_host,
            port=tws_port,
            client_id=tws_client_id + int(post["archive_status_id"] or 0) % 97,
        )

    return {
        "text": text,
        "text_source": text_source,
        "deterministic_meta": deterministic_meta,
        "gemini": gemini,
        "final_category": final_category,
        "tradable_watches": tradable_watches,
        "tws_status": tws_status,
    }


def bootstrap_state_if_needed(
    posts: list[dict[str, Any]],
    state_path: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    if state.get("last_seen_status_id") is not None:
        return state
    latest_id = max(
        (post["archive_status_id"] for post in posts if post.get("archive_status_id") is not None),
        default=None,
    )
    state["last_seen_status_id"] = latest_id
    state["bootstrapped_at"] = pd.Timestamp.now(tz=TZ_ET).isoformat()
    save_state(state_path, state)
    LOGGER.info("bootstrap seeded last_seen_status_id=%s", latest_id)
    print(
        f"[bootstrap] seeded last_seen_status_id={latest_id}; no historical alerts emitted",
        flush=True,
    )
    return state


def emit_post_summary(
    post: dict[str, Any],
    text: str,
    text_source: str,
    gemini: GeminiDecision,
    deterministic_meta: dict[str, Any],
    final_category: str,
    tradable_watches: list[dict[str, Any]],
    tws_status: TwsStatus | None,
    header_label: str = "[post]",
    emit_bell: bool = True,
) -> None:
    posted_at = post["parsed_time_et"].isoformat() if post.get("parsed_time_et") is not None else post["displayed_time_et"]
    if emit_bell and tradable_watches:
        print("\a", end="", flush=True)
    print(
        f"{header_label} status_id={post.get('archive_status_id')} posted_at_et={posted_at} "
        f"final_category={final_category} tradable={bool(tradable_watches)}",
        flush=True,
    )
    print(f"source={text_source}", flush=True)
    print(f"text={text if text else '[no text exposed by archive page]'}", flush=True)
    print(
        f"gemini_category={gemini.category} gemini_confidence={gemini.confidence:.2f} "
        f"gemini_ambiguous={gemini.ambiguous} gemini_model={gemini.model}",
        flush=True,
    )
    if gemini.reasoning_short:
        print(f"gemini_reasoning={gemini.reasoning_short}", flush=True)
    print(
        f"rule_category={deterministic_meta['topic_bucket']} "
        f"rule_ambiguous={deterministic_meta['topic_is_ambiguous']} "
        f"rule_triggers={deterministic_meta['topic_trigger_terms'] or '[none]'}",
        flush=True,
    )

    if tradable_watches:
        print("validation_watch=", flush=True)
        if tws_status is not None:
            print(
                f"TWS online={tws_status.online} detail={tws_status.detail}",
                flush=True,
            )
        if tws_status is not None and tws_status.online:
            for watch in tradable_watches:
                print(format_watch_line(watch), flush=True)
        else:
            print("- TWS offline or unreachable, so validation watch levels were not emitted.", flush=True)
    print("", flush=True)


def process_new_posts(
    posts: list[dict[str, Any]],
    state: dict[str, Any],
    state_path: Path,
    watch_map: dict[str, list[dict[str, Any]]],
    session: requests.Session,
    gemini_model: str,
    gemini_timeout_seconds: float,
    min_gemini_confidence: float,
    tws_host: str,
    tws_port: int,
    tws_client_id: int,
    preview_latest: bool = False,
) -> dict[str, Any]:
    previewed_status_id: int | None = None
    if preview_latest and posts:
        latest_text_post = next((post for post in posts if has_usable_text(post)), None)
        if latest_text_post is not None:
            latest_analysis = analyze_post(
                post=latest_text_post,
                watch_map=watch_map,
                session=session,
                gemini_model=gemini_model,
                gemini_timeout_seconds=gemini_timeout_seconds,
                min_gemini_confidence=min_gemini_confidence,
                tws_host=tws_host,
                tws_port=tws_port,
                tws_client_id=tws_client_id,
            )
            LOGGER.info(
                "startup_preview %s final_category=%s tradable=%s text_source=%s",
                post_key(latest_text_post),
                latest_analysis["final_category"],
                bool(latest_analysis["tradable_watches"]),
                latest_analysis["text_source"],
            )
            emit_post_summary(
                post=latest_text_post,
                text=latest_analysis["text"],
                text_source=latest_analysis["text_source"],
                gemini=latest_analysis["gemini"],
                deterministic_meta=latest_analysis["deterministic_meta"],
                final_category=latest_analysis["final_category"],
                tradable_watches=latest_analysis["tradable_watches"],
                tws_status=latest_analysis["tws_status"],
                header_label="[startup]",
                emit_bell=False,
            )
            previewed_status_id = latest_text_post.get("archive_status_id")
        else:
            LOGGER.info("startup_preview skipped reason=no_usable_text_post_in_current_page")

    state = bootstrap_state_if_needed(posts, state_path, state)
    last_seen_status_id = state.get("last_seen_status_id")
    baseline_seen_status_id = int(last_seen_status_id) if last_seen_status_id is not None else -1
    highest_seen_status_id = baseline_seen_status_id
    if previewed_status_id is not None and previewed_status_id > highest_seen_status_id:
        highest_seen_status_id = int(previewed_status_id)
    unseen = [
        post
        for post in posts
        if (
            post.get("archive_status_id") is not None
            and post["archive_status_id"] > baseline_seen_status_id
            and post["archive_status_id"] != previewed_status_id
        )
    ]
    unseen.sort(
        key=lambda row: (
            row["parsed_time_et"] if row["parsed_time_et"] is not None else EARLIEST_SORT_TS,
            row["archive_status_id"],
        )
    )

    if not unseen:
        return state

    for post in unseen:
        text, text_source = choose_classification_text(post)
        if not text:
            LOGGER.info("suppressed_no_text %s text_source=%s", post_key(post), text_source)
            highest_seen_status_id = max(highest_seen_status_id, int(post["archive_status_id"]))
            state["last_processed_at"] = pd.Timestamp.now(tz=TZ_ET).isoformat()
            continue

        analysis = analyze_post(
            post=post,
            watch_map=watch_map,
            session=session,
            gemini_model=gemini_model,
            gemini_timeout_seconds=gemini_timeout_seconds,
            min_gemini_confidence=min_gemini_confidence,
            tws_host=tws_host,
            tws_port=tws_port,
            tws_client_id=tws_client_id,
        )
        LOGGER.info(
            "processed_post %s final_category=%s tradable=%s text_source=%s gemini_category=%s gemini_confidence=%.2f",
            post_key(post),
            analysis["final_category"],
            bool(analysis["tradable_watches"]),
            analysis["text_source"],
            analysis["gemini"].category,
            analysis["gemini"].confidence,
        )
        if analysis["tws_status"] is not None:
            LOGGER.info(
                "tws_check_for_post %s online=%s detail=%s",
                post_key(post),
                analysis["tws_status"].online,
                analysis["tws_status"].detail,
            )
        emit_post_summary(
            post=post,
            text=analysis["text"],
            text_source=analysis["text_source"],
            gemini=analysis["gemini"],
            deterministic_meta=analysis["deterministic_meta"],
            final_category=analysis["final_category"],
            tradable_watches=analysis["tradable_watches"],
            tws_status=analysis["tws_status"],
        )
        highest_seen_status_id = max(highest_seen_status_id, int(post["archive_status_id"]))
        state["last_processed_at"] = pd.Timestamp.now(tz=TZ_ET).isoformat()

    if highest_seen_status_id > baseline_seen_status_id:
        state["last_seen_status_id"] = highest_seen_status_id
        state["last_processed_at"] = pd.Timestamp.now(tz=TZ_ET).isoformat()
        save_state(state_path, state)

    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll Trump Truth Social archive every 5 minutes, classify new original posts, and emit tradable alerts."
    )
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--outputs-root", type=Path, default=DEFAULT_OUTPUTS_ROOT)
    parser.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument("--gemini-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--min-gemini-confidence", type=float, default=DEFAULT_MIN_GEMINI_CONFIDENCE)
    parser.add_argument("--tws-host", default=DEFAULT_TWS_HOST)
    parser.add_argument("--tws-port", type=int, default=DEFAULT_TWS_PORT)
    parser.add_argument("--tws-client-id", type=int, default=DEFAULT_TWS_CLIENT_ID)
    parser.add_argument("--once", action="store_true", help="Run a single poll cycle and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_file_logger(args.log_file)
    LOGGER.info("bot_start state_file=%s log_file=%s poll_seconds=%s per_page=%s", args.state_file, args.log_file, args.poll_seconds, args.per_page)
    if args.poll_seconds != DEFAULT_POLL_SECONDS:
        print(
            f"[config] poll_seconds={args.poll_seconds} (default study bot cadence is {DEFAULT_POLL_SECONDS}s / 5 minutes)",
            flush=True,
        )
        LOGGER.info("config_override poll_seconds=%s", args.poll_seconds)

    watch_map = load_validation_watch_map(args.outputs_root)
    actionable_topics = ", ".join(sorted(watch_map)) if watch_map else "[none]"
    print(f"[config] actionable_topics={actionable_topics}", flush=True)
    LOGGER.info("config actionable_topics=%s", actionable_topics)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    state = load_state(args.state_file)
    did_startup_preview = False

    while True:
        try:
            posts = fetch_latest_original_posts(session, per_page=args.per_page)
            LOGGER.info(
                "poll_fetched posts=%s latest_status_id=%s",
                len(posts),
                posts[0].get("archive_status_id") if posts else None,
            )
            state = process_new_posts(
                posts=posts,
                state=state,
                state_path=args.state_file,
                watch_map=watch_map,
                session=session,
                gemini_model=args.gemini_model,
                gemini_timeout_seconds=args.gemini_timeout_seconds,
                min_gemini_confidence=args.min_gemini_confidence,
                tws_host=args.tws_host,
                tws_port=args.tws_port,
                tws_client_id=args.tws_client_id,
                preview_latest=not did_startup_preview,
            )
            did_startup_preview = True
            print(".", end="", flush=True)
            LOGGER.info("poll_success heartbeat=. last_seen_status_id=%s", state.get("last_seen_status_id"))
        except KeyboardInterrupt:
            LOGGER.info("bot_interrupt requested_by_user")
            raise
        except Exception as exc:
            print(f"[error] {type(exc).__name__}: {exc}", flush=True)
            LOGGER.exception("poll_error %s: %s", type(exc).__name__, exc)

        if args.once:
            LOGGER.info("bot_exit once=True")
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[exit] interrupted", flush=True)
        LOGGER.info("bot_exit interrupted")
        sys.exit(130)
