# 情报来源注册表

默认优先级：

- A 级：官方公告、项目博客、论文、GitHub、监管文件。
- B 级：主流媒体、专业行业媒体。
- C 级：KOL、社区讨论、社交媒体。
- D 级：未验证爆料、二手搬运。

当前自动采集来源配置见：

```text
configs/sources_config.yaml
```

首批来源：

- OpenAI News：AI / 官方 / A
- Anthropic News：AI / 官方 / A
- Google DeepMind Blog：AI / 官方 / A
- Ethereum Foundation Blog：Web3 / 官方 / A
- Solana News：Web3 / 官方 / A
- TechCrunch AI：AI / 媒体 / B
- CoinDesk：Web3 / 媒体 / B

建议后续增加：

- arXiv AI / ML 相关分类
- GitHub release feed
- SEC / CFTC / EU 官方监管更新
- 重点项目官方博客
- 高质量研究机构与安全团队博客
