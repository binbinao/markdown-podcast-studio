# config.yaml 字段规范

> 配位于工程根目录 `config.yaml`。以下为已验证字段（来自当前 myPodcast 仓库）。

## podcast（站点/节目元信息）
- `title`：节目名
- `author`：作者
- `language`：`zh-CN`
- `website`：站点 URL（部署后填，如 `https://binbinao.github.io/myPodcast`）
- `description` / `tagline` / `hero_desc` / `about`：站点文案
- `cover`：`cover.jpg`
- `subscribe.enabled`：`false`（或配置订阅入口）

## voices（edge-tts 后端）
- `host` / `guest` / `default`：如 `zh-CN-XiaoxiaoNeural`
- 选择 `tts.backend: edge-tts` 时生效

## voices_minimax（minimax 后端）
- `host`：`audiobook_male_1`
- `guest`：`male-qn-qingse`
- `default`：`audiobook_male_1`
- 选择 `tts.backend: minimax` 时生效

## voicecaster
- `mode`：`rule` | `llm`（默认 `rule`）
- `default_voice`：`audiobook_male_1`

## tts
- `backend`：`minimax` | `edge-tts`
- `pause_ms`：`600`（段间静音毫秒）
- `minimax`：`base_url`（`https://api.minimaxi.com/v1`）、`api_key`（**留空，走 env**）、`model`（`speech-2.8-hd`）、`speed` `1.0`、`vol` `1.0`、`pitch` `0`

## prosody
- `enable`：`true`
- `mode`：`heuristic` | `llm`

## format
- 默认 `duo`；可在单篇 frontmatter 覆盖为 `solo` / `duo`

## raw_dir / drafts_dir
- `raw` / `drafts`

## split
- `min_episode_chars`：`600`
- `max_episode_chars`：`3000`

## llm（generate/polish/prosody/voicecaster 共用）
- `enable`：`true`
- `base_url`：`https://api.minimaxi.com/v1`
- `api_key`：`""`（留空，走 env：`LLM_API_KEY` → `MINIMAX_API_KEY` → `OPENAI_API_KEY`）
- `model`：`MiniMax-M2.5`（或 M3）
- `max_tokens`：`4000`（务必从 config 读取，勿硬编码，否则集数偏短）
- `temperature`：`0.7`
- `prompt`：系统提示词

---

## 单篇草稿 frontmatter 三件套（决策门跳过信号）
在 `drafts/<slug>/ep-XX.md` 的 frontmatter 写齐以下三项，可跳过三门交互：
- `format`：`solo` | `duo`
- `voice`：音色 id（solo 用）
- `split_strategy`：分集策略名

duo 另需 `host_voice` / `guest_voice` 透传给 build 的 voice_map。

## ai_stage 生命周期（草稿评审门）
- `skeleton` → `generated` → `reviewed` → `frozen`
- `prepare --mark-reviewed` / `--freeze` 改 stage
- build 按 stage 仅设告警级别（reviewed/frozen 静默）；legacy 无字段只告警不阻断
- build **不**改写草稿正文（只读契约）

---

## v1.1.0 新增字段（多门禁评审链）

### `humanize_stage`（v1.1.0 新增，Phase 1.5 卡兹克用）
- `skeleton`（默认，未抛卡兹克）→ `humanized`（卡兹克已改稿）→ `reviewed`（用户已评卡兹克版）→ `frozen`（用户已 freeze）
- 触发时机：Phase 1.5 完成后由 `script-humanizer` 写回
- build 按 stage 仅设告警级别；legacy 无字段只告警不阻断
- **代码层当前未实现**（`scripts/src/stages.py` 未识别），v1.1.0 仅**文档化契约**；实际接线需 src/ 改造

### `audio_reviewed`（v1.1.0 新增，Phase 3 后音频评审门）
- `bool`，默认 `false`
- 触发时机：用户在 Phase 3 完成后试听 mp3 通过，置 `true`
- build 据此决定是否上线到 gh-pages（`false` → 警告但不阻断；建议工作流必须 `true` 才发布）
- **代码层当前未实现**，v1.1.0 仅**文档化契约**

### `source_hash`（v1.1.0 / v1.1.1 字段定义）
- 含义：**源稿**（`raw/<slug>.md`）的 SHA256 前 16 位内容指纹（`feed.py` 第 181 行 `_hash_source(source_rel)`）
- 触发时机：`build.register_episode` 每次 build 重算
- 变更条件：**源稿变更时变**（raw 改了）
- 关键澄清（v1.1.1）：卡兹克改草稿正文**不会**改变 `source_hash`（raw 没动），所以 build 会**跳过重生成**（续跑命中）。想强制重生成用 `--force`。
- v1.1.0 曾误诊为本字段是"草稿正文指纹"并改名 `episode_hash`，v1.1.1 已全部撤销（hard-constraints C10 已删除）

### 评审门关系
```
ai_stage ∈ {reviewed, frozen}        ← Phase 1 草稿评审
humanize_stage ∈ {reviewed, frozen}  ← Phase 1.5 卡兹克版评审（若触发 Phase 1.5）
audio_reviewed: true                 ← Phase 3 音频评审
↑ 3 门独立可过 / 可跳 / 可回退；build 据 final_reviewed（默认 = audio_reviewed）决定是否上线
```

---

## v1.2.0 新增字段（src/ 实际改造）

### `episode_hash`（v1.2.0 真实接入）
- 含义：**草稿正文**（不含 frontmatter）的 SHA256 前 16 位内容指纹（`scripts/src/episode_hash.py:hash_episode_body`）
- 与 `source_hash` 的区别：
 - `source_hash`：源稿 `raw/<slug>.md` 的指纹，raw 改了才变
 - `episode_hash`：草稿正文指纹，草稿正文改了（含卡兹克写回 / 用户改字）就变
- 接入：`feed.register_episode(out_dir, meta, slug, duration, size, body=body_text)` 写 manifest
- **build 续跑**：同时比对两个 hash，任一变了就重生成（`episode_hash.py:should_resynthesize`）

### `tts.fallback_chain`（v1.2.0 真实接入）
- 含义：主 backend 5xx 失败 → 自动切换的备用 backend 列表
- 默认：`['edge-tts']`（主 backend 不是 edge-tts 时兜底；主 backend 是 edge-tts 时 chain 为空）
- 接入：`tts._resolve_fallback_chain(cfg, primary)` + `tts.build_episode_with_fallback(...)`
- 重试：每个 backend 内置 3 次重试 + 指数退避（1s → 2s → 4s）
- **关闭 fallback**：`tts.fallback_chain: []`

### `pii`（v1.2.0 真实接入）
- `enable`：bool，默认 `true`
- `patterns`：list of `phone_cn / email / id_card_cn / bank_card / ipv4`；默认全部启用
- `llm_verify`：bool，默认 `false`（v1.2.1 接线）
- 接入：`prepare.prepare_file()` 草稿落盘前 `pii_scan.process(body, cfg)`
- 报告路径：`drafts/<series>/.pii/ep-XX.json`
- 失败不阻塞 prepare
