"""Compile a sketch with arduino-cli and fail if SRAM (or flash) use is over a limit.

Usage:
    python tools/firmware_size_gate.py <sketch_dir> --fqbn arduino:avr:nano:cpu=atmega328 \
        [--max-sram-pct 75] [--max-flash-pct 95] [--build-property ...]

Prints a one-line summary (also appended to $GITHUB_STEP_SUMMARY when set).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sketch")
    ap.add_argument("--fqbn", required=True)
    ap.add_argument("--max-sram-pct", type=float, default=75.0)
    ap.add_argument("--max-flash-pct", type=float, default=95.0)
    ap.add_argument("--build-property", action="append", default=[])
    ap.add_argument("--arduino-cli", default="arduino-cli")
    args = ap.parse_args()

    cmd = [args.arduino_cli, "compile", "--fqbn", args.fqbn, "--json", args.sketch]
    for prop in args.build_property:
        cmd += ["--build-property", prop]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout, proc.stderr, sep="\n", file=sys.stderr)
        print("compile output was not JSON", file=sys.stderr)
        return 2
    if not result.get("success"):
        print(result.get("compiler_err", proc.stderr), file=sys.stderr)
        print(f"compile FAILED for {args.sketch} ({args.fqbn})", file=sys.stderr)
        return 1

    sections = {s["name"]: s for s in result["builder_result"]["executable_sections_size"]}
    flash, sram = sections["text"], sections["data"]
    flash_pct = 100.0 * flash["size"] / flash["max_size"]
    sram_pct = 100.0 * sram["size"] / sram["max_size"]
    variant = " ".join([args.fqbn, *args.build_property])
    line = (
        f"{args.sketch} [{variant}]: "
        f"flash {flash['size']}/{flash['max_size']} B ({flash_pct:.1f}%), "
        f"SRAM {sram['size']}/{sram['max_size']} B ({sram_pct:.1f}%), "
        f"gate SRAM <= {args.max_sram_pct:.0f}%"
    )
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"- {line}\n")

    ok = sram_pct <= args.max_sram_pct and flash_pct <= args.max_flash_pct
    if not ok:
        print("size gate FAILED", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
