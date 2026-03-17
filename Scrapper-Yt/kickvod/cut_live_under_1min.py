#!/usr/bin/env python3
"""
Record/cut a stream or VOD into a clip shorter than 1 minute.

Example:
    python cut_live_under_1min.py --input "https://.../master.m3u8" --start 01:00:00 --duration 45 --output clip.mp4
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

MAX_DURATION_SECONDS = 59
KICKVOD_TIMEOUT = 30
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CLIPS_DIR = BASE_DIR / "clips"


def _prompt_choice(prompt: str, options: list[str]) -> str:
    print(f"\n{prompt}")
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")
    while True:
        raw = input("Pilih nomor: ").strip()
        if raw.isdigit():
            selected = int(raw)
            if 1 <= selected <= len(options):
                return options[selected - 1]
        print("Input tidak valid. Masukkan nomor yang tersedia.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cut-live-under-1min",
        description="Cut stream/VOD into a clip with max duration 59 seconds.",
    )
    parser.add_argument(
        "--input",
        help="Stream/VOD URL (e.g. m3u8) or local video path.",
    )
    parser.add_argument(
        "--start",
        default="00:00:00",
        help="Clip start time offset (HH:MM or HH:MM:SS). Default: 00:00:00.",
    )
    parser.add_argument(
        "--end",
        help="Optional clip end time offset (HH:MM or HH:MM:SS). If set, duration is end-start.",
    )
    parser.add_argument(
        "--output",
        default="clip_under_1min.mp4",
        help="Output file name (default: clip_under_1min.mp4).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=59,
        help="Clip duration in seconds (1-59, default: 59).",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Use stream copy for speed (-c copy). If omitted, re-encode for safer compatibility.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive prompt mode to fill input/start/duration quickly.",
    )
    return parser


def validate_duration(seconds: int) -> int:
    if seconds < 1:
        raise ValueError("Duration must be at least 1 second.")
    if seconds > MAX_DURATION_SECONDS:
        raise ValueError("Duration must be <= 59 seconds.")
    return seconds


def parse_time_to_seconds(value: str) -> int:
    text = value.strip()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Time must use HH:MM or HH:MM:SS format.")
    try:
        if len(parts) == 2:
            hours, minutes = map(int, parts)
            seconds = 0
        else:
            hours, minutes, seconds = map(int, parts)
    except ValueError as exc:
        raise ValueError("Time contains invalid non-numeric values.") from exc

    if hours < 0 or minutes < 0 or seconds < 0:
        raise ValueError("Time values cannot be negative.")
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Minutes and seconds must be less than 60.")
    return (hours * 3600) + (minutes * 60) + seconds


def resolve_stream_input(stream_input: str) -> str:
    """
    If input is a Kick VOD page URL, resolve it to direct m3u8 source from kickvod page.
    Otherwise, return input unchanged.
    """
    pattern = r"kick\.com/([^/]+)/(?:videos|video)/([^/?#]+)"
    match = re.search(pattern, stream_input)
    if not match:
        return stream_input

    channel_slug, video_uuid = match.group(1), match.group(2)
    page_url = f"https://kickvod.com/{channel_slug}/{video_uuid}"
    print("Resolving Kick VOD URL to direct stream source...")
    try:
        response = requests.get(page_url, timeout=KICKVOD_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch kickvod page for source resolution: {exc}") from exc

    source_match = re.search(r'const\s+vodSource\s*=\s*"([^"]+)"', response.text)
    if not source_match:
        raise ValueError(
            "Could not extract stream source (vodSource) from kickvod page."
        )

    return source_match.group(1)


def ensure_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise FileNotFoundError("ffmpeg not found in PATH. Please install ffmpeg first.")
    return ffmpeg_path


def make_ffmpeg_command(
    ffmpeg_path: str,
    stream_input: str,
    output_file: str,
    start_seconds: int,
    duration: int,
    use_copy: bool,
) -> list[str]:
    base_cmd = [
        ffmpeg_path,
        "-y",
        "-ss",
        str(start_seconds),
        "-i",
        stream_input,
        "-t",
        str(duration),
    ]

    if use_copy:
        return base_cmd + ["-c", "copy", output_file]

    # Re-encode for broader compatibility and reliable clip length.
    return base_cmd + [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_file,
    ]


def resolve_inputs(args: argparse.Namespace) -> tuple[str, int, int]:
    stream_input = args.input
    start_text = args.start
    end_text = args.end
    duration = args.duration

    if args.interactive:
        if not stream_input:
            stream_input = input("Input stream/VOD URL atau file path: ").strip()
        if not stream_input:
            raise ValueError("Input source cannot be empty.")

        start_raw = input("Mulai dari waktu (HH:MM:SS) [00:00:00]: ").strip()
        if start_raw:
            start_text = start_raw

        mode = _prompt_choice(
            "Pilih mode clip:",
            [
                "Pakai durasi (detik)",
                "Pakai jam selesai (end time)",
            ],
        )
        if mode == "Pakai jam selesai (end time)":
            end_raw = input("Jam selesai (HH:MM:SS): ").strip()
            if not end_raw:
                raise ValueError("End time cannot be empty when mode 2 is selected.")
            end_text = end_raw
        else:
            dur_raw = input("Durasi clip detik (1-59) [59]: ").strip()
            if dur_raw:
                try:
                    duration = int(dur_raw)
                except ValueError as exc:
                    raise ValueError("Duration must be an integer.") from exc

        output_raw = input(f"Output file [{args.output}]: ").strip()
        if output_raw:
            args.output = output_raw

    if not stream_input:
        raise ValueError("--input is required (or use --interactive).")

    stream_input = resolve_stream_input(stream_input)
    start_seconds = parse_time_to_seconds(start_text)

    if end_text:
        end_seconds = parse_time_to_seconds(end_text)
        if end_seconds <= start_seconds:
            raise ValueError("End time must be later than start time.")
        duration = end_seconds - start_seconds

    duration = validate_duration(duration)
    return stream_input, start_seconds, duration


def normalize_output_path(output_value: str) -> Path:
    raw_path = Path(output_value)
    # If user only gives a filename, store it in default clips folder.
    if raw_path.parent == Path("."):
        raw_path = DEFAULT_CLIPS_DIR / raw_path

    if not raw_path.suffix:
        raw_path = raw_path.with_suffix(".mp4")

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    return raw_path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        args.interactive = True

    try:
        stream_input, start_seconds, duration = resolve_inputs(args)
        ffmpeg_path = ensure_ffmpeg()
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path = normalize_output_path(args.output)
    ffmpeg_cmd = make_ffmpeg_command(
        ffmpeg_path=ffmpeg_path,
        stream_input=stream_input,
        output_file=str(output_path),
        start_seconds=start_seconds,
        duration=duration,
        use_copy=args.copy,
    )

    print(f"Clip start offset: {start_seconds}s")
    print(f"Recording clip for {duration}s...")
    print(f"Output: {output_path}")

    result = subprocess.run(ffmpeg_cmd, check=False)
    if result.returncode != 0:
        print("Error: ffmpeg process failed.", file=sys.stderr)
        return result.returncode

    print("Done. Clip created successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
