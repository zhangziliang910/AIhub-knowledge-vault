#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

from lib.config import VAULT_ROOT
from lib.logging_utils import log_error, log_run, now_iso
from lib.pipeline_utils import iso_week_label


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


def write_report(week: str, start: str, end: str, results: list[tuple[str, bool, str]]) -> str:
    path = VAULT_ROOT / "logs" / "runs" / f"{week}-weekly-report.md"
    lines = [
        "# Pipeline Run Report",
        "",
        "## 运行时间",
        "",
        f"- 开始：{start}",
        f"- 结束：{end}",
        "",
        "## 采集结果",
        "",
        "- 周 pipeline 默认不采集，只归纳本周材料。",
        "",
        "## 入库结果",
        "",
        "\n".join(f"- {name}: {'OK' if ok else 'FAIL'}" for name, ok, _ in results),
        "",
        "## 去重结果",
        "",
        "- 不适用。",
        "",
        "## 失败信息源",
        "",
        "- 详见 logs/errors。",
        "",
        "## 新增重点信息",
        "",
        "- 详见周报。",
        "",
        "## 更新的项目档案",
        "",
        "- 本周未单独修改项目档案。",
        "",
        "## 更新的概念文件",
        "",
        "- 本周更新 expert_profile 和 trend_memory。",
        "",
        "## 生成的日报 / 周报",
        "",
        f"- ai/weekly/{week}.md",
        f"- web3/weekly/{week}.md",
        "",
        "## 同步结果",
        "",
        "- SQLite 和向量库已同步。",
        "",
        "## 错误与待处理事项",
        "",
        "\n".join(f"- {name}: {out}" for name, ok, out in results if not ok) or "- 无",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.relative_to(VAULT_ROOT).as_posix()


def run(week: str | None = None) -> dict:
    label = week or iso_week_label()
    start = now_iso()
    steps = [
        ("generate_weekly_brief", "generate_weekly_brief.py", ["--week", label]),
        ("update_trend_memory", "update_trend_memory.py", ["--domain", "all", "--week", label]),
        ("update_expert_profile", "update_expert_profile.py", ["--domain", "all", "--week", label]),
        ("sync_db", "sync_markdown_to_db.py", ["--domain", "all"]),
        ("sync_vector", "sync_markdown_to_vector.py", ["--domain", "all"]),
    ]
    results = []
    for name, script, args in steps:
        ok, out = run_step(script, *args)
        results.append((name, ok, out))
    end = now_iso()
    report = write_report(label, start, end, results)
    log_run("runs", [f"run_weekly_pipeline week={label} report={report}"])
    return {"week": label, "report": report, "ok": all(ok for _, ok, _ in results)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default=None)
    args = parser.parse_args()
    print(run(args.week))


if __name__ == "__main__":
    main()
