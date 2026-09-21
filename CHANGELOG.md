# Changelog — Markdown 播客工作室

所有对本专家包的可见改动都记录于此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [1.2.2] — 2026-09-21 — 一次真实上线的事故沉淀（**文档层**修正）

> **变更驱动**：用本专家包**真实上线了一集播客**（单集 duo、`qwen3-local` 本地 TTS、GitHub Pages），
> 端到端跑通；过程中发现 3 处「会把人带偏」的问题（2 处误判故障 + 1 处误判通过）→ 沉淀为文档层修正。
> **变更范围**：`skills/md-podcast-studio/SKILL.md` + `references/{troubleshooting,hard-constraints,command-reference}.md`
> + `agents/{publishing-engineer,voice-director,markdown-podcast-studio-team-lead}.md`。
> **`scripts/src/` 未改动**（仍为 v1.2.1 快照，见末尾「已知漂移」）。
> **回滚**：`git checkout v1.2.1-patch -- .`

### Added

- **hard-constraints C12（新增）— `--force` 是一次性诊断，跑完必须还原**：
  `--force` 让全部集数重走 `register_episode()`（`eps.insert(0, entry)`）→
  ① 所有 `shownotes.md` 的 `date` 刷成当天；② manifest/RSS 顺序被打乱（`build_feed()` **不排序**，数组顺序即发布顺序）。
  实测在 82 集仓库上产生 ~82 处脏改动、新集从第 1 位掉到第 27 位。附完整还原命令与成功判据（diff = 纯新增、0 删除）。
- **发布验收铁律**（hard-constraints 末节 + troubleshooting §6 + command-reference §6）：
  顺序语义（新集必在第 1 位）/ gh-pages 两段部署（**权威判据是 `git fetch` 后的 blob，不是 HTTP**）/
  gh-pages 上 mp3 必须是裸 blob（Pages 不支持 LFS）/ `index.html` 是纯 JS 外壳不可作判据。
- **troubleshooting §7 交付纪律** 与改写后的「真实验证顺序（commit 前）」（把「还原」列为必做步骤）。
- 排错新增条目：思考型模型 content 空 / 非交互 shell 不加载 zshrc / `--only` 匹配文件名而非 slug /
  快捷分支丢 duo 音色 / 长任务在 teammate 会话被 SIGKILL / stdout 块缓冲导致"假卡死" / 整轨静音的检出。

### Fixed（文档层纠正）

- **C3 `max_tokens` 指引**：原文「默认 4000」对**思考型模型**是错的——reasoning 与正文**共享** `max_tokens`，
  实测 1600 字输入 → reasoning 1044 + 正文 458 tokens，**12000 才稳**；症状是 `finish_reason` 正常但 **content 为空**。
  另补充：`thinking:{type:"disabled"}` **不是所有端点都认**（MiniMax 认，SCNet 忽略），不能当通用省 token 手段。
- **C8 决策门跳过规则**：补上「快捷分支必须同时拿到 `host_voice`/`guest_voice`」，并说明
  **丢失时不报错、build 会静默回退默认音色** → 验收要核 frontmatter。
- **C3 密钥解析**：补充 `cfg.api_key_env` 语义（显式声明时只认该 env，不回落默认列表）。

### Changed（agents 职责细化）

- `publishing-engineer`：硬约束新增「`--force` 跑完必须还原」「上线验收看 gh-pages blob」「新集必须在第 1 位」。
- `voice-director`：音频验收从"时长/体积/文件头"升级为**四项**（新增 `ffmpeg -af volumedetect` 排除整轨静音）；
  新增「日志停滞 ≠ 卡死，用服务计数器判活」「长任务必须在主会话跑」。
- `markdown-podcast-studio-team-lead`：Phase 4 补 C12 还原检查、gh-pages 验收、长任务调度纪律。

### Known Drift（已知漂移 — **待决策，本次未处理**）

- 本包 `scripts/src/` 与真实运行仓库已**分叉**：
  - 本包独有：`episode_hash.py` / `error_policy.py` / `metrics.py` / `pii_scan.py` / `polish.py`
  - 真实仓库独有：`llm.py`（由 `polish.py` 改名而来）/ `analytics.py`
  - 双方同名文件内容也不同：`build.py`(389 vs 357) / `stages.py`(254 vs 118) / `tts.py`(200 vs 68) /
    `feed.py` / `prepare.py` / `generate.py` / `prosody.py` / `voicecaster.py`
  - 真实仓库已支持的 TTS 后端（如 `qwen3-local`）与写稿后端（SCNet DeepSeek-V4.1-Flash）**不在本包 `backends/` 中**
