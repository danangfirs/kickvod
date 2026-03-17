#!/usr/bin/env python3
"""
Unified CLI wrapper for Kick VOD tools in this folder.

Backends:
- python: uses KickNoSub tool logic
- js: runs kick-dl interactive CLI
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KICKNOSUB_TOOL_DIR = BASE_DIR / "KickNoSub" / "tool"
KICKNOSUB_SCRIPT = KICKNOSUB_TOOL_DIR / "kicknosub.py"
KICKDL_DIR = BASE_DIR / "kick-dl"
QUALITY_CHOICES = ["Auto", "1080p60", "720p60", "480p30", "360p30", "160p30"]


def _exit_with_error(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _run_command(command: list[str], cwd: Path | None = None) -> int:
    process = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
    return process.returncode


def _run_pnpm_command(args: list[str], cwd: Path | None = None) -> int:
    """
    Run pnpm in a cross-platform way.
    """
    if os.name == "nt":
        pnpm_cmd = shutil.which("pnpm.cmd")
        if pnpm_cmd:
            return _run_command([pnpm_cmd, *args], cwd=cwd)
        return _run_command(["cmd", "/c", "pnpm", *args], cwd=cwd)

    pnpm_bin = shutil.which("pnpm")
    if not pnpm_bin:
        _exit_with_error("pnpm not found. Install pnpm first.")
    return _run_command([pnpm_bin, *args], cwd=cwd)


def _run_js_backend(install: bool) -> int:
    if not KICKDL_DIR.exists():
        _exit_with_error(f"Folder not found: {KICKDL_DIR}")

    if os.name == "nt":
        has_pnpm = bool(shutil.which("pnpm.cmd")) or bool(shutil.which("pnpm"))
    else:
        has_pnpm = bool(shutil.which("pnpm"))
    if not has_pnpm:
        _exit_with_error("pnpm not found. Install pnpm first.")

    node_bin = shutil.which("node")
    if not node_bin:
        _exit_with_error("node not found. Install Node.js first.")

    if install:
        print("Installing JavaScript dependencies in kick-dl via pnpm...")
        code = _run_pnpm_command(["install"], cwd=KICKDL_DIR)
        if code != 0:
            return code

    cli_entry = KICKDL_DIR / "bin" / "cli.js"
    if not cli_entry.exists():
        _exit_with_error(f"kick-dl CLI entry not found: {cli_entry}")

    print("Starting kick-dl interactive CLI...")
    return _run_command([node_bin, str(cli_entry)], cwd=KICKDL_DIR)


def _run_python_backend(url: str, quality: str, output: str | None) -> int:
    if not KICKNOSUB_SCRIPT.exists():
        _exit_with_error(f"Script not found: {KICKNOSUB_SCRIPT}")

    # Import dynamically from local KickNoSub tool folder.
    sys.path.insert(0, str(KICKNOSUB_TOOL_DIR))
    try:
        from kicknosub import KickNoSub  # type: ignore
    except Exception as exc:
        _exit_with_error(
            "Failed to import KickNoSub. Run: "
            f'"{sys.executable}" -m pip install -r "{KICKNOSUB_TOOL_DIR / "requirements.txt"}"\n'
            f"Details: {exc}"
        )

    app = KickNoSub()
    stream_url = app.get_video_stream_url(url, quality)
    if not stream_url:
        _exit_with_error("Could not get stream URL from given Kick VOD URL.")

    print(f"Stream URL: {stream_url}")

    if output:
        output_file = output if output.lower().endswith(".mp4") else f"{output}.mp4"
        app.download_video(stream_url, output_file)

    return 0


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


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Input tidak valid. Jawab dengan y atau n.")


def _interactive_main() -> int:
    print("Kick VOD CLI - Interactive Mode")
    backend = _prompt_choice(
        "Pilih backend:",
        [
            "Python (KickNoSub)",
            "JavaScript (kick-dl)",
            "Lihat rekomendasi",
            "Keluar",
        ],
    )

    if backend == "Keluar":
        print("Bye.")
        return 0

    if backend == "Lihat rekomendasi":
        print("Recommendation:")
        print("- Use 'js' if you want the most ready-to-use interactive CLI.")
        print("- Use 'python' if you want easier automation from Python scripts.")
        return 0

    if backend == "JavaScript (kick-dl)":
        install = _prompt_yes_no("Install dependency pnpm dulu?", default=False)
        return _run_js_backend(install=install)

    # Python flow
    while True:
        url = input("Masukkan Kick VOD URL: ").strip()
        if url:
            break
        print("URL tidak boleh kosong.")

    quality = _prompt_choice("Pilih kualitas:", QUALITY_CHOICES)
    download = _prompt_yes_no("Sekalian download MP4?", default=False)
    output = None
    if download:
        while True:
            output_name = input("Nama file output (tanpa .mp4): ").strip()
            if output_name:
                output = output_name
                break
            print("Nama file output tidak boleh kosong.")

    return _run_python_backend(url=url, quality=quality, output=output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kickvod-cli",
        description="CLI wrapper for KickNoSub (Python) and kick-dl (JavaScript).",
    )

    subparsers = parser.add_subparsers(dest="backend", required=True)

    py_parser = subparsers.add_parser("python", help="Use KickNoSub Python backend")
    py_parser.add_argument("--url", required=True, help="Kick VOD URL")
    py_parser.add_argument(
        "--quality",
        default="Auto",
        choices=QUALITY_CHOICES,
        help="Preferred stream quality (default: Auto)",
    )
    py_parser.add_argument(
        "--output",
        help="Optional output filename for MP4 download (without/with .mp4)",
    )

    js_parser = subparsers.add_parser("js", help="Use kick-dl JavaScript backend")
    js_parser.add_argument(
        "--install",
        action="store_true",
        help="Run pnpm install before starting kick-dl",
    )

    subparsers.add_parser(
        "recommend",
        help="Show recommended backend based on your use case",
    )

    return parser


def main() -> int:
    if len(sys.argv) == 1:
        return _interactive_main()

    parser = build_parser()
    args = parser.parse_args()

    if args.backend == "python":
        return _run_python_backend(args.url, args.quality, args.output)

    if args.backend == "js":
        return _run_js_backend(args.install)

    if args.backend == "recommend":
        print("Recommendation:")
        print("- Use 'js' if you want the most ready-to-use interactive CLI.")
        print("- Use 'python' if you want easier automation from Python scripts.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
