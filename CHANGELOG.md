# Changelog — Markdown 播客工作室

所有对本专家包的可见改动都记录于此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [1.1.0] — 2026-08-20 — 流程管控专家评审应用

> **变更驱动**：上一轮"流程管控专家（30+ 年经验）"诊断报告应用。
> **变更范围**：纯**专家团治理层**（agents/ + skills/*.md + README + plugin.json）。**不动 `skills/md-podcast-studio/scripts/src/`**（冻结资产）。
> **回滚**：`git checkout v1.0.0 -- .` 或 `rsync -a --delete .archive/v1.0.0/ ./`

### Added（新增）

- **SOP 元数据（metadata）**：在 `skills/md-podcast-studio/SKILL.md` 头部加 frontmatter 元信息：`version` / `owner` / `effective_from` / `change_log`。流程治理的最小元数据。→ **R3**
- **决策矩阵（DecisionMatrix）**：在 `SKILL.md` 加 "决策矩阵" 章节，覆盖 5 个决策点：Phase 0 脚手架检测、Phase 1 plan_episodes fallback、Phase 1.5 卡兹克触发、Phase 3 后端选择、Phase 4 部署路径。每个决策点：触发条件 + 推荐 + 兜底。→ **Y1**
- **RACI 矩阵**：在 `SKILL.md` 加 "RACI 矩阵" 章节，覆盖 7 阶段 × 4 角色（主理人 / 成员 / 用户 / 系统）。明确 A 与 R，避免主理人代写成员产出。→ **Y3**
- **ErrorPolicy 表**：新建 `skills/md-podcast-studio/references/error-policy.md`。4 类错误策略（STOP_AND_NOTIFY / RETRY_WITH_BACKOFF / FALLBACK_BACKEND / DEGRADE）+ 每阶段应用示例。→ **Y2**
- **Metrics 采集建议**：新建 `skills/md-podcast-studio/references/metrics.md`。每阶段采集的指标 + 反馈环入口（写到 `output/metrics/<date>.json`）。文档化建议，实际采集需 src/ 改造（不在 v1.1.0 范围）。→ **Y4**
- **PII 扫描建议**：新建 `skills/md-podcast-studio/references/pii-scan.md`。草稿出口 PII 扫描（私人姓名 / 电话 / 邮箱 → `[REDACTED]`）。文档化建议。→ **G3**
- **2 张流程图**：在 `SKILL.md` 加主流程图（happy path，Phase 0→1→2→3→4→5，6 节点）+ 异常流图（retry / fallback / skip / fallback backend）。→ **G1**
- **多门禁字段定义（humanize_stage / audio_reviewed）**：在 `config-spec.md` 文档化 2 个新字段（`humanize_stage`：`skeleton/humanized/reviewed/frozen`；`audio_reviewed`：`bool`）。代码层 `prepare --mark-reviewed` 不强制实现，向后兼容。→ **R2 简化**
- **并行评审配置项**：在 `SKILL.md` 加 `parallel_review: bool` 配置项说明：理论上 Phase 1.5 与 Phase 2 评审门可并行。文档化建议。→ **G4**
- **版本元数据（plugin.json）**：`.codebuddy-plugin/plugin.json` 加 `version: "1.1.0"` 字段；`description` / `displayDescription` 更新以反映 v1.1.0 关键能力（多门禁 + 决策矩阵 + RACI + episode_hash）。
- **本 CHANGELOG.md**。
- **`.archive/` 目录 + `.archive/README.md`**：物理冗余备份指南，v1.0.0 baseline 已 snapshot。

### Changed（变更）

- **`source_hash` → `episode_hash` 改名（文档层）**：在 `references/hard-constraints.md` C6 与 `references/config-spec.md` 把 `source_hash` 改名为 `episode_hash`（更准确反映"它是当前集内容指纹，非源稿哈希"）。代码层 `source_hash` 字段保留作为别名，向后兼容不破坏现有 `prepare/build`。→ **R1**
- **hard-constraints C6 澄清**：明确"卡兹克抛光后 episode_hash 实际已变，build 视为新草稿重生成 mp3，是预期（不是数据血缘断裂）"。→ **R1**
- **`hard-constraints.md` 新增 C10 — episode_hash 命名约定**：见 C6 改名说明，源稿哈希另有 `source_text_hash`。
- **agents/*.md 同步 v1.1.0**：5 个 agent MD 文件（team-lead / script-editor / script-humanizer / voice-director / publishing-engineer）全部对齐 v1.1.0 关键变更（episode_hash 改名、humanize_stage 新字段、决策矩阵、RACI）。不动每个角色的核心职责边界。
- **`README.md`**：加版本号、CHANGELOG 摘要、回滚说明、关键能力 v1.1.0 摘要。

### Not Changed（未改，受范围限制）

- `skills/md-podcast-studio/scripts/src/**` — **冻结资产**（"代码是冻结资产，包装期不修改逻辑"）。若要落实 episode_hash 改名 / humanize_stage 字段 / metrics 采集，需 myPodcast 仓库演进后重新打包。
- `skills/md-podcast-studio/bin/scaffold` — 冻结资产。
- `skills/md-podcast-studio/templates/**` — 冻结资产。

### Future / Out of Scope（已识别但不在 v1.1.0）

- metrics 实际采集（需 src/ 改造）
- PII 扫描实际接入 prepare 出口（需 src/ 改造）
- ErrorPolicy 自动 fallback 实际接入（需 src/ 改造）
- `naming_enforce` 自动接入 prepare/CI（hard-constraints 已有 ⚠ 文档/代码不一致声明）

---

## [1.0.0] — 2026-08-20 — Baseline（流程管控专家评审前）

### 概要
- **5 人团队**：team-lead（播客制作总监）/ script-editor（脚本编辑）/ voice-director（配音导演）/ publishing-engineer（发布工程师）
- **skills/md-podcast-studio/**：SKILL.md + 4 references（command-reference / config-spec / hard-constraints / troubleshooting）+ templates（config.yaml + 工程脚手架 + 暗色站点 + gh-pages 工作流）
- **scripts/src/**：22 个 Python 模块（prepare / build / backends / generate / split / 等），冻结资产
- **9 条硬约束** C1-C9：ffmpeg concat、MiniMax TTS、LLM 调用、yaml.safe_dump、分集剔 `---`、build 只读、退出码、决策门跳过、fish-speech 国内 4 坑
- **avatar 5 张**：expert + 4 成员头像

### 工作流（v1.0.0）
- Phase 0 脚手架 → Phase 1 prepare（script-editor）→ Phase 2 评审门（ai_stage）→ Phase 3 build（TTS + 站点）→ Phase 4 部署（gh-pages）
- ai_stage 4 阶段：skeleton → generated → reviewed → frozen

### 已知问题（v1.0.0）
- `naming_enforce` 未接入 prepare/CI（hard-constraints ⚠）
- 评审门只有 1 道（脚本评审），卡兹克版与音频版无独立门禁
- 决策点缺客观触发器（"是否走交互"、"是否走卡兹克"、"选哪个 TTS 后端"全靠用户原话）
- 无 RACI 矩阵（主理人可能代写成员产出）
- 无 ErrorPolicy 表（异常流只覆盖一半）
- 无 metrics 采集（流程不可度量）
- 无版本元数据（SOP 无法治理）