- ⇒ 从本包 `scaffold` 出的新工程**不会**包含这些演进。**重新打包 `scripts/src/` 是独立动作，需单独评估**
  （直接覆盖会删掉本包自己的 `episode_hash/metrics/pii_scan/error_policy` 及其 57 个单测）。

---

## [1.2.1] — 2026-08-20 — 卡兹克必做强阻断 + 4 候选落地

> **变更驱动**：用户要求"继续 v1.2.1 且把卡兹克审稿设定为必做"。这是 v1.2.0 的延伸 + **卡兹克从可选升级为必做强阻断**（hard-constraint C11）。
> **变更范围**：`scripts/src/` 改造（卡兹克门禁 / llm_verify / phase5_summary / ErrorPolicy 标准化）+ 新增 `tests/` 单测套件 + 文档同步。**首次在 src/ 落地"硬门禁"逻辑**（v1.2.0 主要是 metrics/PII/fallback 软接入）。
> **回滚**：`git checkout v1.2.0 -- .` 或 `rsync -a --delete .archive/v1.2.0/ ./`

### Added（src/ 硬门禁 + 4 候选落地）

- **卡兹克必做强阻断（hard-constraint C11 新增）**：
 - `stages.py`：`HUMANIZE_*` 4 阶段常量 + `humanize_stage_of` / `is_humanize_approved` / `humanize_stage_warning` / `set_humanize_stage` / `mark_humanize_reviewed` / `init_humanize_stage`
 - `build.py:run_one()` Phase 3 入口加 humanize_stage 检查 → `error_policy.stop_and_notify("phase1.5", ...)` 标准化抛错
 - `build.py:run()` 加 `--skip-humanize` flag（豁免：CI / 烟雾测试）
 - `prepare.py:prepare_file()` 草稿落盘前 `init_humanize_stage(f)`
 - **关键决策**：卡兹克 LLM 失败 → RETRY(3) → STOP_AND_NOTIFY（不静默降级到原文）
- **`pii_scan.py` llm_verify 接线**：
 - 中文姓名启发式上下文正则（`CEO X` / `X 先生` / `X 老师` 等）
 - 调用 `polish.llm_complete()` 做二次校验
 - 失败 fallback 正则-only（不阻塞）
 - Trade-off：边界严格（lookbehind 排除"汉字+姓名"），宁可漏几个，不要误杀
- **`metrics.py` emit_phase5_summary 自动调用**：在 `build.py:run()` 末尾无条件 emit，采集 first_attempt_success + phases_succeeded/degraded
- **`error_policy.py` 标准化**：`stop_and_notify(stage, message, hint)` / `degrade(stage, message, reason)` helper
- **`tests/` 套件**（新目录）：`test_episode_hash.py` (9) / `test_metrics.py` (11) / `test_pii_scan.py` (11) / `test_error_policy.py` (13) / `test_stages.py` (13) = **57 tests passing**
- **`tests/conftest.py`**：自动加 `scripts/` 到 sys.path，pytest discoverable
- **`references/hard-constraints.md` C11 新增**：卡兹克活人感抛光必做强阻断（10 条硬约束，从 v1.2.0 的 9 条扩展）

### Changed

- **`stages.py`**：扩展支持 humanize_stage 4 阶段生命周期（与 ai_stage 并列），公开 `humanize_stage_of` / `is_humanize_approved` 等函数
- **`prepare.py:prepare_file()`**：草稿落盘后追加 `init_humanize_stage(f)`（best-effort，失败不阻塞）
- **`build.py:run()`**：末尾 emit `phase5_summary`（best-effort，失败不阻塞）
- **`.codebuddy-plugin/plugin.json`**：version 1.2.0 → 1.2.1 / description 改写（"REQUIRED humanize"）
- **5 个 agent MD 文件**：sop_version + description 同步（卡兹克从"可选"升级为"REQUIRED"）
- **`README.md` / `SKILL.md`**：v1.2.1 关键能力 + C11 + 57 测试段

### 兼容性（关键）

- `build_episode_audio(...)` / `stages.mark_reviewed(...)` / `prepare_file(...)`：**接口不变**，内部追加 humanize_stage 生命周期
- `register_episode(..., body="")`：**接口不变**（v1.2.0 已 keyword-only）
- `--skip-humanize` flag：**可选参数**，默认 False（强阻断开启）

