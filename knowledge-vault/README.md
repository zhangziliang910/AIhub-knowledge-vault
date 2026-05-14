# 领域情报采集与专家问答知识库

本项目用于持续搜集、整理和沉淀 AI 圈与 Web3 圈的信息。当前版本已经从轻量版升级为标准版：

```text
信息录入 / 信息采集
        ↓
Markdown 原文与结构化笔记
        ↓
SQLite 元数据索引
        ↓
向量数据库 embedding
        ↓
领域路由
        ↓
RAG 检索
        ↓
AI / Web3 专家问答
```

设计原则：

- Markdown 作为长期可读知识库，方便人工查看和 Git 管理。
- SQLite 保存结构化元数据、chunk、问题记录。
- 本地向量库保存 AI / Web3 独立集合，默认无外部依赖。
- Embedding 通过统一接口封装，默认使用 deterministic mock embedding，可后续替换为 OpenAI、DashScope、Voyage、BGE、Jina 等。
- AI 与 Web3 目录、SQLite domain、向量集合保持隔离；交叉问题会同时检索两个领域。

## 目录结构

```text
knowledge-vault/
  ai/
    raw/
    processed/
    daily/
    weekly/
    projects/
    people/
    companies/
    concepts/
    index.md
  web3/
    raw/
    processed/
    daily/
    weekly/
    projects/
    people/
    companies/
    concepts/
    index.md
  shared/
    sources/
    prompts/
    templates/
    taxonomy.md
    routing_rules.md
  data/
    sqlite/
      knowledge.db
    vector/
      ai/
      web3/
    exports/
  scripts/
    db_init.py
    db_upsert.py
    build_index.py
    chunk_documents.py
    embed_documents.py
    retrieve.py
    rag_answer.py
    route_question.py
    sync_markdown_to_db.py
    sync_markdown_to_vector.py
    health_check.py
  configs/
    app_config.yaml
    embedding_config.yaml
    retrieval_config.yaml
    domain_config.yaml
  logs/
    ingestion/
    indexing/
    retrieval/
    errors/
    runs/
```

## 安装依赖

当前标准版只依赖 Python 标准库即可运行。若安装了 `PyYAML`，配置解析会自动使用它；未安装时会使用内置的轻量 YAML 解析器。

```powershell
cd C:\Users\50580\Desktop\PAB\AIhub\knowledge-vault
python --version
```

## 初始化数据库

```powershell
python scripts/db_init.py
```

数据库路径：

```text
data/sqlite/knowledge.db
```

包含表：

- `documents`
- `document_tags`
- `document_entities`
- `chunks`
- `sources`
- `questions`
- `sync_state`

## 录入信息

基础版录入脚本仍可继续使用：

```powershell
python scripts/vault.py ingest `
  --title "OpenAI 发布新模型能力更新" `
  --body "这里填写正文。" `
  --url "https://example.com/news" `
  --source "OpenAI official blog" `
  --published-at "2026-05-12"
