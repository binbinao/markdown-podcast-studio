# 10 条硬约束（团队必守，v1.1.0）

> 这些约束来自对当前已验证流水线的代码级核实（file:line）。违反会直接导致合成失败、站点异常或重复返工。**代码是冻结资产，包装期不修改逻辑；运行期也不得绕过。**
>
> v1.1.0 在原 8 条（C1-C8 = C9 错位排序后）基础上**新增 C10（episode_hash 命名约定）**，并**改名文档层 source_hash → episode_hash**（代码层字段名保留作为别名，向后兼容）。

## C1 — 音频拼接用 ffmpeg，不用 pydub
- Python 3.13 已移除 `audioop`，pydub 不可用（代码里根本不 import pydub）。
- 两个后端都用 `ffmpeg -filter_complex concat`。
- **mp4a 标签坑**：minimax 的 mp3 mime 标成 mp4a、实际编码 mp3，和 silence 拼接会 ffmpeg **exit 234**。修法：concat 前 `aformat=sample_fmts=fltp:sample_rates=32000:channel_layouts=mono` + `aresample=32000` 归一化。
- 段间静音：`ffmpeg anullsrc ... libmp3lame`；时长用 `ffprobe`。

## C2 — MiniMax TTS  specifics
- 模型 `speech-2.8-hd`（其它可用：speech-2.8-turbo、2.6/2.0 hd/turbo）。
- `_speak` 内置 **3 次指数退避重试**（`time.sleep(2**attempt)`），端点偶发抖动。
- 密钥：`_resolve_key()` 读 `os.environ["MINIMAX_API_KEY"]` 优先，其次 `cfg.api_key`。env 名精确为 `MINIMAX_API_KEY`。
- 端点 `https://api.minimaxi.com/v1/t2a_v2`，`output_format: hex`，`binascii.unhexlify` 解码。
- 情绪取自 `prosody.plan_sentences` 首句 emotion。

## C3 — LLM 后端（generate / polish / prosody / voicecaster）
- OpenAI 兼容 Chat：`base_url + /chat/completions`。
- `resolve_api_key()` 优先级：`cfg.api_key` → `LLM_API_KEY` → `MINIMAX_API_KEY` → `OPENAI_API_KEY`。
- **MiniMax 必须发** `thinking: {type: "disabled"}` + `reasoning_split: true`。不发 → token 全烧在 reasoning → content 为空。
- 务必从 config 读 `max_tokens`（默认 4000）与 `temperature`（默认 0.7），勿硬编码（曾硬编码导致集数过短）。

## C4 — frontmatter 用 `yaml.safe_dump`
- `generate._wrap` 用 `yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False, width=4096)`，禁止 f-string 拼 YAML。
- 原因：LLM 生成的 chapter/description 可能含双引号（`结语："开始"`），f-string 会破 YAML 边界 → 整集 meta 变空、build 把 output 写到诡异路径。
- 手工修 frontmatter 用中文引号 `""` 替换 `"`。

## C5 — 分集必须剔除水平线 `---`
- `split._strip_md` 用 `re.sub(r"^-{3,}\s*$\n?", "", t, flags=re.M)` 剔除。
- 原因：分集用 `---` 分节，残留 `---` 行无法被 edge-tts 合成（报 "No audio was received"），长系列全卡死。

## C6 — build 对 drafts 只读（**含 v1.1.0 episode_hash 澄清**）
- `run_one` **不得**调 `polish()`（有 AST 测试 `TestBuildReadOnlyContract` 看守：build 一旦 import/call `polish` 即 fail）。
- 草稿是 LLM 产物只读；build 再改会吃掉人工修改、成本翻倍、不可复现。
- 改草稿必须先 `--mark-reviewed` / `--freeze` 再 build。

**v1.1.0 episode_hash 行为**：
- 卡兹克（Phase 1.5）走 in-place 改稿后，**`episode_hash` 实际已变**（它是"当前草稿正文内容指纹"，源稿哈希另有 `source_text_hash`）。
- build 据 `episode_hash` 决定是否重生成 mp3：卡兹克改稿 → `episode_hash` 变 → build 视为新草稿重生成 mp3（**这是预期行为，不是数据血缘断裂**）。
- 想保留老音频：改前先 `git commit` 当前 mp3 + 记 `episode_hash`，改后 `--skip-audio --force` 只重渲站点。
- 详见 **C10（episode_hash 命名约定）**。

## C7 — 退出码契约
- `0` 成功 / `1` 流水线失败（跳过 RSS/站点重建）/ `2` 门禁违规。
- 禁止在 `run_one` / `run` 内 `raise SystemExit`（只允许在 `main()`/argparse）。

## C8 — 决策门跳过规则
- frontmatter 同时含 `format`+`voice`+`split_strategy` → 跳过三门交互，尊重作者预决策。
- 否则 `collect_decisions()` 跑 AI 推荐 + 用户终裁。