### Smoke Test（已通过）

- ✅ 57/57 单测通过（pytest）
- ✅ 9 模块 import 成功
- ✅ 卡兹克门禁：草稿 humanize_stage=skeleton → build 抛 PipelineError
- ✅ --skip-humanize 豁免
- ✅ PII 中文姓名识别：CEO 张三先生 → "张三"（边界严格 trade-off）
- ✅ ErrorPolicy stop_and_notify → raise PipelineError 含 stage/hint

### Future / Out of Scope（v1.2.2 候选）

- `metrics.cycle_time_hours` 全 cycle 估算（当前 build 内难算，用上次 phase1 时间戳推算）
- `ErrorPolicy.STOP_NOTIFY` 接入告警系统（Slack / email）
- ErrorPolicy DEGRADE 接入 validate_script 软告警场景
- 集成测试（build.py / prepare.py / tts.py 需外部依赖）
- `--skip-humanize` 加更细粒度

---

## [1.2.0] — 2026-08-20 — src/ 实际改造（4 候选落地）

> **变更驱动**：v1.1.0/v1.1.1 文档化的 metrics / PII / ErrorPolicy fallback / 真正 episode_hash 从"建议"变为"实现"。
> **变更范围**：`scripts/src/` 实际改造 + 文档同步。**首次动冻结资产**，按 hard-constraints C1（不动 src/ 业务逻辑）部分妥协 — 但所有改动都向后兼容 + 不破坏 ai_stage / source_hash 契约。
> **回滚**：`git checkout v1.1.1 -- .`

### Added（src/ 实际改造）

- **`scripts/src/episode_hash.py`（新文件，~110 行）**：草稿正文（不含 frontmatter）SHA256 前 16 位指纹。导出 `hash_episode_body` / `episode_hash_of` / `split_frontmatter` / `should_resynthesize`。**这是 v1.1.0 误诊的"episode_hash 命名约定"的真正实现**，但语义与 v1.1.0 错描述不同（v1.1.0 误把 source_hash 改名 episode_hash；v1.2.0 真正新增 episode_hash 作为草稿正文指纹）。
- **`scripts/src/metrics.py`（新文件，~190 行）**：每阶段指标采集。导出 `Timer` + `emit_phase1/1.5/2/3/4/5_summary` + `read_phase`。写到 `output/metrics/<date>/phase*.json`，原子写入。
- **`scripts/src/pii_scan.py`（新文件，~210 行）**：PII 扫描。默认正则覆盖 `phone_cn / email / id_card_cn / bank_card / ipv4`，可配置启用 + 占位符替换。LLM 二次校验 `llm_verify=false` 占位（v1.2.1 接线）。失败不阻塞 prepare。
- **`scripts/src/error_policy.py`（新文件，~95 行）**：4 类错误策略（STOP_AND_NOTIFY / RETRY_WITH_BACKOFF / FALLBACK_BACKEND / DEGRADE）+ `RetryConfig` / `is_retryable_exception` / `apply_policy` / `record_metrics`。
- **`scripts/src/tts.py`**：新增 `build_episode_with_fallback`（带 fallback 的版本），主 backend 失败 → 自动切 fallback_chain（默认 `['edge-tts']`）。原 `build_episode_audio` 走 `build_episode_with_fallback` 内部，向后兼容。
- **`scripts/src/feed.py:register_episode`**：加 `body: str = ""` 参数（v1.2.0 关键字参数，向后兼容），写 `episode_hash` 到 manifest。

### Changed（现有 src/ 改造）

- **`scripts/src/build.py:run()` 续跑逻辑**：从"单 source_hash 比对"升级到"双重 hash 比对（source_hash + episode_hash）"。规则：任一 hash 缺失（legacy）→ 重生成；都未变 → 跳过；任一变了 → 重生成。**这是 v1.1.0 误诊的修正 + v1.1.1 真相的工程化**——卡兹克改稿 / 用户改字 → episode_hash 变 → 重生成。
- **`scripts/src/build.py:run_one()`**：调 `build_episode_with_fallback` 采集 TTS metrics + emit_phase3。
- **`scripts/src/prepare.py:prepare_file()`**：草稿落盘前 `pii_scan.process(body)` + 报告写到 `drafts/<series>/.pii/ep-XX.json`；出口 `emit_phase1` metrics。
- **`scripts/src/stages.py:mark_reviewed()`**：调 `emit_phase2_review` metrics（best-effort，失败不阻塞评审）。