```

录入后建议同步 SQLite 和向量库：

```powershell
python scripts/sync_markdown_to_db.py --domain all
python scripts/sync_markdown_to_vector.py --domain all
```

## 自主采集在线信息

系统现在支持从配置好的来源主动获取 AI / Web3 情报。

来源配置：

```text
configs/sources.yaml
configs/sources_config.yaml
```

来源注册表：

```text
shared/sources/source_registry.md
```

先 dry-run 预览，不入库：

```powershell
python scripts/collect_web.py --domain all --limit-per-source 1 --dry-run
```

真实采集，并自动同步 SQLite 和向量库：

```powershell
python scripts/collect_web.py --domain all --limit-per-source 3 --sync
```

只采集 AI：

```powershell
python scripts/collect_web.py --domain ai --limit-per-source 3 --sync
```

只采集 Web3：

```powershell
python scripts/collect_web.py --domain web3 --limit-per-source 3 --sync
```

统一入口：

```powershell
python main.py collect --domain all --limit-per-source 3 --sync
```

当前首批来源包括 OpenAI、Anthropic、Google DeepMind、Ethereum Foundation、Solana、TechCrunch AI、CoinDesk。采集器优先读取 RSS/Atom；如果来源没有可用 feed，会退回网页链接发现。所有采集内容仍然走原来的 `vault.py ingest`，因此会复用领域判断、去重、Markdown 落盘、项目档案更新等能力。

AI 自动化采集还接入了 AI HOT：

```text
https://aihot.virxact.com
```

配置位置：

```text
configs/sources.yaml
```

来源名称：

```text
AI HOT 精选
```

采集器会调用 AI HOT 公开 API，并按要求带 `aihot-skill` User-Agent。该来源会进入每日 AI pipeline，与 OpenAI、Anthropic、Hugging Face、GitHub Trending 等来源一起参与筛选、入库、日报和 RAG。

## 自动专家系统 Pipeline

标准版之上新增了自动运转 pipeline：

```text
自动采集 -> 自动筛选 -> 自动沉淀 -> 自动总结 -> 辅助决策
```

核心命令：

```powershell
python scripts/collect_sources.py --domain ai
python scripts/collect_sources.py --domain web3
python scripts/filter_items.py --domain all
python scripts/ingest_pipeline.py --domain all
python scripts/run_daily_pipeline.py
python scripts/run_weekly_pipeline.py
```

每日 pipeline 会执行：

1. 从 `configs/sources.yaml` 读取来源并采集。
2. 写入 `data/collections/YYYY-MM-DD/ai.jsonl` 和 `web3.jsonl`。
3. 筛选、去重、评分。
4. 调用现有 `vault.py ingest` 入库。
5. 对英文材料保留英文原文，并在下方追加中文翻译 / 中文要点。
6. 同步 SQLite 和向量库。
7. 生成 AI / Web3 日报。
8. 生成可读 HTML 日报。
9. 写运行报告。

英文材料处理规则：

```text
英文原文保留在原位置
下方追加 “中文翻译 / 中文要点”
```

可手动补翻当天内容：

```powershell
python scripts/add_chinese_translation.py --domain all --date 2026-05-13
python scripts/sync_markdown_to_db.py --domain all
python scripts/sync_markdown_to_vector.py --domain all
```

### 使用 OpenAI API 翻译

翻译配置：

```text
configs/translation_config.yaml
```

默认 provider 为 `openai`，模型配置为 `gpt-5.2`。API Key 只从环境变量读取：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
python scripts/add_chinese_translation.py --domain all --date 2026-05-13 --force
```

如果没有配置 `OPENAI_API_KEY`，脚本会自动退回到本地 mock 翻译/中文要点，不会中断 pipeline。

HTML 日报是主要阅读版本：

```text
reports/daily/YYYY-MM-DD-ai.html
reports/daily/YYYY-MM-DD-web3.html
```

Markdown 日报继续用于知识库和 RAG：

```text
ai/daily/YYYY-MM-DD.md
web3/daily/YYYY-MM-DD.md
```

每周 pipeline 会执行：

```powershell
python scripts/run_weekly_pipeline.py
```

输出：

```text
ai/weekly/YYYY-Wxx.md
web3/weekly/YYYY-Wxx.md
ai/trend_memory.md
web3/trend_memory.md
ai/expert_profile.md
web3/expert_profile.md
```

## 调度

本地常驻调度：

```powershell
python scripts/scheduler.py start
```

手动触发：

```powershell
python scripts/scheduler.py run-daily
python scripts/scheduler.py run-evening
python scripts/scheduler.py run-weekly
```

Windows 任务计划程序可分别调用：

```powershell
cd C:\Users\50580\Desktop\PAB\AIhub\knowledge-vault
python scripts/run_daily_pipeline.py
python scripts/run_daily_pipeline.py --mode evening
python scripts/run_weekly_pipeline.py
```

Cron 示例：

```bash
# 每天 07:30 运行每日知识积累
30 7 * * * cd /path/to/knowledge-vault && /usr/bin/python scripts/run_daily_pipeline.py >> logs/runs/daily.log 2>&1

# 每天 20:30 运行晚间补充
30 20 * * * cd /path/to/knowledge-vault && /usr/bin/python scripts/run_daily_pipeline.py --mode evening >> logs/runs/evening.log 2>&1

# 每周日 21:00 运行周报和专家更新
0 21 * * 0 cd /path/to/knowledge-vault && /usr/bin/python scripts/run_weekly_pipeline.py >> logs/runs/weekly.log 2>&1
```

## 同步 Markdown 到 SQLite

```powershell
python scripts/sync_markdown_to_db.py --domain all
python scripts/sync_markdown_to_db.py --domain ai
python scripts/sync_markdown_to_db.py --domain web3
```

同步逻辑：

- 扫描 AI / Web3 Markdown 文件。
- 自动读取 frontmatter；没有 frontmatter 时从标题和正文尽量提取。
- 生成 `content_hash` 判断文件是否变化。
- 新文件写入 `documents`。
- 变化文件更新 `documents`、`document_tags`、`document_entities`。
- 删除或移动的文件标记为 `archived`，不硬删除。
- 日志写入 `logs/indexing/`。

## 同步 Markdown 到向量库

