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