### 文档同步

- **`skills/md-podcast-studio/SKILL.md`**：v1.2.0 description + 治理层新增段（metrics/PII/ErrorPolicy 实际接入说明）。
- **`skills/md-podcast-studio/references/config-spec.md`**：新增 `pii` 字段、`tts.fallback_chain` 字段说明；episode_hash 字段从 v1.1.1 文档化契约升级为 v1.2.0 真实接入。
- **`skills/md-podcast-studio/references/metrics.md`**：从"建议"升级为"已实现"，标注调用点。
- **`skills/md-podcast-studio/references/error-policy.md`**：从"建议"升级为"已实现 tts 层 fallback"，标注 `_resolve_fallback_chain` + `build_episode_with_fallback`。
- **`skills/md-podcast-studio/references/pii-scan.md`**：从"建议"升级为"已实现 prepare 出口"。
- **`README.md`**：加 v1.2.0 关键能力清单 + smoke test 通过记录。
- **`.codebuddy-plugin/plugin.json`**：version 1.1.1 → 1.2.0 / description 同步。
- **5 个 agent MD 文件**：同步 v1.2.0 真实接入（episode_hash / metrics / PII / ErrorPolicy fallback）。

### 兼容性（关键）

- `register_episode(out_dir, meta, slug, duration, size, *, body="")`：`body` 是 keyword-only，默认 `""`，**老调用方式不受影响**
- `build_episode_audio(...)` 返回 `(mp3, duration)`：**接口不变**，内部走 `build_episode_with_fallback`
- `stages.mark_reviewed(target, stage=...)`：**接口不变**，内部追加 metrics 写入（best-effort）
- `prepare_file(...)`：**接口不变**，内部追加 PII 扫描 + metrics

### Smoke Test（已通过）

```
✅ episode_hash 正文: ba3510655cec96bb, 改字后: f0eaccfac17e98fe（变）
✅ should_resynthesize 4 个场景全部正确（legacy/都未变/源改/草稿改）
✅ PII: phone_cn + email 正确识别并脱敏
✅ ErrorPolicy: RetryConfig + is_retryable_exception 正确
✅ metrics: emit_phase1 + read_phase 完整闭环
✅ 全部 9 个模块 import 成功（build / prepare / feed / stages / tts / episode_hash / metrics / pii_scan / error_policy）
```

### Future / Out of Scope（v1.2.1 候选）

- `pii_scan.llm_verify` 真实接线（识别中文姓名等启发式难覆盖）
- `metrics.emit_phase5_summary` 在 build.py:run() 末尾自动调用
- `ErrorPolicy` 文档化的 STOP_AND_NOTIFY / DEGRADE 在 prepare/build 各阶段接入
- unit test 套件（`tests/test_*.py`）

---

## [1.1.1] — 2026-08-20 — R1 数据血缘真相澄清（hotfix）

