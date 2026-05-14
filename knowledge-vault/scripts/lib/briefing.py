from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path
from typing import Any

from .config import VAULT_ROOT
from .db import connect, init_db
from .pipeline_utils import iso_week_label, load_user_context


def domain_label(domain: str) -> str:
    return "AI" if domain == "ai" else "Web3"


def docs_for_date(domain: str, date: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM documents
            WHERE status='active' AND domain IN (?, 'cross') AND substr(collected_at,1,10)=?
            ORDER BY importance_score DESC, collected_at DESC
            """,
            (domain, date),
        ).fetchall()
        return [dict(r) for r in rows]


def docs_for_week(domain: str, week_label: str) -> list[dict[str, Any]]:
    year, week = week_label.split("-W")
    start = dt.date.fromisocalendar(int(year), int(week), 1)
    end = dt.date.fromisocalendar(int(year), int(week), 7)
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM documents
            WHERE status='active' AND domain IN (?, 'cross')
              AND substr(collected_at,1,10) >= ? AND substr(collected_at,1,10) <= ?
            ORDER BY importance_score DESC, collected_at DESC
            """,
            (domain, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]


def top_terms(docs: list[dict[str, Any]], limit: int = 8) -> list[str]:
    text = " ".join((d.get("title", "") + " " + d.get("summary", "")) for d in docs)
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}|[\u4e00-\u9fff]{2,}", text)
    stop = {"今日", "信息", "项目", "来源", "the", "and", "for", "with", "from"}
    counts: dict[str, int] = {}
    for c in candidates:
        if c.lower() in stop:
            continue
        counts[c] = counts.get(c, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def work_insights(domain: str, docs: list[dict[str, Any]]) -> list[str]:
    ctx = load_user_context()
    focus = "、".join(ctx.get("focus_topics", [])[:6])
    if not docs:
        return ["当前入库材料不足，暂不形成项目建议；优先补充高可信官方材料和专题研究。"]
    terms = "、".join(top_terms(docs, 6)) or "当前主题"
    if domain == "ai":
        return [
            f"对多 Agent 知识汇集项目：关注 {terms} 是否能转化为采集、路由、记忆或工具调用能力。",
            "对 OpenClaw / Codex / MCP / Skill 生态：优先跟踪能降低工作流集成成本的接口、插件和执行环境变化。",
            "对银行 AI 赋能：重点筛选可落地到知识管理、客户运营、风控合规、投研辅助的案例。",
            f"建议继续围绕用户关注方向建立专题概念卡片：{focus}。",
        ]
    return [
        f"对 Web3 信息协作机制：关注 {terms} 与身份、确权、协作、激励机制之间的连接。",
        "对 AI 共享网盘 / Agent 文档工作区：优先研究 Web3 在权限、溯源、贡献度记录方面的可借鉴设计。",
        "对银行业务：稳定币、RWA、DeFi 的合规进展可作为数字资产与跨境支付研究线索。",
        f"建议继续围绕用户关注方向建立专题概念卡片：{focus}。",
    ]


def citation_lines(docs: list[dict[str, Any]]) -> list[str]:
    lines = []
    for idx, doc in enumerate(docs[:12], 1):
        lines.append(f"{idx}. `{doc['file_path']}` - {doc['title']}（{doc.get('source') or '未标注'}，可信度 {doc.get('credibility_level')}）")
    return lines or ["- 今日无可引用新增材料。"]


def render_daily_markdown(domain: str, date: str, docs: list[dict[str, Any]]) -> str:
    label = domain_label(domain)
    top = docs[:5]
    terms = top_terms(docs)
    insights = work_insights(domain, docs)
    core = "今日信息不足，暂不形成强结论。" if not docs else f"今日 {label} 重点围绕 {', '.join(terms[:5]) or '若干主题'} 展开，应优先跟踪高可信、高重要性材料。"
    lines = [
        f"# {label} 日报：{date}",
        "",
        "## 一、今日核心结论",
        "",
        core,
        "",
        "## 二、今日最重要的 5 条信息",
        "",
    ]
    if top:
        for doc in top:
            lines.extend([f"### {doc['title']}", "", f"- 来源：{doc.get('source') or '未标注'}", f"- 可信度：{doc.get('credibility_level')}", f"- 重要性：{doc.get('importance_score')}/5", f"- 文件：`{doc.get('file_path')}`", "", doc.get("summary") or "暂无摘要", ""])
    else:
        lines.append("- 今日无新增入库信息。")
    lines.extend([
        "## 三、重点项目动态",
        "",
        "- " + ("；".join(d["title"] for d in top if d.get("doc_type") in {"project", "product"}) or "暂无明确项目动态。"),
        "",
        "## 四、新出现或值得关注的概念",
        "",
        "- " + ("、".join(terms) if terms else "暂无。"),
        "",
        "## 五、行业趋势判断",
        "",
        "基于今日入库材料，趋势判断仍需结合周报和 trend_memory 验证；单日信息只作为弱信号。",
        "",
        "## 六、风险与不确定性",
        "",
        "- 媒体与社区来源需要二次验证。",
        "- 自动网页采集可能只包含摘要，需要后续补充全文或官方来源。",
        "",
        "## 七、对我的工作 / 项目的启发",
        "",
        "### 1. 对多 Agent 知识汇集项目的启发",
        "",
        insights[0],
        "",
        "### 2. 对 OpenClaw / Codex / MCP / Skill 生态的启发",
        "",
        insights[1] if len(insights) > 1 else "暂无。",
        "",
        "### 3. 对银行 AI 赋能工作的启发",
        "",
        insights[2] if len(insights) > 2 else "暂无。",
        "",
        "### 4. 对 Web3 信息协作机制的启发",
        "",
        insights[3] if len(insights) > 3 else "暂无。",
        "",
        "## 八、明日继续跟踪事项",
        "",
        "- 跟踪今日高重要性材料是否出现官方后续、GitHub 更新、监管回应或项目进展。",
        "- 对高频概念补充 concepts 文件，避免日报碎片化。",
        "",
        "## 九、引用来源",
        "",
        *citation_lines(docs),
        "",
    ])
    return "\n".join(lines)


def markdown_to_html(markdown: str, title: str) -> str:
    body = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line:
            if in_list:
                body.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        body.append("</ul>")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f6f7f9; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 24px 72px; background: #fff; min-height: 100vh; box-shadow: 0 0 0 1px #e8eaed; }}
    h1 {{ font-size: 30px; line-height: 1.25; margin: 0 0 28px; }}
    h2 {{ font-size: 21px; margin: 34px 0 14px; padding-top: 18px; border-top: 1px solid #e6e8eb; }}
    h3 {{ font-size: 17px; margin: 22px 0 8px; }}
    p, li {{ font-size: 15px; line-height: 1.75; }}
    ul {{ padding-left: 22px; }}
    li {{ margin: 6px 0; }}
    code {{ background: #f0f2f4; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body><main>
{chr(10).join(body)}
</main></body></html>
"""


def write_daily_outputs(domain: str, date: str, markdown: str) -> dict[str, str]:
    md_path = VAULT_ROOT / domain / "daily" / f"{date}.md"
    html_path = VAULT_ROOT / "reports" / "daily" / f"{date}-{domain}.html"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(markdown_to_html(markdown, f"{domain_label(domain)} 日报 {date}"), encoding="utf-8")
    return {"markdown": md_path.relative_to(VAULT_ROOT).as_posix(), "html": html_path.relative_to(VAULT_ROOT).as_posix()}


def render_weekly_markdown(domain: str, week: str, docs: list[dict[str, Any]]) -> str:
    label = domain_label(domain)
    terms = top_terms(docs, 10)
    insights = work_insights(domain, docs)
    lines = [
        f"# {label} 周报：{week}",
        "",
        "## 一、本周核心判断",
        "",
        "本周资料不足，暂不形成强判断。" if not docs else f"本周核心主题集中在 {', '.join(terms[:6])}。需要把高频信息压缩为项目、概念和趋势记忆。",
        "",
        "## 二、本周关键事件回顾",
        "",
    ]
    for doc in docs[:10]:
        lines.append(f"- {doc['title']}（{doc.get('source') or '未标注'}，重要性 {doc.get('importance_score')}/5）")
    if not docs:
        lines.append("- 本周暂无新增材料。")
    lines.extend([
        "",
        "## 三、本周趋势变化",
        "",
        "- 新增趋势：" + ("、".join(terms[:4]) if terms else "暂无。"),
        "- 强化趋势：需要结合下周材料继续验证。",
        "- 减弱趋势：暂无足够证据。",
        "",
        "## 四、重点项目 / 公司 / 协议动态",
        "",
        "- " + ("；".join(d["title"] for d in docs[:5]) if docs else "暂无。"),
        "",
        "## 五、重要概念更新",
        "",
        "- " + ("、".join(terms) if terms else "暂无。"),
        "",
        "## 六、风险与不确定性",
        "",
        "- 周报为本地知识库归纳，不代表外部实时全量事实。",
        "- 低可信来源只作为弱信号。",
        "",
        "## 七、对我的工作 / 项目的启发",
        "",
        *[f"- {x}" for x in insights],
        "",
        "## 八、下周观察清单",
        "",
        "- 继续追踪高频主题是否出现官方确认、产品落地或监管变化。",
        "- 对重点项目和概念补充长期档案。",
        "",
        "## 九、引用来源",
        "",
        *citation_lines(docs),
        "",
    ])
    return "\n".join(lines)
