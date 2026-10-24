# life-pipeline · 数字永生流水线

> 我的个人数据引擎：每天写的日记，自动变成标签、双链、周度观察、认知画像和访谈问题。
> 15 个 Python 模块 + 飞书多维表格 + Obsidian vault，一条命令跑完七步。

![Python](https://img.shields.io/badge/Python-3.x-3776ab)
![Feishu](https://img.shields.io/badge/飞书-Bitable%20API-00d6b9)
![Obsidian](https://img.shields.io/badge/Obsidian-vault-7c3aed)

## 这是什么

我每天在 Obsidian 写日记，这套流水线把日记自动加工成结构化资产：

```
日记（非结构化文本）
  → 自动打标签 + 双向链接（词典规则，零 NLP 依赖）
  → 周度观察（这周在做什么/想什么）
  → Wiki 实体页维护（人物/概念自动建 stub）
  → 认知画像更新（检测 6 类认知变化，只追加不重写）
  → 访谈问题生成（每周深度访谈的题库）
  → 飞书多维表格同步（时间记录 → 周报）
```

## 为什么值得看

这不是玩具脚本，是一个**跑了几个月的生产系统**，体现了几个工程决策：

- **规则优于模型**：标签用词典+规则而非 NLP API——零依赖、零成本、可解释、可调试
- **宁少勿滥**：每篇日记 2-6 个标签，按优先级排序
- **只追加不重写**：认知画像保留演化历史，不覆盖旧数据
- **爆炸半径表驱动开发**：改任何模块前先查依赖表评估影响面（见下）

## 模块爆炸半径表

改代码前必读——这张表本身就是这套系统的核心工程实践：

| 改这个文件 | 影响哪些文件 | 风险等级 |
|-----------|-------------|---------|
| `utils.py` | tag_diary / analyze_diary / update_wiki / daily_draft / update_cognition / dbs_scan | **高**（6 个下游共享 frontmatter 解析） |
| `config.py` | 几乎所有模块 | **极高**（全局配置中心） |
| `feishu_client.py` | sync_bitable / pipeline | **高**（飞书 API 封装层） |
| `config_loader.py` | tag_diary / analyze_diary | 中 |
| `pipeline.py` | CLI 入口 | 中 |
| 其余 10 个模块 | 只被 pipeline 调用 | 低 |

规则：改标"高/极高"的文件，必须手动跑一遍 `python pipeline.py weekly --dry-run` 验证。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入飞书凭证和 vault 路径
python pipeline.py weekly --dry-run   # 干跑预览，不写文件
python pipeline.py weekly             # 正式跑七步
```

## 关键文件

- `pipeline_rules.md` — 指标驱动 + 失败处理规则
- `interview_rules.md` — 每周深度访谈流程
- `config/*.yaml` — 标签规则、商业信号、实体词典（规则引擎的"数据库"）
- `examples/` — 飞书 API 操作示例（发消息/日历/文档/审批）
