# 12 条硬约束（团队必守，v1.3.0）

> 这些约束来自对当前已验证流水线的代码级核实（file:line）。违反会直接导致合成失败、站点异常或重复返工。**运行期不得绕过。**
>
> - v1.2.1 新增 C11 — 卡兹克活人感抛光必做强阻断（build 前必须 humanize_stage ∈ {reviewed, frozen}）。
> - **v1.2.2 新增 C12 — `--force` 是一次性诊断，跑完必须还原**（2026-09-21 真实上线事故沉淀）；
>   同时按一次真实上线修正 C3 的 `max_tokens` 指引（思考型模型需 12000）。
> - **v1.3.0 模块改名** — `polish.py` → **`llm.py`**（C3/C6 的模块名同步更新）。包内 `src/` 已按脚手架定位重打包，
>   **不再是"冻结资产"**：它是 scaffold 会原样复制进新工程的"当前最佳实践版本"。

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

## C3 — LLM 后端（generate / llm / prosody / voicecaster）
- OpenAI 兼容 Chat：`base_url + /chat/completions`。
- `resolve_api_key()` 优先级：`cfg.api_key` → `LLM_API_KEY` → `MINIMAX_API_KEY` → `OPENAI_API_KEY`。
- **MiniMax 必须发** `thinking: {type: "disabled"}` + `reasoning_split: true`。不发 → token 全烧在 reasoning → content 为空。
- 务必从 config 读 `max_tokens` 与 `temperature`（默认 0.7），勿硬编码（曾硬编码导致集数过短）。
- ⚠️ **换用「思考型模型」时 `max_tokens` 必须重估，不能沿用 4000**：reasoning 与正文**共享** `max_tokens` 预算
  （reasoning 走独立字段 `reasoning_content`，不污染正文，但**要占预算**）。实测 1600 字输入 → reasoning 1044 + 正文 458 tokens，
  4000 会截断，**12000 才稳**（SCNet `DeepSeek-V4.1-Flash` 的实测配置）。
  典型症状：`finish_reason` 正常但 **content 为空** —— 就是预算被 reasoning 吃光了。
- ⚠️ **`thinking:{type:"disabled"}` 不是所有端点都认**：MiniMax 认，**SCNet 忽略**（reasoning 照产）。
  所以「关思考」这条不能当作省 token 的通用手段。
- ⚠️ `resolve_api_key()` 还应支持 `cfg.api_key_env`：**显式声明时只认该 env，不回落默认列表**——
  防止 shell 里躺着别的 provider 的 key 被取错还难查。

## C4 — frontmatter 用 `yaml.safe_dump`
- `generate._wrap` 用 `yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False, width=4096)`，禁止 f-string 拼 YAML。
- 原因：LLM 生成的 chapter/description 可能含双引号（`结语："开始"`），f-string 会破 YAML 边界 → 整集 meta 变空、build 把 output 写到诡异路径。
- 手工修 frontmatter 用中文引号 `""` 替换 `"`。

## C5 — 分集必须剔除水平线 `---`
- `split._strip_md` 用 `re.sub(r"^-{3,}\s*$\n?", "", t, flags=re.M)` 剔除。
- 原因：分集用 `---` 分节，残留 `---` 行无法被 edge-tts 合成（报 "No audio was received"），长系列全卡死。

## C6 — build 对 drafts 只读（**v1.1.1 source_hash 真相澄清**）
- `run_one` **不得**调 `llm()`（有 AST 测试 `TestBuildReadOnlyContract` 看守：build 一旦 import/call `llm` 或 `polish` 即 fail）。
  ⚠️ **改名陷阱**：v1.3.0 把 `polish.py` 改名为 `llm.py`。守护测试若只断言 `polish`，改名后**必然静默通过**
  （已无人引用它）→ 测试必须**同时覆盖两个名字 + AST 级 Call 节点**，见 `tests/test_scaffold_contract.py`。
- 草稿是 LLM 产物只读；build 再改会吃掉人工修改、成本翻倍、不可复现。
- 改草稿必须先 `--mark-reviewed` / `--freeze` 再 build。

**v1.1.1 source_hash 真相澄清**（v1.1.0 误诊修正）：
- `source_hash` 字段计算的是 `raw/<slug>.md` 源稿的 SHA256 前 16 位（`feed.py` 第 181 行 `_hash_source(source_rel)`）。它**就是源稿指纹**，命名本来就对。
- **卡兹克（Phase 1.5）走 in-place 改稿后，`source_hash` 不变**（因为 raw 源稿没改，只是草稿正文改了）。
- build 据 `source_hash` 决定是否重生成 mp3：源稿 hash 没变 → **跳过重生成**（续跑命中）。这是正确行为，**不是 bug**。
- 想"草稿改后强制重生成" → 用 `--force` 或 `--only ep-XX --force`（现状行为）。
- 想保留老音频 → 改前先 `git commit` 当前 mp3，改后 `--skip-audio --force` 只重渲站点。
- **v1.1.0 误诊已撤销**：v1.1.0 把 `source_hash` 改名为 `episode_hash`（声称"当前草稿正文指纹"），并新增 C10 命名约定。审阅代码后确认这是误诊断，v1.1.1 已全部撤销（C10 删除，所有"episode_hash"文档层引用清除）。

