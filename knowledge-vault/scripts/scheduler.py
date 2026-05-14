#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time

from lib.config import VAULT_ROOT, load_config
from lib.logging_utils import log_error, log_run


def run_script(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(VAULT_ROOT / "scripts" / script), *args], cwd=VAULT_ROOT, check=True)


def run_daily() -> None:
    run_script("run_daily_pipeline.py")


def run_evening() -> None:
    run_script("run_daily_pipeline.py", "--mode", "evening")


def run_weekly() -> None:
    run_script("run_weekly_pipeline.py")


def start_loop() -> None:
    config = load_config("schedule_config.yaml")
    last_run: set[str] = set()
    while True:
        now = dt.datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        try:
            daily = config.get("daily_pipeline", {})
            if daily.get("enabled") and now.strftime("%H:%M") == daily.get("time") and f"daily-{minute_key}" not in last_run:
                run_daily()
                last_run.add(f"daily-{minute_key}")
            evening = config.get("evening_update", {})
            if evening.get("enabled") and now.strftime("%H:%M") == evening.get("time") and f"evening-{minute_key}" not in last_run:
                run_evening()
                last_run.add(f"evening-{minute_key}")
            weekly = config.get("weekly_pipeline", {})
            if weekly.get("enabled") and now.strftime("%A") == weekly.get("day") and now.strftime("%H:%M") == weekly.get("time") and f"weekly-{minute_key}" not in last_run:
                run_weekly()
                last_run.add(f"weekly-{minute_key}")
        except Exception as exc:
            log_error("scheduler", str(exc))
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "run-daily", "run-evening", "run-weekly"])
    args = parser.parse_args()
    if args.command == "start":
        log_run("runs", ["scheduler start"])
        start_loop()
    elif args.command == "run-daily":
        run_daily()
    elif args.command == "run-evening":
        run_evening()
    elif args.command == "run-weekly":
        run_weekly()


if __name__ == "__main__":
    main()
