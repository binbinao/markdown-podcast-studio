# Command Reference — Markdown→Podcast 流水线

> 所有命令从**工程根目录**运行（即含 `src/`、`config.yaml`、`raw/`、`drafts/`、`output/` 的目录）。
> 需要 Python >=3.13 和系统级 `ffmpeg` + `ffprobe`（pip 装不了，缺则 `brew install ffmpeg` 或 apt 安装）。

## 入口
`pyproject.toml` 注册了两个 console script，等价于模块形式：
- `mypodcast-prepare = "src.prepare:main"`
- `mypodcast-build = "src.build:main"`

可用 `python -m src.prepare` / `python -m src.build`（推荐，免安装）。

---

## 1. PREPARE（raw → drafts）

```bash
python -m src.prepare                        # 处理全部 raw/*.md
python -m src.prepare --article raw/foo.md   # 单篇
python -m src.prepare --raw raw              # 默认 raw 目录
python -m src.prepare --drafts drafts        # 默认 drafts 目录
python -m src.prepare --config config.yaml   # 默认 config.yaml

python -m src.prepare --yes                  # == --auto：接受 AI 推荐、无交互（CI/批处理）
python -m src.prepare --mark-reviewed <path> # 置 ai_stage=reviewed
python -m src.prepare --freeze <path>        # 置 ai_stage=frozen
```
- 三决策门（format / voice / split）：frontmatter 同时含 `format`+`voice`+`split_strategy` 时跳过交互，尊重作者预决策。
- 产出：`drafts/<date-slug>/ep-XX.md`（人工评审门）。

---

## 2. BUILD（drafts → output + RSS + 站点）

```bash
python -m src.build drafts/                  # 构建全部系列
python -m src.build drafts/2026-08-02-foo/ep-01.md   # 单文件
python -m src.build drafts/ --out output
python -m src.build drafts/ --config config.yaml

python -m src.build drafts/ --skip-audio     # CI/静态部署：复用 mp3，只重渲 RSS/站点
python -m src.build drafts/ --only ep-01     # 只处理「文件名 == ep-01.md」的单集（配合 --force 真合成）
python -m src.build drafts/ --from ep-03     # 从某集续跑（失败即停）
python -m src.build drafts/ --retry-failed   # 只重建缺失 source_hash 的集
python -m src.build drafts/ --force          # 忽略 source_hash，重建 mp3。⚠️ 见下方副作用警告
python -m src.build drafts/ --voice VOICE_ID # 覆盖音色（仅 solo）
```
- `run_one` 五步：`[1/5]` 读草稿（只读，不调 polish）→ `[2/5]` parse_script → `[3/5]` validate_script（门禁 BLOCK 抛错）→ `[4/5]` write_shownotes → `[5/5]` register_episode（manifest 写 source_hash 续跑）。
- 全部成功后渲染 `output/feed.xml`（RSS 2.0）+ `output/index.html`（Jinja2 暗色站点）+ `series/<slug>/ep-XX/episode.mp3`。
- ⚠️ **`--only` 匹配的是 `ep-XX` 文件名，不是系列 slug**。传 slug 会报「`--only xxx` 找不到对应 draft」。
  要限定系列，就把 draft 目录当位置参数：`python -m src.build drafts/<slug>`。

### ⚠️ `--force` 的副作用（v1.2.2 必读）
`--force` 会让**全部**集数重走 `register_episode()`，而它结尾是 `eps.insert(0, entry)` → 于是：
- 所有 `shownotes.md` 的 `date` 被刷成当天（draft 无 `date:` 时取渲染当天）；
- **manifest / RSS 顺序被打乱**（`build_feed()` 不排序，数组顺序即发布顺序），新集不再在第 1 位。

⇒ **`--skip-audio --force` 是一次性诊断**：跑它是为了验证渲染路径 + 确认「失败 0」，
但**它产出的 output 不是可提交终态**，必须还原再用**非 force** 构建重注册新集。
完整还原命令见 `troubleshooting.md` §7 与 hard-constraints **C12**。

