#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys

from lib.config import VAULT_ROOT
from lib.logging_utils import log_error, log_run, now_iso
from lib.pipeline_utils import today_str


def run_step(script: str, *args: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(VAULT_ROOT / "scripts" / script), *args],
            cwd=VAULT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return True, result.stdout.strip()
    except Exception as exc:
        log_error("pipeline", f"{script} failed: {exc}")
        return False, str(exc)


def write_report(date: str, mode: str, start: str, end: str, results: list[tuple[str, bool, str]]) -> str:
    path = VAULT_ROOT / "logs" / "runs" / f"{date}-daily-report.md"
    result_map = {name: out for name, _, out in results}
    lines = [
        "# Pipeline Run Report",
        "",
        "## 运行时间",
        "",
        f"- 模式：{mode}",
        f"- 开始：{start}",
        f"- 结束：{end}",
        "",
        "## 网络探针",
        "",
        result_map.get("network_probe", "无"),
        "",
        "## 采集结果",
        "",
        result_map.get("collect_sources", "无"),
        "",
        "## 入库结果",
        "",
        "\n".join(f"- {name}: {'OK' if ok else 'FAIL'}" for name, ok, _ in results),
        "",
        "## 去重结果",
        "",
        "- 详见 filter_items 输出和 logs/pipeline。",
        "",
        "## 失败信息源",
        "",
        "- 详见 logs/errors。若采集结果中 sources > 0 且 items = 0，通常表示网络或 socket 权限异常，应优先检查自动化运行环境。",
        "",
        "## 新增重点信息",
        "",
        "- 详见生成的 AI / Web3 日报。",
        "",
        "## 更新的项目档案",
        "",
        "- 由 vault.py ingest 自动更新。",
        "",
        "## 更新的概念文件",
        "",
        "- 当前版本保留 concepts 目录，后续可按主题拆分。",
        "",
        "## 生成的日报 / 周报",
        "",
        f"- ai/daily/{date}.md",
        f"- web3/daily/{date}.md",
        f"- reports/daily/{date}-ai.html",
        f"- reports/daily/{date}-web3.html",
        "",
        "## 同步结果",
        "",
        "- SQLite 和向量库在入库及日报生成后同步。",
        "",
        "## 错误与待处理事项",
        "",
        "\n".join(f"- {name}: {out}" for name, ok, out in results if not ok) or "- 无",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.relative_to(VAULT_ROOT).as_posix()


def run(mode: str = "daily") -> dict:
    date = today_str()
    start = now_iso()
    steps = [
        ("network_probe", "network_probe.py", []),
        ("collect_sources", "collect_sources.py", ["--domain", "all"]),
        ("filter_items", "filter_items.py", ["--domain", "all", "--date", date]),
        ("ingest_pipeline", "ingest_pipeline.py", ["--domain", "all", "--date", date]),
        ("add_chinese_translation", "add_chinese_translation.py", ["--domain", "all", "--date", date]),
        ("sync_db", "sync_markdown_to_db.py", ["--domain", "all"]),
        ("sync_vector", "sync_markdown_to_vector.py", ["--domain", "all"]),
        ("generate_daily_brief", "generate_daily_brief.py", ["--date", date]),
    ]
    results = []
    for name, script, args in steps:
        ok, out = run_step(script, *args)
        results.append((name, ok, out))
    end = now_iso()
    report = write_report(date, mode, start, end, results)
    log_run("runs", [f"run_daily_pipeline mode={mode} report={report}"])
    return {"date": date, "report": report, "ok": all(ok for _, ok, _ in results)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "evening"], default="daily")
    args = parser.parse_args()
    print(run(args.mode))


if __name__ == "__main__":
    main()
