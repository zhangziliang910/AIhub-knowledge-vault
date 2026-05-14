# Knowledge Vault 最简使用手册

当前版本：1.0.1

这套系统只保留一个核心目标：

> 每天自动收集 AI / Web3 信息，沉淀为可检索知识，并在你提问时给出有来源的判断。

## 一句话架构

```text
信息源 / 手动资料
  -> Markdown 知识库
  -> SQLite 元数据
  -> 向量索引
  -> RAG 问答
  -> 日报 / 周报 / 专家记忆
```

## 日常只用这 5 个命令

在项目目录运行：

```powershell
cd C:\Users\50580\Desktop\PAB\AIhub\knowledge-vault
```

### 1. 每天自动跑一遍

```powershell
python main.py daily
```

它会完成：

- 联网采集 AI / Web3 来源
- 去重、筛选、评分
- 写入 raw / processed
- 同步 SQLite
- 同步向量库
- 生成 Markdown 日报
- 生成 HTML 日报

### 2. 每周生成趋势判断

```powershell
python main.py weekly
```

它会生成周报，并更新：

- `ai/trend_memory.md`
- `web3/trend_memory.md`
- `ai/expert_profile.md`
- `web3/expert_profile.md`

### 3. 上传或手动修改资料后同步

```powershell
python main.py sync --domain all
```

如果怀疑向量索引乱了，重建：

```powershell
python main.py sync --domain all --rebuild
```

### 4. 直接提问

```powershell
python main.py ask "Token 经济和 DAA 对企业 AI 应用有什么启发？"
```

### 5. 检查系统状态

```powershell
python main.py health
```

## 你每天真正需要看的文件

### AI 日报

```text
reports/daily/YYYY-MM-DD-ai.html
ai/daily/YYYY-MM-DD.md
```

### Web3 日报

```text
reports/daily/YYYY-MM-DD-web3.html
web3/daily/YYYY-MM-DD.md
```

### 周趋势记忆

```text
ai/trend_memory.md
web3/trend_memory.md
```

### 专家认知框架

```text
ai/expert_profile.md
web3/expert_profile.md
```

## 目录只需要理解这几类

```text
ai/
  raw/          原始资料
  processed/    可检索的结构化笔记
  daily/        每日简报
  weekly/       每周总结
  projects/     项目档案
  concepts/     概念档案

web3/
  同上，和 AI 严格隔离

configs/
  sources.yaml          信息源
  expert_config.yaml    你的工作关注点
  schedule_config.yaml  自动运行时间

data/
  sqlite/       结构化索引
  vector/       本地向量索引

reports/
  daily/        可读性更好的 HTML 日报

logs/
  runs/         每次 pipeline 运行报告
  errors/       错误日志
```

## 信息源只改一个文件

新增、关闭、调整来源，只改：

```text
configs/sources.yaml
```

不要改采集代码。

## 系统角色分工

这套系统可以简化成 3 层：

```text
Collector：负责抓信息
Researcher：负责筛选、摘要、入库、索引
Expert：负责问答、趋势判断、工作建议
```

对应到脚本：

```text
Collector   -> collect_sources.py
Researcher  -> ingest_pipeline.py + sync_markdown_to_db.py + sync_markdown_to_vector.py
Expert      -> rag_answer.py + generate_daily_brief.py + generate_weekly_brief.py
```

日常不要直接调用这些脚本，使用 `main.py` 即可。

## 当前最重要的判断框架

这套系统后续应重点围绕四个问题沉淀：

1. 今天 AI / Web3 发生了什么？
2. 哪些变化真正重要？
3. 对我的项目和工作有什么影响？
4. 我下一步应该跟踪或行动什么？

尤其要把 AI 信息转成这几类判断：

- Agent 是否真的产生工作结果
- Token 消耗是否转化为有效产出
- 企业是否需要预算、审计、权限和成本治理
- 对银行 AI 赋能、多 Agent 知识汇集、OpenClaw / Codex / MCP 生态有什么启发

## 保持系统不乱的原则

1. 日常入口只用 `main.py`。
2. 信息源只改 `configs/sources.yaml`。
3. 用户工作背景只改 `configs/expert_config.yaml`。
4. 人看的内容优先看 `reports/daily/*.html`、`daily/`、`weekly/`、`trend_memory.md`。
5. 机器用的内容放在 `data/`，不要手动改。
6. `scripts/` 是内部实现层，除调试外不要直接碰。

## 推荐自动化

Codex automation 或本地定时任务只需要执行：

```powershell
python main.py daily
```

每周执行：

```powershell
python main.py weekly
```

这样系统就不会因为入口过多而变复杂。
