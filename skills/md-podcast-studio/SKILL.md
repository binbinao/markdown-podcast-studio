---
# === SOP 元数据（流程治理） ===
name: md-podcast-studio
version: 1.2.1
owner: script-editor                       # SOP 修改权限归属（PR 评审需 owner + 主理人 + 用户）
effective_from: 2026-08-20
changelog_ref: ../../../CHANGELOG.md      # 变更日志相对路径
supersedes: v1.2.0
description: "Self-contained Markdown-to-Podcast pipeline: scaffold a fresh project, split articles into scripts, REQUIRED humanize via Khazix (Phase 1.5, hard-gate C11), direct AI voice (MiniMax / edge-tts / fish-speech), build RSS + dark site, deploy to GitHub Pages. v1.2.1 makes Khazix mandatory, wires pii_scan.llm_verify (Chinese name detection), emits phase5_summary automatically, standardizes ErrorPolicy STOP_NOTIFY/DEGRADE, and adds unit test suite (57 tests)."
---

# Markdown Podcast Studio — Skill (v1.2.1)

把 Markdown 文章变成可上线播客的完整、可移植流水线。本 skill 自带**已验证可用**的流水线代码与工程模板，能在任意新仓库 scaffold 出一套 Markdown→播客工程。

> **v1.2.1 变更驱动**：v1.2.0 已实现 episode_hash / metrics / PII / ErrorPolicy fallback；v1.2.1 **将卡兹克从可选升级为必做强阻断**（hard-constraint C11），并补齐 v1.2.1 候选清单（llm_verify / phase5_summary / ErrorPolicy 标准化 / unit test）。详见 `CHANGELOG.md`。回滚方式见文末。

---

## 何时使用
- 用户想把一篇 Markdown / 长文 / 白皮书变成播客（单人或双人）。
- 需要从零搭建一套文字转语音播客工程（脚手架）。
- 需要排查 prepare / TTS / build / 部署 各环节的问题。
- 用户原话提到"更自然 / 更生动 / 像人念的 / 活人感 / 卡兹克" → 触发 **Phase 1.5**（见决策矩阵）。

## 目录布局（本 skill 内）
- `scripts/src/` — 流水线代码（= 已验证的 myPodcast `src/`，**原样打包，不修改逻辑；冻结资产**）
- `templates/` — 可移植工程模板：`config.yaml`、`pyproject.toml`、`requirements.txt`/`requirements.lock`、`site/`（Jinja2 暗色站点）、`github/workflows/publish.yml`（gh-pages 部署）
- `bin/scaffold` — 在新目录实例化整套工程
- `references/`
  - `command-reference.md` — 精确 CLI 调用（prepare / build / 全序列）
  - `config-spec.md` — `config.yaml` 字段规范（含 v1.1.0 新增 `humanize_stage` / `audio_reviewed`；v1.1.1 撤销 v1.1.0 误诊的 `episode_hash` 字段定义）
  - `hard-constraints.md` — **v1.1.1 删除 v1.1.0 误诊的 C10**，回到 9 条硬约束（团队必守）
  - `troubleshooting.md` — 已知坑与排错
  - `error-policy.md` — **v1.1.0 新增**：4 类错误策略与每阶段应用示例
  - `metrics.md` — **v1.1.0 新增**：每阶段采集指标建议（文档化，实际采集需 src/ 改造）
  - `pii-scan.md` — **v1.1.0 新增**：草稿出口 PII 扫描建议

## 快速开始
```bash
# 1. 在新目录实例化工程（复制代码 + 模板）
bin/scaffold /path/to/my-podcast
cd /path/to/my-podcast

# 2. 安装依赖（Python >=3.13；系统需 ffmpeg/ffprobe，pip 装不了）
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock

# 3. 放文章 → 准备草稿 → 人工评审 → 合成与发布
cp article.md raw/$(date +%Y-%m-%d)-article.md
export MINIMAX_API_KEY=...          # minimax 后端需要；edge-tts 免密；fish-speech 用 FISH_AUDIO_API_KEY
python -m src.prepare --yes
python -m src.prepare --mark-reviewed drafts/<date-slug>
python -m src.build drafts/
git add output drafts && git commit -m "new episodes" && git push  # 部署 gh-pages
```