> **变更驱动**：审阅 `scripts/src/feed.py` 第 181 行 `_hash_source(source_rel)` 后发现 v1.1.0 的 R1 应用有误诊断。
> **变更范围**：纯**文档层修复**（agents/ + skills/*.md + README + plugin.json + CHANGELOG）。**不动 scripts/src/**（确认 source_hash 字段就是源稿指纹，命名正确）。
> **回滚**：`git checkout v1.1.0 -- .` 或 `rsync -a --delete .archive/v1.0.0/ ./`（物理归档仍是 v1.0.0 baseline；如需 v1.1.0 → v1.1.1 直接 `git checkout v1.1.0`）。

### 真相

| 字段 | v1.1.0 错诊断 | v1.1.1 真相 |
|---|---|---|
| `source_hash` | "当前草稿正文指纹，v1.1.0 改名为 episode_hash" | **源稿（`raw/<slug>.md`）的 SHA256 前 16 位**，命名本来就对 |
| 卡兹克改稿后 | "episode_hash 变 → build 重生成 mp3（预期）" | **source_hash 不变**（raw 没改）→ **build 跳过重生成**（续跑命中）。这是正确行为 |
| 想"草稿改后重生成" | "episode_hash 变自动触发" | 用 `--force`（现状行为） |

### Changed

- **撤销 R1 改名**：恢复 `source_hash` 原名，删除"episode_hash"全部文档层引用
- **hard-constraints C6 真相澄清**（v1.1.1 新增）：明示"source_hash 是源稿指纹；卡兹克改稿不触发重生成（除非 raw 改）；想强制重生成用 `--force`"
- **删除 hard-constraints C10**（v1.1.0 误诊的"episode_hash 命名约定"整段）
- **config-spec.md** 删除"episode_hash"字段定义（恢复 v1.0.0 之前的 source_hash 单字段语义）
- **5 个 agent MD** 全部对齐：删除 episode_hash 引用、修正"卡兹克改稿触发重生成"错描述为正确行为
- **README.md / plugin.json / SKILL.md** description 同步删除 episode_hash 表述

### Not Changed

- `skills/md-podcast-studio/scripts/src/**` — 冻结资产（v1.1.1 确认 source_hash 字段就是源稿指纹，命名本来就对，无需改代码）
- v1.1.1 不引入 `episode_hash` 草稿指纹字段；如未来需要"草稿改触发重生成"机制，作为 v1.2.0 候选（需 src/ 改造）

---

## [1.1.0] — 2026-08-20 — 流程管控专家评审应用（**已被 v1.1.1 修订**，R1 改名撤销）

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
- **版本元数据（plugin.json）**：`.codebuddy-plugin/plugin.json` 加 `version: "1.1.0"` 字段；`description` / `displayDescription` 更新以反映 v1.1.0 关键能力（多门禁 + 决策矩阵 + RACI + 真相澄清后的源稿指纹语义）。v1.1.1 同步更新。
- **本 CHANGELOG.md**。
- **`.archive/` 目录 + `.archive/README.md`**：物理冗余备份指南，v1.0.0 baseline 已 snapshot。

### Changed（变更）

- **R1 数据血缘修正（实际为 R1 文档化澄清，非改名）**：实际审阅 `scripts/src/feed.py` 第 181 行 `_hash_source(source_rel)` 后确认：`source_hash` 字段的计算**就是源稿（`raw/<slug>.md`）的 SHA256 前 16 位**——它名副其实就是"源稿指纹"。原 v1.1.0 把它改名为"episode_hash"（声称是"当前草稿正文指纹"）是误诊断；v1.1.1 撤销该改名，恢复 `source_hash` 原名。`hard-constraints.md` C6 增加 v1.1.1 真相澄清：C10 整段删除（不再需要"episode_hash 命名约定"，因为源稿指纹就是源稿指纹）。所有 agent MD 与 plugin.json / README / SKILL.md 同步。**关键修正**：卡兹克改稿**不会**触发 mp3 重生成（因为 source_hash 是源稿指纹，草稿改 ≠ 源稿改）；想"草稿改后强制重生成"请用 `--force`。
- **hard-constraints C6 真相澄清（v1.1.1）**：`source_hash` 是源稿指纹。**卡兹克抛光后草稿正文变了，但 source_hash 不变（因为 raw 没改）→ build 跳过重生成（续跑命中）**。这是 build 的正确行为，不是 bug。要主动重生成请用 `--force` 或 `--only ep-XX --force`。→ **R1**
- **hard-constraints.md 删除 v1.1.0 新增的 C10**：v1.1.0 误诊的"episode_hash 命名约定"不再适用。源稿指纹就是源稿指纹，命名清晰。v1.2.0 候选：若想让"草稿正文变化也触发重生成"，需新增 `episode_hash` 字段（草稿 SHA256）+ build 双重比对。**当前不做**（scripts/src/ 冻结资产）。
- **agents/*.md 同步 v1.1.1**：5 个 agent MD 文件（team-lead / script-editor / script-humanizer / voice-director / publishing-engineer）全部对齐 v1.1.1 R1 真相澄清（恢复 source_hash 原名、删除 episode_hash 引用、修正"卡兹克改稿触发重生成"错描述）。
- **`README.md` v1.1.1 修正**：删除"episode_hash 改名"项，恢复 v1.1.0 之前状态（source_hash 原名，源稿指纹语义）。
- **`.codebuddy-plugin/plugin.json` v1.1.1 修正**：`description` / `displayDescription` 同步更新（删除 episode_hash 改名表述）。

### Not Changed（未改，受范围限制）

- `skills/md-podcast-studio/scripts/src/**` — **冻结资产**（"代码是冻结资产，包装期不修改逻辑"）。v1.1.1 不动代码逻辑；R1 真相澄清纯文档层修复。
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