## C9 — fish-speech 国内访问 4 坑（hosted Fish Audio API）
- 端点 `POST {base_url}/v1/tts`（默认 `https://api.fish.audio/v1/tts`）；鉴权 `Authorization: Bearer <key>`；**model 经 header 传**（非 body）。
- 适用模型：`s2.1-pro`（付费）/ `s2.1-pro-free`（试用）/ `s2-pro` / `s1`。响应：原始音频 bytes（mp3/wav/pcm/opus）。
- **不支持 zero-shot `references`**：必须先在 Fish Audio 控制台建好 voice model 拿到 `reference_id`，写入 `config.yaml` 的 `voices_fishspeech.host/guest/default`。
- 多说话人 v1 限制：per-segment 单 voice（项目当前未启用 dialog `<|speaker:N|>` 标记）。emotion `(happy)(sad)...` 内联标签与 minimax emotion 字段不对齐，**v1 不做转换**。
- chunk 策略：项目用 `chunk_chars=1000` 一次性 POST（Fish 推荐 `chunk_length` 100-300，**不通过 body 下发**，代码层不依赖），靠 `chunk_chars` 兜底。
- **4 条国内访问坑（已修，不要"自作聪明"绕开）**：
  1. **DNS 污染**：`api.fish.audio` AAAA 被污染成 Facebook IPv6 段，Python 默认 IPv6 撞 Facebook 400 页。修：代码 monkey-patch `urllib3.util.connection.create_connection` 强制 IPv4。
  2. **CF HTTP 版本路由**：Python `requests` 默认 HTTP/1.1 被路由到非 Fish 后端返 400。修：项目用 `httpx.Client(http2=True)`（curl 默认 HTTP/2 所以能通）。
  3. **MITM 代理 SSL**：本地 SOCKS5 做 MITM，Python strict SSL 失败（hostname mismatch）。修：`config.yaml` 的 `tts.fishspeech.verify_ssl: false`（本地），CI 直连留 `true`。
  4. **代理**：`config.yaml` 的 `tts.fishspeech.socks5_proxy: "socks5://127.0.0.1:1086"`（CI 留空直连）。本机调试装 `httpx[socks] PySocks` 到 managed venv。
- **重试策略**：4xx 不重试（鉴权/参数错，治不了）；5xx 重试 3 次 + 指数退避。
- **密钥不落盘**：env `FISH_AUDIO_API_KEY` 优先，zshrc 兜底，绝不写 config/git。

---

## ⚠ 文档/代码不一致（必须如实写，不得谎称自动）
- README/docs 声称 `prepare.run()` 调用 `enforce_raw_files` + `enforce_drafts_dirs`，且 CI 把 `naming_enforce` 当**硬门**。
- **实际代码未接入**：`prepare.py` 已显式移除静默 rename；grep 确认 `naming_enforce` 仅出现在 README、docs、工具本身（`src/naming_enforce.py`）、`src/core.py`（注释）、`src/naming.py`、`tests/`。
- 工具 `naming_enforce.py` + `test_naming_enforce.py` 存在（`--dry-run` 违规返回 2，`--apply` 真改名），但**当前是手动/离线门**，未接 prepare/CI。
- **专家包处理**：不宣称它自动生效；仅作可选手动步骤说明（`python -m src.naming_enforce --dry-run` / `--apply`）。如需自动，作为后续增强单独接线，不要顺手改。

## ⚠ 鱼音 backend 已知限制（v1，未做转换器）
- emotion `(happy)(sad)...` 内联标签与 minimax emotion 字段不对齐，**v1 不做转换**（pass-through 透传，鱼音会忽略）。
- 多说话人 dialog `<|speaker:N|>` 标记 v1 不启用。
- 无 self-host 路径（方案 B 待实现）。

---

## C10 — episode_hash 命名约定（**v1.1.0 新增**）

> **目的**：避免"R1 数据血缘断裂"的误解——卡兹克写回草稿后音频也变其实是**预期**。

### 三个 hash 字段的语义边界

| 字段 | 语义 | 谁写 | 何时变 |
|---|---|---|---|
| **`source_text_hash`** | 源稿（`raw/<slug>.md`）内容指纹 | `prepare.ingest` 一次性写入 | 永不（源稿不动） |
| **`episode_hash`**（v1.1.0 改名） | **当前**草稿正文内容指纹 | `build.register_episode` 每次 build 重算 | 草稿正文变更时变（卡兹克写回会触发）|
| `source_hash`（代码层别名）| 同 `episode_hash` | 同上 | 同上 |

### 改名原因（v1.1.0）
- 旧名 `source_hash` 容易被误读为"源稿哈希"（实际是"当前草稿哈希"）
- 改名后语义清晰：源稿有 `source_text_hash`；当前稿有 `episode_hash`；二者**不混淆**

### 兼容性（关键）
- **代码层字段名仍为 `source_hash`**（`scripts/src/build.py` 的 `register_episode` 函数签名不变）
- **文档层统一用 `episode_hash`**，并在第一次出现时写"代码层仍叫 source_hash"
- 用户 / 上层工具读 YAML 时，两个名字都接受

### 决策矩阵

| 场景 | 行为 | 是否重生成 mp3 |
|---|---|---|
| 只改 `raw/<slug>.md` 源稿 | `source_text_hash` 变；`episode_hash` 也变（草稿重生成）| **是** |
| 只跑 Phase 1.5 卡兹克写回 | `episode_hash` 变（正文改了）；`source_text_hash` 不变 | **是**（预期）|
| 用户评审改了几个字 | `episode_hash` 变 | **是**（小成本）|
| 只想改 frontmatter（不动正文）| `episode_hash` 不变（YAML 不计入正文指纹）| 否 |
| 只想重渲站点不动音频 | `python -m src.build drafts/ --skip-audio --force` | 否（skip-audio）|

### 排错
- 改稿后音频"无故"重生成 → 这是预期（C10）
- 想保留老音频 → 改前先 `git commit` 当前 mp3 + 记 `episode_hash`，改后 `--skip-audio --force` 只重渲站点
- 想知道当前 `episode_hash` → 读 `output/manifest.json` 或 `series/<slug>/ep-XX/manifest.json`（代码层字段为 `source_hash`）