### 三 TTS 后端速选（详细见决策矩阵 §D4）
| 后端 | 密钥 | 何时用 |
|---|---|---|
| `edge-tts` | 无 | 烟雾测试 / CI 默认（`TTS_BACKEND=edge-tts`） |
| `minimax` | `MINIMAX_API_KEY` | 主用：单人 / 反思独白 / 商务节目（8 种情绪 + 22 拟声词） |
| `fish-speech` | `FISH_AUDIO_API_KEY` | Fish Audio OpenAudio S2，hosted API；国内访问有 4 坑（见 hard-constraints C9） |

切换**只改 `config.yaml` 的 `tts.backend`**，不改业务代码。

---

## 主流程图（Happy Path）

```mermaid
flowchart LR
    U([用户: Markdown 文章]) --> P0[Phase 0<br/>脚手架检测]
    P0 --> P1[Phase 1<br/>script-editor<br/>plan_episodes + 草稿生成]
    P1 --> P2[Phase 2<br/>用户评审<br/>mark-reviewed / freeze]
    P2 --> P3[Phase 3<br/>voice-director<br/>TTS 后端 + ffmpeg 拼接]
    P3 --> P4[Phase 4<br/>publishing-engineer<br/>质量门禁 + RSS + 站点]
    P4 --> P5[Phase 5<br/>主理人汇总汇报]
    P5 --> Live([节目上线])
    
    P1 -.触发条件见决策矩阵 §D3.-> P15[Phase 1.5<br/>script-humanizer<br/>卡兹克活人感抛光]
    P15 -.用户评审.-> P2
```

## 异常流图（ErrorPolicy 路由）

```mermaid
flowchart TD
    Err[阶段失败] --> Det{ErrorPolicy 判定}
    Det -->|STOP_AND_NOTIFY| S1[抛错 + 主理人升级]
    Det -->|RETRY_WITH_BACKOFF| S2[指数退避 N 次]
    Det -->|FALLBACK_BACKEND| S3[切备用后端]
    Det -->|DEGRADE| S4[跳过该阶段继续]
    
    S2 -->|仍失败| Det
    S3 -->|仍失败| S2
    S4 --> Note[⚠ output/metrics/&lt;date&gt;.json<br/>记录 DEGRADE 原因]
    
    Note --> P5
```

> 每阶段 ErrorPolicy 详见 `references/error-policy.md`。

---

## 角色分工（与专家团对应）

| 阶段 | 主理人 (A) | 成员 (R) | 用户 (C) | 系统 (I) | 核心动作 |
|---|---|---|---|---|---|
| **Phase 0** 脚手架 | A | R: 自动化脚本 | — | — | `detect_scaffold()`；缺则 `bin/scaffold` |
| **Phase 1** 脚本 | A | R: script-editor | C: 用户（确认选题） | — | 决策门、分集、生成草稿、`ai_stage` 生命周期 |
| **Phase 1.5** 卡兹克（可选）| A | R: script-humanizer | C: 用户（是否触发） | — | in-place 改稿、`humanize_stage` 推进、不动 frontmatter |
| **Phase 2** 评审门 | A | — | **R: 用户** | I: 系统（超时告警） | `ai_stage ∈ {reviewed, frozen}` + `humanize_stage ∈ {reviewed, frozen}` + `audio_reviewed: true` 三门独立 |
| **Phase 3** 配音 | A | R: voice-director | C: 用户（选声） | — | TTS、prosody、ffmpeg 拼接 |
| **Phase 4** 构建发布 | A | R: publishing-engineer | C: 用户（站点名） | I: GitHub Actions | 质量门禁、RSS、暗色站点、`--skip-audio`、gh-pages |
| **Phase 5** 汇报 | **A+R** | — | C: 用户 | I: 全流程 metrics | 集数 / 时长 / 后端 / URL / git status |