## C7 — 退出码契约
- `0` 成功 / `1` 流水线失败（跳过 RSS/站点重建）/ `2` 门禁违规。
- 禁止在 `run_one` / `run` 内 `raise SystemExit`（只允许在 `main()`/argparse）。


## C8 — 决策门跳过规则
- frontmatter 同时含 `format`+`voice`+`split_strategy` → 跳过三门交互，尊重作者预决策。
- 否则 `collect_decisions()` 跑 AI 推荐 + 用户终裁。
- ⚠️ **走快捷分支时，duo 必须同时拿到 `host_voice`/`guest_voice`**（2026-09-21 修）：该分支原先只透传三件套，
  duo 的 `host_voice`/`guest_voice` 会**静默丢空**。修法：`_duo_voices_from_meta()` 在读显式 key 之余，
  再解析 `voice: "host=X / guest=Y"` 标签（这个格式 `decisions.py` 一直在**写**、却从没人**读**）。
  - **为什么危险**：丢了**不报错**——build 会回退到 `voices.*` 的默认 host/guest，产出音频"听起来正常"但**不是你要的音色**。
  - **验收动作**：过快捷分支后，核 draft 与 `_decisions.json` 里的 `host_voice`/`guest_voice` 是否为你指定的值。

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

<!-- v1.1.1: 删除 v1.1.0 误诊的 C10（episode_hash 命名约定）。source_hash 本来就是源稿指纹，命名本来就对。 -->

## C11 — 卡兹克活人感抛光必做强阻断（v1.2.1 新增）
- **build 前必须** `humanize_stage ∈ {reviewed, frozen}`；否则 PipelineError 抛错（exit 1）。
- **门禁调用点**：`scripts/src/build.py:run_one()`（Phase 3 入口）；通过 `scripts/src/error_policy.py:stop_and_notify("phase1.5", ...)` 标准化抛错。
- **豁免**：`build --skip-humanize` flag（仅 CI / 烟雾测试 / 用户显式跳过用）。
- **生命周期**（`scripts/src/stages.py`）：
 - `skeleton` → prepare 草稿落盘时由 `init_humanize_stage` 初始化（v1.2.1 新增）
 - `humanized` → 卡兹克改稿完成（由 script-humanizer 写回）
 - `reviewed` → 用户评完卡兹克版（`python -m src.stages mark-humanize-reviewed <path>`）
 - `frozen` → 用户 freeze（不再重生成）
- **接入**：`prepare.py:prepare_file()` 草稿落盘前调 `init_humanize_stage(f)`；build 入口强检查。
- **ErrorPolicy**：卡兹克 LLM 失败 → RETRY(3) → 失败 STOP_AND_NOTIFY（不静默降级到原文）。
- **不被 C11 阻断的场景**：`--skip-humanize` flag + 用户已显式声明豁免。

## C12 — `--force` 是一次性诊断，跑完必须还原（v1.2.2 新增）

> 来源：2026-09-21 一次真实上线。按旧规程「commit 前必跑 `--skip-audio --force`」执行，结果
> 在 82 集仓库上凭空产生 ~82 处脏改动 + RSS 顺序错乱，新集从第 1 位掉到第 27 位。

**为什么会这样**：`--force` 绕过续跑判断，让**全部**集数重新走 `register_episode()`，而它结尾是 `eps.insert(0, entry)`。

| 副作用 | 机制 |
|---|---|
| 所有 `shownotes.md` 的 `date` 刷成当天 | `feed.py` 取 `meta.get("date", today)`；draft 无 `date:` 时取渲染当天 |
| manifest / RSS 顺序被打乱 | 全量重注册 = 按 drafts 扫描序倒序重排；`build_feed()` **不排序**，数组顺序即发布顺序 |

**两条硬规则**：
1. `--skip-audio --force` **仍要跑**（它是验证渲染路径、确认「失败 0」的唯一手段），
   但**它产出的 output 不是可提交的终态**。
2. 跑完**必须还原**（`git checkout HEAD -- output/{manifest.json,feed.xml,index.html}` +
   `git checkout -- output/series/`），再用**不带 `--force`** 的单目录构建重注册新集。

**还原成功的判据**：`git diff HEAD -- output/manifest.json` = **「纯新增、0 删除」**，
且 manifest 第 1 条 `_key` / `feed.xml` 第 1 个 `<item>` = 新集。

> 完整命令见 `references/troubleshooting.md` §7。

## ⚠ 发布验收铁律（与 C12 配套）

- **顺序语义**：`register_episode()` 是 `insert(0)` → 新集必在 manifest 第 1 位；`build_feed()` **不排序**
  → RSS 顺序 = manifest 顺序 = 发布顺序。站点首页由**前端**按 series `latest_date` 倒序排。
- **gh-pages 部署是两段**（① 推分支 ② Pages 异步发布 CDN）→ **只看 HTTP 会把「还没生效」误判为「发布失败」**。
  权威判据是 `git fetch origin gh-pages` 后的 blob。
- **gh-pages 上 mp3 必须是裸 blob**（Page 不支持 LFS）。`git cat-file -p origin/gh-pages:<mp3> | head -c4` 应为 `ID3`。
- **`index.html` 是纯 JS 外壳**（不含任何系列标题，靠 `feed.js` 运行时 fetch manifest）→
  **不可用「index.html 里有没有新系列标题」作判据**，要查查 `manifest.json`。