### 退出码
- `0` EXIT_OK：全部成功
- `1` EXIT_PIPELINE_FAIL：任一集失败（**跳过** RSS/站点重建，避免发布 broken 站点）
- `2` EXIT_GATE_VIOLATION：门禁/校验违规（不在 build 内抛出）

---

## 3. 完整本地序列

```bash
# 1. 作者放文章
cp my-article.md raw/2026-08-06-my-article.md

# 2. 摄取 + 分集 + 生成草稿（交互，或 --yes 全自动）
python -m src.prepare --yes

# 3. 人工打开 drafts/2026-08-06-my-article/ep-01.md 编辑，然后：
python -m src.prepare --mark-reviewed drafts/2026-08-06-my-article

# 4. 合成音频 + RSS + 站点（minimax 需 MINIMAX_API_KEY；edge-tts 免密）
export MINIMAX_API_KEY=...
python -m src.build drafts/

# 5. 提交推送 → GitHub Actions 用 --skip-audio 重渲并部署 gh-pages
git add output drafts && git commit -m "new episodes" && git push
```

---

## 4. 密钥（仅运行时从 env 读取，绝不写进 config/代码/包）
- `MINIMAX_API_KEY`：MiniMax TTS 端点 `https://api.minimaxi.com/v1/t2a_v2`（模型 `speech-2.8-hd`）。
- `LLM_API_KEY` / `MINIMAX_API_KEY` / `OPENAI_API_KEY`：generate/polish/prosody/voicecaster 的 LLM 后端（优先级见 hard-constraints）。
- edge-tts 后端：无需密钥。

## 5. 部署
- `.github/workflows/publish.yml`：push 到 `main` 触发，路径含 `output/** drafts/** src/** config.yaml scripts/** templates/** .github/**`。
- 步骤：checkout（lfs:true）→ Python 3.13 → 装 ffmpeg → `pip install -r requirements.lock` → 跑单测 → `TTS_BACKEND=edge-tts python -m src.build drafts/ --skip-audio` → `peaceiris/actions-gh-pages@v4` 部署 `output/` 到 `gh-pages`（force_orphan, lfs:true）。
- 站点 URL：`config.yaml` 的 `podcast.website`（当前 `https://binbinao.github.io/myPodcast`）。

---

## 6. 上线验收（v1.2.2 新增）

> gh-pages 部署是**两段**：① Actions 推分支；② Pages **异步**发布 CDN。所以 **HTTP 会滞后**——
> 只看 `curl` 会把「还没生效」误判成「发布失败」。**权威判据是 `git fetch` 后的 blob。**

```bash
# 1. 顺序断言：新集必须在第 1 位（register_episode 是 insert(0)；build_feed 不排序）
python -c "import json;e=json.load(open('output/manifest.json'))['episodes'];print(e[0]['_key'])"
grep -m1 '<title>' output/feed.xml

# 2. 拉取远端分支（不 fetch 的话本地 origin/gh-pages 也是旧的，会得出错误结论）
git fetch origin gh-pages

# 3. 新集产物在位 + mp3 是裸 blob（Pages 不支持 LFS）
git ls-tree -r -l origin/gh-pages -- series/<slug>
git cat-file -p origin/gh-pages:series/<slug>/ep-01/episode.mp3 | head -c4   # 期望 ID3

# 4. 逐字节比对三个含数据的产物
for f in manifest.json feed.xml index.html; do
  [ "$(git hash-object output/$f)" = "$(git rev-parse origin/gh-pages:$f)" ] \
    && echo "OK   $f" || echo "DIFF $f"; done

# 5. 音频最终校验（应等于本地 sha256，也等于 LFS oid）
curl -sL <site>/series/<slug>/ep-01/episode.mp3 | shasum -a 256
```

- ⚠️ **`index.html` 是纯 JS 外壳**，不含任何系列标题（连老系列也没有）→
  **不要用「index.html 里有没有新系列标题」当判据**，要查就查 `manifest.json`。
- 若只有 `manifest.json` / `feed.xml` 不一致、而 `index.html` 一致 = **CDN 半刷新**，不是内容分歧，等一会儿再测。
- 完整清单与原理见 `troubleshooting.md` §6 / §7。