> **铁律**：成员产出由对应成员输出后再采信；主理人在 Phase 5 可汇编但不代写成员结论。

---

## 决策矩阵（DecisionMatrix）

> 每个决策点：触发条件 + 推荐 + 兜底。避免"用户原话驱动"的主观性。

### D1 — Phase 0 脚手架检测
- **触发**：用户说"搭工程" / "从零" / "scaffold"
- **检测**：`detect_scaffold()` 检查工程根目录是否含 `src/`、`config.yaml`、`raw/`、`drafts/`、`output/`
- **推荐**：
 - 5 项齐全 → 跳过 Phase 0，直接 Phase 1
 - 缺任意 1 项 → `bin/scaffold` 初始化
- **兜底**：scaffold 失败 → 主理人升级（ErrorPolicy: `STOP_AND_NOTIFY`）

### D2 — Phase 1 plan_episodes fallback
- **触发**：`python -m src.prepare` 调 `plan_episodes(strategy=...)`
- **正常**：`plan_episodes` 返回真实集数（含「短引言合并进第 1 集」）
- **fallback**：`plan_episodes` 失败 / 不可用 → 按 `split.min_episode_chars=600` / `max_episode_chars=3000` 字数估算集数
- **兜底**：估算后再做一次决策门交互让用户确认（ErrorPolicy: `DEGRADE` + 用户咨询）

### D3 — Phase 1.5 卡兹克触发
- **触发条件**（任一满足）：
 1. 用户原话提到"更自然 / 更生动 / 像人念的 / 活人感 / 去 AI 味 / 卡兹克"
 2. `cost_tier ≥ medium`（脚本编辑判断：内容重要程度）
 3. 草稿 `length > 5000 字`
 4. `format == solo`（独白稿天然适合卡兹克）
- **不触发**：纯流水线跑通 / 单期一次性脚本 / 低稿费内容 / 用户已在脚本编辑阶段自带改稿
- **兜底**：卡兹克改稿后 `humanize_stage` 未到 `reviewed` → 不进 Phase 3（ErrorPolicy: `STOP_AND_NOTIFY`）

### D4 — Phase 3 TTS 后端选择
- **默认走 `config.yaml`** 的 `tts.backend`
- **决策树**（用户没说时主理人按此推荐）：
 - 烟雾测试 / CI → `edge-tts`（免密，最稳）
 - 单人 / 反思独白 / 商务节目 → `minimax`（8 情绪 + 22 拟声词）
 - 双人对谈 / 多情感切换 → `minimax`（更稳定）或 `fish-speech`（音色丰富但有 4 坑）
 - 国内 CI 网络受限 → `edge-tts` 优先（minimax/fish 都走外网）
- **兜底**：主后端 5xx 连续 3 次 → 自动切 `edge-tts`（ErrorPolicy: `FALLBACK_BACKEND`）

### D5 — Phase 4 部署路径
- **正常**：`push output/` 触发 `.github/workflows/publish.yml` → gh-pages
- **离线**：`python -m src.build drafts/ --skip-audio` 复用 git-LFS mp3 重渲 RSS/站点
- **本地**：开发机直接预览 `output/index.html`（无需部署）
- **兜底**：gh-pages 部署失败 → 主理人升级（ErrorPolicy: `STOP_AND_NOTIFY`）

---

## RACI 矩阵（治理与代写边界）