```powershell
python scripts/sync_markdown_to_vector.py --domain all
python scripts/sync_markdown_to_vector.py --domain ai --rebuild
python scripts/sync_markdown_to_vector.py --domain web3 --rebuild
```

向量集合：

- `data/vector/ai/ai_knowledge.json`
- `data/vector/web3/web3_knowledge.json`

进入向量库的目录：

- `processed/`
- `daily/`
- `weekly/`
- `projects/`
- `concepts/`
- `index.md`，低权重

`raw/` 默认不进入向量库。

## 文档切块

```powershell
python scripts/chunk_documents.py --domain ai
```

切块规则：

- 优先按 Markdown 标题切块。
- 单 chunk 默认最大约 `1200` 字符。
- 长段落保留 overlap，默认 `150` 字符。
- 每个 chunk 记录 `document_id`、`domain`、`file_path`、`heading`、`token_count`。

配置位置：

```text
configs/embedding_config.yaml
```

## 问题路由

```powershell
python scripts/route_question.py "Web3 最近 RWA 有什么值得关注的变化？"
```

路由输出：

```json
{
  "domain": "ai | web3 | cross | unknown",
  "reason": "判断理由",
  "keywords": [],
  "suggested_filters": {}
}
```

规则文件：

- `shared/routing_rules.md`
- `configs/domain_config.yaml`

## 检索

```powershell
python scripts/retrieve.py --question "最近 AI Agent 有什么趋势？" --domain ai --top_k 8
```

支持过滤：

```powershell
python scripts/retrieve.py `
  --question "最近 AI Agent 有什么趋势？" `
  --domain ai `
  --credibility A,B `
  --min-importance 4 `
  --start-date 2026-01-01
```

检索方式：

- SQLite / Markdown 关键词检索。
- 本地向量语义检索。
- 元数据过滤。
- 混合排序重排。

排序权重配置：

```text
configs/retrieval_config.yaml
```

## RAG 问答

```powershell
python scripts/rag_answer.py --question "Solana 最近生态有什么值得关注的变化？"
```

回答会尽量区分：

- 已归档事实；
- 来源观点；
- 系统推测；
- 信息不足。

回答会保存到 `questions` 表，方便后续优化问答效果。

## 统一入口

```powershell
python main.py init
python main.py sync-db --domain all
python main.py sync-vector --domain all
python main.py sync-vector --domain ai --rebuild
python main.py ask "最近 AI 圈有什么重要趋势？"
python main.py collect --domain all --limit-per-source 3 --sync
python main.py health
```

## 重建索引

一键构建 SQLite 和向量索引：

```powershell
python scripts/build_index.py
```

手动重建：

```powershell
python scripts/db_init.py
python scripts/sync_markdown_to_db.py --domain all
python scripts/sync_markdown_to_vector.py --domain all --rebuild
```

## 健康检查

```powershell
python scripts/health_check.py
```

检查内容：

- 目录是否完整；
- SQLite 是否存在；
- 表结构是否完整；
- Markdown 文件数量；
- documents 数量；
- chunks 数量；
- 向量库是否可用；
- AI / Web3 数据情况；
- embedding failed chunk；
- 最近一次同步时间。

## 常见问题

### 没有 API Key 能跑吗？

可以。默认 embedding provider 是 `mock`，使用 deterministic hash embedding，适合打通流程和本地开发。生产使用建议替换为正式 embedding 模型。

### 为什么 RAG 回答说资料不足？

RAG 只基于本地已同步内容回答。如果知识库只有空日报、空周报或索引页，系统会避免编造事实。先录入材料，再同步数据库和向量库。

### 如何换 embedding 模型？

修改：

```text
configs/embedding_config.yaml
```

然后在 `scripts/lib/embedding.py` 中新增 provider 实现即可。业务脚本只依赖 `EmbeddingProvider` 接口。

### 如何接 Chroma / LanceDB / FAISS？

当前默认本地 JSON 向量库，保证零依赖可运行。后续可以在 `scripts/lib/vector_store.py` 中增加新的 store 实现，并保持 `upsert / query / delete_document / reset` 接口不变。

## 后续扩展方向

- 接入正式 embedding 模型。
- 接入 Chroma、LanceDB 或 FAISS。
- 增加 RSS、GitHub、官方博客、X/Reddit 自动采集器。
- 增加多 Agent：采集 Agent、清洗 Agent、研究 Agent、问答 Agent。
- 增加 Web 前端。
- 增加人工审核工作流和可信来源管理后台。
- 将项目、人物、公司、概念档案自动更新为更稳定的知识图谱结构。
