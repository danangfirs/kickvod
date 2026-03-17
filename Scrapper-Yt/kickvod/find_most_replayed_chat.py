#!/usr/bin/env python3
"""
Find "Most Replayed"-like moments on Kick VOD using chat density spikes.

This script:
1) Fetches VOD metadata (start time + duration)
2) Pulls replay chat messages from Kick endpoint candidates
3) Buckets messages by time window (default: 60s)
4) Prints top intervals with highest chat velocity
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KickChatDensity/1.0"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://kick.com",
    "Referer": "https://kick.com/",
}


def create_http_session(
    prefer_curl_cffi: bool = True,
    impersonate: str = "safari18_4_ios",
) -> Any:
    """
    Create a resilient HTTP session.
    Prefer cloudscraper (if installed) to reduce 403 from Cloudflare/WAF.
    """
    if prefer_curl_cffi:
        try:
            # curl_cffi can impersonate modern browsers and often bypasses
            # anti-bot checks that block plain requests/cloudscraper.
            from curl_cffi import requests as curl_requests  # type: ignore

            curl_session = curl_requests.Session(impersonate=impersonate)
            curl_session.headers.update(DEFAULT_HEADERS)
            return curl_session
        except Exception:
            pass

    try:
        import cloudscraper  # type: ignore

        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        scraper.headers.update(DEFAULT_HEADERS)
        return scraper
    except Exception:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        return session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="find-most-replayed-chat",
        description="Detect top VOD moments on Kick using chat density spikes.",
    )
    parser.add_argument("--vod-url", required=True, help="Kick VOD URL")
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=60,
        help="Bucket window in seconds (default: 60)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many top intervals to print (default: 10)",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output JSON file for intervals",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=600,
        help="Safety cap for API requests (default: 600)",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "kick", "kickvod"],
        default="auto",
        help="Message source: auto (default), kick API, or kickvod replay API.",
    )
    parser.add_argument(
        "--kickvod-step-ms",
        type=int,
        default=10000,
        help="Time range step in milliseconds for kickvod replay API (default: 10000).",
    )
    parser.add_argument(
        "--kickvod-timeout",
        type=int,
        default=30,
        help="Request timeout seconds for kickvod API/page fetch (default: 30).",
    )
    parser.add_argument(
        "--kickvod-retries",
        type=int,
        default=3,
        help="Retry count per kickvod request when timeout/network error occurs (default: 3).",
    )
    parser.add_argument(
        "--cookie",
        help=(
            "Optional raw Cookie header for Kick requests "
            "(example: 'session=...; XSRF-TOKEN=...'). Useful if endpoint returns 403."
        ),
    )
    parser.add_argument(
        "--cookie-file",
        help=(
            "Optional path to text file containing raw Cookie header "
            "(one line: 'session=...; XSRF-TOKEN=...')."
        ),
    )
    parser.add_argument(
        "--authorization",
        help=(
            "Optional Authorization header value "
            "(example: 'Bearer <token>')."
        ),
    )
    parser.add_argument(
        "--authorization-file",
        help=(
            "Optional path to text file containing Authorization header value "
            "(one line, e.g. 'Bearer <token>')."
        ),
    )
    parser.add_argument(
        "--no-curl-cffi",
        action="store_true",
        help="Disable curl_cffi and use cloudscraper/requests fallback.",
    )
    parser.add_argument(
        "--impersonate",
        default="safari18_4_ios",
        help=(
            "Browser profile for curl_cffi impersonation "
            "(default: safari18_4_ios). Example: chrome136, edge101, safari17_0."
        ),
    )
    parser.add_argument(
        "--chatroom-channel-id",
        type=int,
        help="Optional chatroom channel_id (skip channel metadata fetch).",
    )
    parser.add_argument(
        "--vod-start-epoch",
        type=int,
        help="Optional VOD start unix timestamp (seconds).",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        help="Optional VOD duration in seconds.",
    )
    parser.add_argument(
        "--range-start",
        help="Start offset in VOD (HH:MM or HH:MM:SS). Example: 01:00",
    )
    parser.add_argument(
        "--range-end",
        help="End offset in VOD (HH:MM or HH:MM:SS). Example: 02:00",
    )
    parser.add_argument(
        "--interactive-range",
        action="store_true",
        help="Prompt interactively for range start/end before processing.",
    )
    return parser


def parse_vod_url(vod_url: str) -> tuple[str, str]:
    # Accept both /videos/{uuid} and /video/{uuid}
    pattern = r"kick\.com/([^/]+)/(?:videos|video)/([^/?#]+)"
    match = re.search(pattern, vod_url)
    if not match:
        raise ValueError("Invalid Kick VOD URL format.")
    channel_slug = match.group(1)
    video_uuid = match.group(2)
    return channel_slug, video_uuid


def parse_datetime_to_epoch(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:  # likely ms
            return int(value / 1000)
        return int(value)

    text = str(value).strip()
    if text.isdigit():
        num = int(text)
        if num > 10_000_000_000:
            return int(num / 1000)
        return num

    # Try ISO formats
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def extract_video_duration_seconds(video_data: dict[str, Any]) -> int:
    duration_candidates = [
        video_data.get("duration"),
        video_data.get("duration_seconds"),
        video_data.get("length"),
    ]

    for value in duration_candidates:
        if isinstance(value, (int, float)):
            if value > 0:
                return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)

    # Try HH:MM:SS
    duration_text = video_data.get("duration")
    if isinstance(duration_text, str) and ":" in duration_text:
        parts = duration_text.split(":")
        try:
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
            if len(parts) == 2:
                m, s = map(int, parts)
                return m * 60 + s
        except Exception:
            pass

    raise ValueError("Could not determine video duration from API response.")


def get_json(session: Any, url: str, params: dict[str, Any] | None = None) -> Any:
    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_text(
    session: Any, url: str, params: dict[str, Any] | None = None
) -> str:
    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_video_metadata_from_record(video_data: dict[str, Any]) -> tuple[int, int]:
    start_epoch = parse_datetime_to_epoch(
        video_data.get("start_time")
        or video_data.get("created_at")
        or video_data.get("created")
        or video_data.get("video", {}).get("created_at")
    )
    if start_epoch is None:
        raise ValueError("Could not parse VOD start time from video metadata.")

    duration_seconds = extract_video_duration_seconds(video_data)
    if duration_seconds > 60 * 60 * 24:
        duration_seconds = int(duration_seconds / 1000)
    if duration_seconds <= 0:
        raise ValueError("Invalid VOD duration from video metadata.")
    return start_epoch, duration_seconds


def find_video_in_channel_video_list(
    items: Any, target_uuid: str
) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        # Kick often stores uuid under nested "video.uuid"
        nested_video = item.get("video")
        if isinstance(nested_video, dict):
            if str(nested_video.get("uuid", "")).lower() == target_uuid.lower():
                return item
        # Some payload variants may expose uuid directly
        if str(item.get("uuid", "")).lower() == target_uuid.lower():
            return item
    return None


def fetch_video_metadata_from_v2_list(
    session: Any, channel_slug: str, video_uuid: str
) -> tuple[int, int]:
    videos_endpoint = f"https://kick.com/api/v2/channels/{channel_slug}/videos"
    payload = get_json(session, videos_endpoint)
    if isinstance(payload, dict):
        videos = payload.get("data", payload.get("videos", []))
    else:
        videos = payload

    matched = find_video_in_channel_video_list(videos, video_uuid)
    if matched is None:
        raise ValueError("Target video uuid not found in channel video list.")
    return extract_video_metadata_from_record(matched)


def fetch_video_metadata_from_page(
    session: Any, channel_slug: str, video_uuid: str
) -> tuple[int, int]:
    vod_page_url = f"https://kick.com/{channel_slug}/videos/{video_uuid}"
    page_html = get_text(session, vod_page_url)

    # Kick frontend often embeds JSON under __NEXT_DATA__ script.
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page_html,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("Could not locate __NEXT_DATA__ in VOD page HTML.")

    raw_json = html.unescape(match.group(1))
    payload = json.loads(raw_json)
    payload_str = json.dumps(payload)

    # Last-resort extraction using regex from serialized payload.
    start_match = re.search(
        r'"start_time"\s*:\s*"([^"]+)"|"created_at"\s*:\s*"([^"]+)"',
        payload_str,
    )
    duration_match = re.search(r'"duration"\s*:\s*("?[\d:]+"?)', payload_str)

    if not start_match or not duration_match:
        raise ValueError("Could not extract start_time/duration from page payload.")

    start_value = start_match.group(1) or start_match.group(2)
    duration_value_raw = duration_match.group(1).strip('"')
    temp_record: dict[str, Any] = {
        "start_time": start_value,
        "duration": duration_value_raw,
    }
    return extract_video_metadata_from_record(temp_record)


def fetch_video_metadata(
    session: Any, channel_slug: str, video_uuid: str
) -> tuple[int, int]:
    errors: list[str] = []

    # Candidate 1: legacy direct video endpoint
    try:
        video_endpoint = f"https://kick.com/api/v1/video/{video_uuid}"
        video_data = get_json(session, video_endpoint)
        return extract_video_metadata_from_record(video_data)
    except Exception as exc:
        errors.append(f"api/v1/video failed: {exc}")

    # Candidate 2: channel videos listing endpoint
    try:
        return fetch_video_metadata_from_v2_list(session, channel_slug, video_uuid)
    except Exception as exc:
        errors.append(f"api/v2/channels/{{slug}}/videos failed: {exc}")

    # Candidate 3: parse metadata embedded in the VOD HTML page
    try:
        return fetch_video_metadata_from_page(session, channel_slug, video_uuid)
    except Exception as exc:
        errors.append(f"VOD page parse failed: {exc}")

    raise ValueError(" | ".join(errors))


def fetch_channel_chatroom_id(session: Any, channel_slug: str) -> int:
    channel_endpoint = f"https://kick.com/api/v2/channels/{channel_slug}"
    channel_data = get_json(session, channel_endpoint)

    chatroom = channel_data.get("chatroom") or {}
    for key in ("channel_id", "id"):
        value = chatroom.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    # Fallback from top-level fields
    for key in ("id", "channel_id"):
        value = channel_data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    raise ValueError("Could not find channel/chatroom id from channel endpoint.")


def normalize_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "messages", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                nested_messages = value.get("messages")
                if isinstance(nested_messages, list):
                    return [x for x in nested_messages if isinstance(x, dict)]
    return []


def extract_message_id(message: dict[str, Any]) -> str | None:
    for key in ("id", "message_id", "uuid"):
        value = message.get(key)
        if value is not None:
            return str(value)
    return None


def extract_message_epoch(message: dict[str, Any]) -> int | None:
    candidates = [
        message.get("created_at"),
        message.get("timestamp"),
        message.get("sent_at"),
        message.get("time"),
    ]
    for value in candidates:
        epoch = parse_datetime_to_epoch(value)
        if epoch is not None:
            return epoch
    return None


def fetch_messages_for_timestamp(
    session: Any, channel_id: int, unix_ts: int
) -> tuple[list[dict[str, Any]], str | None]:
    url = f"https://kick.com/api/v2/channels/{channel_id}/messages"
    param_candidates = [
        {"start_time": unix_ts},
        {"startTime": unix_ts},
        {"timestamp": unix_ts},
        {"time": unix_ts},
        {"start": unix_ts},
    ]

    last_error = None
    for params in param_candidates:
        try:
            payload = get_json(session, url, params=params)
            messages = normalize_messages(payload)
            if messages:
                return messages, next_cursor_from_payload(payload)
        except Exception as exc:  # keep trying next params
            last_error = exc
            continue

    if last_error is not None:
        return [], str(last_error)
    return [], None


def next_cursor_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("next_cursor", "cursor", "next"):
            value = meta.get(key)
            if value:
                return str(value)

    for key in ("next_cursor", "cursor", "next"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def fetch_messages_by_cursor(
    session: Any, channel_id: int, cursor: str
) -> tuple[list[dict[str, Any]], str | None]:
    url = f"https://kick.com/api/v2/channels/{channel_id}/messages"
    params = {"cursor": cursor}
    try:
        payload = get_json(session, url, params=params)
        return normalize_messages(payload), next_cursor_from_payload(payload)
    except Exception:
        return [], None


def fetch_kickvod_replay_counts(
    vod_url: str,
    window_seconds: int,
    max_requests: int,
    step_ms: int,
    timeout_seconds: int,
    retries: int,
    range_start_text: str | None = None,
    range_end_text: str | None = None,
    interactive_range: bool = False,
) -> tuple[dict[int, int], int, int, int, int, int, int]:
    channel_slug, video_uuid = parse_vod_url(vod_url)
    page_url = f"https://kickvod.com/{channel_slug}/{video_uuid}"

    if timeout_seconds < 5:
        timeout_seconds = 5
    if retries < 1:
        retries = 1

    page_html = ""
    last_page_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            page_html = requests.get(page_url, timeout=timeout_seconds).text
            last_page_error = None
            break
        except requests.RequestException as exc:
            last_page_error = exc
            if attempt < retries:
                time.sleep(min(1.5 * attempt, 4.0))
    if last_page_error is not None:
        raise ValueError(f"Failed loading kickvod page after {retries} retries: {last_page_error}")

    created_match = re.search(r"const\s+vodCreatedAt\s*=\s*(\d+)", page_html)
    duration_match = re.search(r"const\s+vodDuration\s*=\s*(\d+)", page_html)
    slug_match = re.search(r'const\s+slug\s*=\s*"([^"]+)"', page_html)

    if not created_match or not duration_match:
        raise ValueError("kickvod page missing vodCreatedAt/vodDuration.")

    replay_slug = slug_match.group(1) if slug_match else channel_slug
    vod_start_ms = int(created_match.group(1))
    vod_duration_ms = int(duration_match.group(1))

    if vod_duration_ms <= 0:
        raise ValueError("Invalid vodDuration from kickvod page.")

    vod_start_epoch = int(vod_start_ms / 1000)
    duration_seconds = int(vod_duration_ms / 1000)
    range_start_offset, range_end_offset = resolve_range_offsets(
        duration_seconds=duration_seconds,
        range_start_text=range_start_text,
        range_end_text=range_end_text,
        interactive=interactive_range,
    )
    range_start_epoch = vod_start_epoch + range_start_offset
    range_end_epoch = vod_start_epoch + range_end_offset
    query_start_ms = vod_start_ms + (range_start_offset * 1000)
    query_end_ms = vod_start_ms + (range_end_offset * 1000)

    counts: dict[int, int] = defaultdict(int)
    seen_ids: set[str] = set()
    total_messages = 0
    request_count = 0
    failed_windows = 0

    if step_ms < 1000:
        step_ms = 1000
    # kickvod rejects large range; 10s is known to work.
    if step_ms > 10000:
        step_ms = 10000

    cursor_ms = query_start_ms
    while cursor_ms < query_end_ms and request_count < max_requests:
        end_ms = min(cursor_ms + step_ms, query_end_ms)
        url = f"https://kickvod.com/api/messages/{replay_slug}"
        params = {"start": cursor_ms, "end": end_ms}
        response = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, params=params, timeout=timeout_seconds)
                request_count += 1
                break
            except requests.RequestException:
                request_count += 1
                if attempt < retries:
                    time.sleep(min(0.5 * attempt, 2.0))
        if response is None:
            failed_windows += 1
            cursor_ms = end_ms
            continue

        if response.status_code != 200:
            cursor_ms = end_ms
            continue

        try:
            payload = response.json()
        except Exception:
            payload = []

        if not isinstance(payload, list):
            cursor_ms = end_ms
            continue

        for msg in payload:
            if not isinstance(msg, dict):
                continue
            msg_id = extract_message_id(msg)
            if msg_id and msg_id in seen_ids:
                continue
            if msg_id:
                seen_ids.add(msg_id)

            msg_epoch = parse_datetime_to_epoch(
                msg.get("createdAt") or msg.get("created_at")
            )
            if msg_epoch is None:
                continue

            if msg_epoch < range_start_epoch or msg_epoch > range_end_epoch:
                continue

            bucket = ((msg_epoch - vod_start_epoch) // window_seconds) * window_seconds
            counts[bucket] += 1
            total_messages += 1

        cursor_ms = end_ms

    if failed_windows > 0:
        print(f"kickvod warning: skipped {failed_windows} windows due to network timeouts/errors")

    return (
        counts,
        total_messages,
        request_count,
        vod_start_epoch,
        duration_seconds,
        range_start_offset,
        range_end_offset,
    )


def load_cookie_header(cookie_arg: str | None, cookie_file: str | None) -> str | None:
    if cookie_arg:
        return cookie_arg.strip()
    if not cookie_file:
        return None
    file_path = Path(cookie_file)
    if not file_path.exists():
        raise ValueError(f"Cookie file not found: {file_path}")
    raw = file_path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("Cookie file is empty.")
    # Support accidental multi-line paste.
    return " ".join(line.strip() for line in raw.splitlines() if line.strip())


def load_authorization_header(
    authorization_arg: str | None, authorization_file: str | None
) -> str | None:
    if authorization_arg:
        return authorization_arg.strip()
    if not authorization_file:
        return None
    file_path = Path(authorization_file)
    if not file_path.exists():
        raise ValueError(f"Authorization file not found: {file_path}")
    raw = file_path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("Authorization file is empty.")
    return " ".join(line.strip() for line in raw.splitlines() if line.strip())


def seconds_to_hhmmss(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def compute_stats(values: list[int]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(variance)


def parse_hhmmss_to_seconds(value: str) -> int:
    text = value.strip()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Time must be HH:MM or HH:MM:SS")
    try:
        if len(parts) == 2:
            hours, minutes = map(int, parts)
            seconds = 0
        else:
            hours, minutes, seconds = map(int, parts)
    except ValueError as exc:
        raise ValueError("Time must contain only numbers") from exc

    if hours < 0 or minutes < 0 or seconds < 0:
        raise ValueError("Time values cannot be negative")
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Minutes and seconds must be less than 60")
    return (hours * 3600) + (minutes * 60) + seconds


def resolve_range_offsets(
    duration_seconds: int,
    range_start_text: str | None,
    range_end_text: str | None,
    interactive: bool,
) -> tuple[int, int]:
    default_start = "00:00"
    default_end = seconds_to_hhmmss(duration_seconds)

    if interactive:
        start_input = input(f"Range start [{default_start}]: ").strip()
        end_input = input(f"Range end [{default_end}]: ").strip()
        range_start_text = start_input or default_start
        range_end_text = end_input or default_end

    start_offset = 0
    end_offset = duration_seconds

    if range_start_text:
        start_offset = parse_hhmmss_to_seconds(range_start_text)
    if range_end_text:
        end_offset = parse_hhmmss_to_seconds(range_end_text)

    if start_offset >= duration_seconds:
        raise ValueError("range-start is outside VOD duration")
    if end_offset <= 0:
        raise ValueError("range-end must be > 00:00")
    if end_offset > duration_seconds:
        end_offset = duration_seconds
    if start_offset >= end_offset:
        raise ValueError("range-start must be earlier than range-end")

    return start_offset, end_offset


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.window_seconds < 5:
        print("Error: --window-seconds minimal 5", flush=True)
        return 1
    if args.top < 1:
        print("Error: --top minimal 1", flush=True)
        return 1
    if args.kickvod_step_ms < 1000:
        print("Error: --kickvod-step-ms minimal 1000", flush=True)
        return 1
    if args.kickvod_timeout < 5:
        print("Error: --kickvod-timeout minimal 5", flush=True)
        return 1
    if args.kickvod_retries < 1:
        print("Error: --kickvod-retries minimal 1", flush=True)
        return 1

    try:
        channel_slug, video_uuid = parse_vod_url(args.vod_url)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    session = create_http_session(
        prefer_curl_cffi=not args.no_curl_cffi,
        impersonate=args.impersonate,
    )
    try:
        cookie_value = load_cookie_header(args.cookie, args.cookie_file)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    try:
        authorization_value = load_authorization_header(
            args.authorization, args.authorization_file
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    if cookie_value:
        session.headers.update({"Cookie": cookie_value})
    if authorization_value:
        session.headers.update({"Authorization": authorization_value})

    manual_mode = (
        args.vod_start_epoch is not None
        and args.duration_seconds is not None
        and args.chatroom_channel_id is not None
    )

    counts: dict[int, int] = defaultdict(int)
    total_messages = 0
    request_count = 0

    vod_start = 0
    duration = 0
    analysis_start_offset = 0
    analysis_end_offset = 0
    chatroom_channel_id: int | None = None

    use_kick = args.source in ("auto", "kick")
    use_kickvod = args.source in ("auto", "kickvod")

    if use_kick:
        if manual_mode:
            vod_start = int(args.vod_start_epoch)
            duration = int(args.duration_seconds)
            chatroom_channel_id = int(args.chatroom_channel_id)
        else:
            try:
                vod_start, duration = fetch_video_metadata(session, channel_slug, video_uuid)
                chatroom_channel_id = fetch_channel_chatroom_id(session, channel_slug)
            except Exception as exc:
                if args.source == "kick":
                    print(f"Error while fetching metadata: {exc}")
                    print(
                        "Tip: Kick is returning 403. Use --cookie or --cookie-file.\n"
                        "Alternative: provide --vod-start-epoch --duration-seconds --chatroom-channel-id."
                    )
                    return 1
                # In auto mode, we'll try kickvod fallback below.

        if vod_start > 0 and duration > 0 and chatroom_channel_id is not None:
            try:
                analysis_start_offset, analysis_end_offset = resolve_range_offsets(
                    duration_seconds=duration,
                    range_start_text=args.range_start,
                    range_end_text=args.range_end,
                    interactive=args.interactive_range,
                )
            except ValueError as exc:
                print(f"Error: {exc}")
                return 1

            vod_analysis_start = vod_start + analysis_start_offset
            vod_analysis_end = vod_start + analysis_end_offset
            print(f"Channel: {channel_slug}")
            print(f"Video UUID: {video_uuid}")
            print(f"Duration: {duration}s")
            print(f"Chatroom channel id: {chatroom_channel_id}")
            print(
                "Analyze range: "
                f"{seconds_to_hhmmss(analysis_start_offset)} - "
                f"{seconds_to_hhmmss(analysis_end_offset)}"
            )
            print("Collecting chat replay data from Kick API...")

            seen_ids: set[str] = set()
            cursor: str | None = None

            for ts in range(vod_analysis_start, vod_analysis_end, args.window_seconds):
                if request_count >= args.max_requests:
                    break

                messages, cursor_candidate = fetch_messages_for_timestamp(
                    session, chatroom_channel_id, ts
                )
                request_count += 1
                if cursor is None and cursor_candidate:
                    cursor = cursor_candidate

                for msg in messages:
                    msg_epoch = extract_message_epoch(msg)
                    if msg_epoch is None:
                        continue
                    if msg_epoch < vod_analysis_start or msg_epoch > vod_analysis_end:
                        continue

                    msg_id = extract_message_id(msg)
                    if msg_id and msg_id in seen_ids:
                        continue
                    if msg_id:
                        seen_ids.add(msg_id)

                    bucket = ((msg_epoch - vod_start) // args.window_seconds) * args.window_seconds
                    counts[bucket] += 1
                    total_messages += 1

            while cursor and request_count < args.max_requests:
                messages, next_cursor = fetch_messages_by_cursor(
                    session, chatroom_channel_id, cursor
                )
                request_count += 1
                if not messages:
                    break

                for msg in messages:
                    msg_epoch = extract_message_epoch(msg)
                    if msg_epoch is None:
                        continue
                    if msg_epoch < vod_analysis_start or msg_epoch > vod_analysis_end:
                        continue

                    msg_id = extract_message_id(msg)
                    if msg_id and msg_id in seen_ids:
                        continue
                    if msg_id:
                        seen_ids.add(msg_id)

                    bucket = ((msg_epoch - vod_start) // args.window_seconds) * args.window_seconds
                    counts[bucket] += 1
                    total_messages += 1

                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

    if use_kickvod and not counts:
        print("Kick API returned no replay messages, trying kickvod replay API...")
        try:
            (
                counts,
                total_messages,
                kickvod_requests,
                vod_start,
                duration,
                analysis_start_offset,
                analysis_end_offset,
            ) = fetch_kickvod_replay_counts(
                vod_url=args.vod_url,
                window_seconds=args.window_seconds,
                max_requests=args.max_requests,
                step_ms=args.kickvod_step_ms,
                timeout_seconds=args.kickvod_timeout,
                retries=args.kickvod_retries,
                range_start_text=args.range_start,
                range_end_text=args.range_end,
                interactive_range=args.interactive_range,
            )
            request_count += kickvod_requests
            print(
                f"kickvod replay loaded: messages={total_messages}, "
                f"requests={kickvod_requests}, duration={duration}s"
            )
            print(
                "Analyze range: "
                f"{seconds_to_hhmmss(analysis_start_offset)} - "
                f"{seconds_to_hhmmss(analysis_end_offset)}"
            )
        except Exception as exc:
            print(f"kickvod fallback failed: {exc}")

    if not counts:
        print("No chat replay messages collected.")
        print(
            "Tip: endpoint or params may have changed. Try increasing --max-requests "
            "or inspect network requests from Kick web app."
        )
        return 2

    if analysis_end_offset <= analysis_start_offset:
        analysis_start_offset = 0
        analysis_end_offset = duration

    all_buckets = list(
        range(
            analysis_start_offset,
            analysis_end_offset + args.window_seconds,
            args.window_seconds,
        )
    )
    values = [counts.get(bucket, 0) for bucket in all_buckets]
    mean, std = compute_stats(values)

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_rows = ranked[: args.top]

    output = []
    print("\nTop intervals (Most Replayed approximation):")
    for index, (bucket_offset, count) in enumerate(top_rows, start=1):
        z_score = (count - mean) / std if std > 0 else 0.0
        start_hhmmss = seconds_to_hhmmss(bucket_offset)
        end_hhmmss = seconds_to_hhmmss(bucket_offset + args.window_seconds)
        item = {
            "rank": index,
            "start": start_hhmmss,
            "end": end_hhmmss,
            "messages": count,
            "z_score": round(z_score, 2),
        }
        output.append(item)
        print(
            f"{index:02d}. {start_hhmmss} - {end_hhmmss} | "
            f"messages={count} | z={item['z_score']}"
        )

    print(
        f"\nCollected messages: {total_messages} | "
        f"API requests: {request_count} | window={args.window_seconds}s"
    )

    if args.json_output:
        payload = {
            "vod_url": args.vod_url,
            "channel": channel_slug,
            "video_uuid": video_uuid,
            "window_seconds": args.window_seconds,
            "analyzed_range_start": seconds_to_hhmmss(analysis_start_offset),
            "analyzed_range_end": seconds_to_hhmmss(analysis_end_offset),
            "total_messages_collected": total_messages,
            "api_requests": request_count,
            "mean_messages_per_window": round(mean, 4),
            "std_messages_per_window": round(std, 4),
            "top_intervals": output,
        }
        with open(args.json_output, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        print(f"Saved analysis to: {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