> **R** = Responsible（执行）/**A** = Accountable（最终负责）/ **C** = Consulted（咨询）/**I** = Informed（知会）
>
> **铁律**：每个产出有且只有一个 A；成员产出不可由主理人代写。

| 产出 | 主理人 | 脚本编辑 | 卡兹克 | 配音导演 | 发布工程师 | 用户 | 系统 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 草稿正文 (`drafts/<slug>/ep-XX.md`) | A | **R** | R（Phase 1.5 写回）| — | — | C | — |
| `ai_stage` 推进 | A | **R** | — | — | — | C（评审）| I |
| `humanize_stage` 推进（v1.1.0 新增）| A | — | **R** | — | — | C（评审）| I |
| `audio_reviewed` 推进（v1.1.0 新增）| A | — | — | R（音频评审）| — | C（终裁）| I |
| `episode.mp3`（音频）| A | — | — | **R** | — | C（终裁）| — |
| `output/feed.xml`（RSS）| A | — | — | — | **R** | — | — |
| `output/index.html`（站点）| A | — | — | — | **R** | — | — |
| `output/metrics/<date>.json`（v1.1.0 新增）| **A+R** | — | — | — | — | — | I |
| Phase 5 汇报（最终）| **A+R** | — | — | — | — | C | — |

> **违规检测**：若主理人在 Phase 5 写出"配音导演选了哪个音色"——这是代写，必须由 voice-director 自己回传再采信。

---

## 并行评审配置（v1.1.0 新增，G4）

```yaml
# config.yaml
workflow:
  parallel_review: false   # 默认 false（串行：Phase 1 → Phase 1.5 → Phase 2 评审 → Phase 3 → Phase 4）
                          # true 时：Phase 1.5 与 Phase 2 评审门可并行
                          #   - 用户先评 Phase 1 草稿（ai_stage）
                          #   - 卡兹克并行跑 Phase 1.5 抛光
                          #   - 用户再评卡兹克版（humanize_stage）
                          # 适用：高稿费长稿、双人节奏并行优化
```

> 启用前需确认：用户能并行处理两版（编辑原文 + 卡兹克版），否则节奏反而更乱。

---

## 度量反馈环（v1.1.0 新增，Y4）

每阶段采集的指标建议写到 `output/metrics/<date>.json`，下个迭代可被 SOP 引用（**反馈环入口**）。

| 阶段 | 指标 | 写入 |
|---|---|---|
| Phase 1 | 决策门通过率 / 草稿生成耗时 / LLM token 消耗 | `output/metrics/<date>/phase1.json` |
| Phase 1.5 | 改稿轮次 / 字数漂移率 / 复核脚本失败次数 | `output/metrics/<date>/phase1.5.json` |
| Phase 3 | 后端成功率 / 平均合成耗时 / 音频总时长 | `output/metrics/<date>/phase3.json` |
| Phase 4 | `validate_script` BLOCK 率 / 续跑命中率 / 部署成功率 | `output/metrics/<date>/phase4.json` |
| Phase 5 | **端到端 cycle time**（用户输入到上线的小时数）| `output/metrics/<date>/phase5.json` |

> 当前为**文档化建议**。实际采集需 `scripts/src/` 改造，不在 v1.1.0 范围（冻结资产）。

---

## 回滚（v1.1.0 → v1.0.0）

```bash
# 方式 A：从 git tag 回滚（推荐，绝大多数情况）
cd /Users/jiduobin/.workbuddy/plugins/marketplaces/my-experts/plugins/markdown-podcast-studio
git checkout v1.0.0 -- .

# 方式 B：从物理归档回滚（git 损坏 / tag 误删时）
cd /Users/jiduobin/.workbuddy/plugins/marketplaces/my-experts/plugins/markdown-podcast-studio
```

> **v1.1.1 → v1.1.0**：把 v1.1.1 误诊的 episode_hash 改名回滚，回 source_hash 真相。`git checkout v1.1.0 -- .`。
> **v1.2.0 → v1.1.1**：把 src/ 实际改造回滚，文档层回归"建议"状态。`git checkout v1.1.1 -- .`。

---

## v1.2.0 治理层新增（src/ 实际改造）

### 候选 1：真 episode_hash（草稿指纹）— `scripts/src/episode_hash.py`
- **目的**：v1.1.1 真相（source_hash 是源稿指纹）+ 卡兹克改稿场景需要"草稿正文指纹"双重比对
- **实现**：`hash_episode_body(body)` 算 SHA256 前 16 位（不含 frontmatter）
- **接入**：`feed.register_episode(..., body=body_text)` 写 manifest；`build.run()` 续跑同时比对 source_hash + episode_hash
- **续跑规则**（`should_resynthesize`）：
 - 任一 hash 缺失（legacy / 首次 build）→ 重生成
 - source_hash 变 → 重生成（raw 改了）
 - episode_hash 变 → 重生成（草稿正文改了，含卡兹克写回 / 用户改字）
 - 都未变 → 跳过

### 候选 2：metrics 实际采集 — `scripts/src/metrics.py`
- **目的**：v1.1.0 文档化的反馈环入口
- **写入路径**：`output/metrics/<date>/phase*.json`（原子写）
- **接入点**：
 - `prepare_file()` 出口 → `emit_phase1(...)`
 - `stages.mark_reviewed()` 出口 → `emit_phase2_review(...)`（best-effort）
 - `build.run_one()` 出口 → `emit_phase3(...)`（含 ErrorPolicy metrics）
- **Timer** 上下文管理器：`with Timer() as t: ... t.duration_sec` 自动记

### 候选 3：PII 扫描接入 — `scripts/src/pii_scan.py`
- **目的**：草稿出口脱敏私人信息（电话 / 邮箱 / 身份证 / 银行卡 / IP）
- **接入点**：`prepare_file()` 草稿落盘前 `pii_scan.process(body, cfg)`
- **报告**：`drafts/<series>/.pii/ep-XX.json`（hidden，build glob 不匹配）
- **配置**（`config.yaml`）：
  ```yaml
  pii:
    enable: true
    patterns: [phone_cn, email, id_card_cn]   # 选启用哪些
    llm_verify: false                          # 关闭（v1.2.1 接线）
  ```
- **失败不阻塞**：扫描失败仅 warn，不阻塞 prepare。

### 候选 4：ErrorPolicy 自动 fallback — `scripts/src/error_policy.py` + `tts.py`
- **目的**：主 backend 5xx 连续失败 → 自动切 fallback（默认 edge-tts）
- **接入点**：`build.run_one()` 调 `tts.build_episode_with_fallback(...)`（替代原 `build_episode_audio`）
- **Fallback chain**：默认 `['edge-tts']`（主 backend 不是 edge-tts 时兜底）；用户可在 `config.yaml` 覆盖 `tts.fallback_chain`
- **重试策略**：每个 backend 内置 3 次重试 + 指数退避（1s → 2s → 4s）
- **Metrics**：`build_episode_with_fallback` 返回 `(mp3, duration, metrics)`，含 `attempted_backends / success_backend / retries_total / degraded`

### 兼容性总结

- `register_episode(..., body="")`：`body` 是 keyword-only，默认 `""`，老调用方式不受影响
- `build_episode_audio(...)` 返回 `(mp3, duration)`：**接口不变**，内部走 fallback 版
- `stages.mark_reviewed(...)`：接口不变，metrics 写入 best-effort
- `prepare_file(...)`：接口不变，内部加 PII 扫描 + metrics

### Smoke Test（v1.2.0 已通过）

详见 `CHANGELOG.md [1.2.0]` 段。已验证：episode_hash 业务逻辑 / should_resynthesize 4 场景 / PII 脱敏 / RetryConfig + is_retryable / metrics emit + read / 全部 9 模块 import + 函数签名。

### Future / Out of Scope（v1.2.1 候选）

- `pii_scan.llm_verify` 真实接线（识别中文姓名等启发式难覆盖）
- `metrics.emit_phase5_summary` 在 build.py:run() 末尾自动调用
- `ErrorPolicy` 文档化的 STOP_AND_NOTIFY / DEGRADE 在 prepare/build 各阶段接入
- unit test 套件（`tests/test_*.py`）
rsync -a --delete .archive/v1.0.0/ ./
```

> 详细命令、配置、约束与排错见 `references/`。**代码是冻结资产**：本 skill 只复制、不修改流水线逻辑；仓库后续演进需重新打包。
---

## v1.2.1 治理层新增（卡兹克必做 + 4 候选落地）

### 卡兹克从可选 → 必做强阻断（hard-constraint C11）
- **触发条件**：v1.2.0 卡兹克仅在用户原话触发时跑；v1.2.1 起**默认必做**，build 入口强检查 `humanize_stage ∈ {reviewed, frozen}`
- **门禁调用点**：`build.py:run_one()` Phase 3 入口 → `error_policy.stop_and_notify("phase1.5", ...)` 标准化抛 PipelineError
- **豁免**：`--skip-humanize` flag（CI / 烟雾测试 / 用户显式跳过）
- **生命周期**（`stages.py`）：
 - `skeleton` → prepare 草稿落盘时由 `init_humanize_stage(f)` 初始化
 - `humanized` → 卡兹克改稿完成
 - `reviewed` → 用户评完卡兹克版（`python -m src.stages mark-humanize-reviewed <path>`）
 - `frozen` → 用户 freeze（不再重生成）
- **ErrorPolicy**：卡兹克 LLM 失败 → RETRY(3) → 失败 STOP_NOTIFY（**不**静默降级到原文）

### pii_scan.llm_verify 接线（中文姓名识别）
- **触发条件**：`cfg.pii.llm_verify: true`（默认关闭）
- **设计**：启发式找"上下文疑似姓名"（CEO X / X 先生 / 老师 X 等）→ 调 LLM 二次校验 → 确认的姓名脱敏为 `[已脱敏姓名]`
- **复用**：`polish.llm_complete()`（已有 LLM helper）
- **失败 fallback**：LLM 调用失败 → 正则-only（不阻塞 prepare/build）
- **Trade-off**：边界严格（lookbehind 排除"汉字+姓名"），宁可漏几个，不要误杀

### metrics.emit_phase5_summary 自动调用
- **触发条件**：`build.py:run()` 末尾无条件 emit
- **采集**：cycle_time_hours（占位 0.0，全 cycle 估算作为 v1.2.2）/ user_review_time_hours / first_attempt_success / phases_succeeded / phases_degraded
- **写入**：`output/metrics/<date>/phase5.json`
- **智能判断 phases_degraded**：`--skip-humanize` 时 phase1.5 列入 degraded，否则 phases_succeeded 含 1.5 + 2

### ErrorPolicy STOP_NOTIFY/DEGRADE 标准化
- **`stop_and_notify(stage, message, hint=None)`**：log error + raise PipelineError。统一入口，便于未来 metrics 接入 + 告警系统。
- **`degrade(stage, message, reason)`**：log warning，不抛错，主流程继续。
- **接入**：build.py 卡兹克门禁失败用 `stop_and_notify("phase1.5", ...)`；其他 raise PipelineError 保留原样（向后兼容）

### Unit Test 套件（v1.2.1 新增）
- **位置**：`tests/test_*.py`
- **覆盖**：episode_hash（9 测试）/ metrics（11）/ pii_scan（11）/ error_policy（13）/ stages（13）
- **运行**：`cd skills/md-podcast-studio/tests && pytest`
- **结果**：**57 passed** ✅
- **conftest.py**：自动加 `scripts/` 到 sys.path，让 pytest 能 import src/
- **不覆盖**：build.py / prepare.py / tts.py（需要外部依赖，集成测试建议）

### 兼容性总结（v1.2.1 不破坏的）

- `build_episode_audio(...)`：返回 `(mp3, duration)`，**接口不变**
- `register_episode(..., body="")`：`body` 是 keyword-only 默认空
- `stages.mark_reviewed(...)`：接口不变
- `prepare_file(...)`：接口不变（内部加 `init_humanize_stage`）

### Smoke Test（v1.2.1 已通过）

详见 `CHANGELOG.md [1.2.1]` 段。

- **57 单测全过**（tests/ 套件）
- **9 模块 import 成功**（build / prepare / feed / stages / tts / episode_hash / metrics / pii_scan / error_policy）
- **卡兹克门禁场景**：草稿 humanize_stage=skeleton → build 抛 PipelineError ✓；--skip-humanize 豁免 ✓
- **PII 姓名启发式**：CEO 张三先生 → "张三" ✓；王女士 + 张先生 → 略过（lookbehind 严格）
- **ErrorPolicy stop_and_notify**：raise PipelineError 含 stage/hint ✓
