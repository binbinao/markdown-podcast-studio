# 排错指南（已知坑 + 解法）

> 按「症状 → 根因 → 解法」组织。§6（发布验收）与 §7（交付纪律）是 2026-09-21 一次真实上线后新增的，
> 也是最容易**误判为故障 / 误判为通过**的两节，务必读。

## 1. TTS 阶段
| 现象 | 根因 | 解法 |
|------|------|------|
| `No audio was received`（edge-tts） | 分集残留 `---` 水平线（C5） | 确保 `split._strip_md` 剔除；手工检查草稿正文无裸 `---` |
| ffmpeg **exit 234** | minimax mp3 标 mp4a，与 silence 拼接不兼容（C1） | concat 前 `aformat=sample_fmts=fltp:sample_rates=32000:channel_layouts=mono` + `aresample=32000` 归一化 |
| LLM 返回 content 为空 | MiniMax 未发 `thinking.disabled` + `reasoning_split`（C3） | 检查 LLM 调用是否带这两个字段；否则 token 烧在 reasoning |
| LLM 返回 content 为空（**思考型模型**，如 DeepSeek-V4.1-Flash） | reasoning 与正文**共享 `max_tokens`**；预算被 reasoning 吃光 → `finish_reason` 正常但 content 空 | `max_tokens` 必须同时覆盖 reasoning + 正文（实测 1600 字输入 → reasoning 1044 + 正文 458 tokens；4000 会截断，**12000 稳**）。注意 SCNet 端点**忽略** `thinking:{type:"disabled"}` |
| 集数异常短 | `max_tokens` 被硬编码（曾 4000 以下）（C3） | 从 config 读 `llm.max_tokens`；**换思考型模型时此值必须重估，不能沿用 4000** |
| TTS 偶发失败 | 端点抖动 | `_speak` 已内置 3 次重试；仍是网络问题则重试整集 |
| 长跑 build 日志停在 `48段 → 48块` 后毫无动静 | `> log 2>&1` 重定向 → Python **块缓冲**，逐块进度不实时落盘 | **别据此判"卡死"**。用服务侧计数器看活性：`curl -s 127.0.0.1:<port>/health` → `engine.stats.{calls,total_audio_s,last_rtf,errors}`，两次采样有差值即活着 |
| 音频产出、但不确定是不是整轨静音 | 时长 / 体积 / 文件头全对**不能排除静音** | 标配 `ffmpeg -af volumedetect -f null -`：正常语音 `mean≈-24dB` / `max≈-2.6dB`；若 `max≈-91dB` 即静音 |

## 2. 密钥
| 现象 | 根因 | 解法 |
|------|------|------|
| minimax 401/无音频 | `MINIMAX_API_KEY` 未设 | `export MINIMAX_API_KEY=...`（绝不要写进 config/代码） |
| LLM 调用失败 | `LLM_API_KEY`/`MINIMAX_API_KEY`/`OPENAI_API_KEY` 均未设 | 设任一 env；`resolve_api_key` 按优先级取 |
| 想免密钥 | — | 用 edge-tts 后端：`tts.backend: edge-tts`，CI 设 `TTS_BACKEND=edge-tts` |
| 自动化/工具 shell 里 `$SOME_API_KEY` 打印为空，但交互终端里明明有 | **非交互 shell 不加载 `~/.zshrc` / `~/.bashrc`** | 显式取出：`export K=$(grep -m1 '^export K=' ~/.zshrc \| cut -d'"' -f2)`。**别据此判"密钥丢了 / 写稿通道挂了"**——曾因此误判，差点放弃 LLM 改手写稿 |

## 3. build / 部署
| 现象 | 根因 | 解法 |
|------|------|------|
| build 跑完但 output 无变化 | 把「没报错」当「验证通过」（C7 注释） | 看 `git status` 是否有变化才是真信号；`--skip-audio` 在已注册集上**幂等跳过整集** |
| 想真重渲 RSS/站点 | `--skip-audio` 跳过音频但 manifest 未变 | `python -m src.build drafts/ --skip-audio --force` —— ⚠️ **有副作用，见 §7** |
| 单集真合成调试 | `--skip-audio` 不合成 | `python -m src.build drafts/ --only ep-01 --force` |
| `--only` 报「找不到对应 draft」 | **`--only` 匹配的是 `ep-XX` 文件名，不是系列 slug** | 传 `--only ep-01`；要限定系列就把 draft 目录当位置参数（`drafts/<slug>`） |
| 新集不在 RSS / 首页第 1 条 | `--force` 全量重注册打乱了顺序 | 见 §7 还原法 |
| 发布 broken 站点 | 某集失败仍重建 RSS | 不会：失败 → `exit 1` 且**跳过** RSS/站点重建 |
| 诡异 output 路径 | frontmatter YAML 被双引号破边界（C4） | grep log 看有无 frontmatter YAML warning；用 `yaml.safe_dump` 重写；手工改中文引号 |

## 4. 决策门 / 草稿
| 现象 | 根因 | 解法 |
|------|------|------|
| 每次都走交互决策门 | frontmatter 缺三件套 | 写齐 `format`+`voice`+`split_strategy` 跳过 |
| duo 用 `--voice` 不生效 | CLI `--voice` 对 duo 不生效（C8 注释） | 用 frontmatter `host_voice`/`guest_voice` 透传 |
| 走快捷分支后 draft 的 `host_voice`/`guest_voice` 为空 | 快捷分支原先只透传 `format`/`voice`/`split_strategy`（**已修**：`_duo_voices_from_meta()` 会额外解析 `voice: "host=X / guest=Y"` 标签） | 老版本代码 / 手工稿：直接在 raw 或 draft frontmatter 显式写 `host_voice:` / `guest_voice:`。⚠️ **缺了不报错**——build 会回退默认 host/guest，属**静默降级**（音色不是你要的），所以验收要核 frontmatter |
| 想「一篇文章只出一集」（`recommend_split` 默认按 H2 出多集） | `split_strategy: by_h2` 且 H2≥2 | raw frontmatter 写 `split_strategy: by_chars` + **临时 config** 把 `split.max_episode_chars` 调到大于正文长度（**别改全局 config**） |
| 命名被改 | 误以为 `naming_enforce` 自动 | 它**未接入** prepare/CI（hard-constraints ⚠）；手动跑 `python -m src.naming_enforce --apply`；作者命名自主 |

## 5. 环境
| 现象 | 根因 | 解法 |
|------|------|------|
| `import audioop` 报错 | Python 3.13 无 audioop，误用 pydub | 一律 ffmpeg concat（C1）；不要用 pydub |
| `ffmpeg: command not found` | ffmpeg 非 pip 包 | 系统安装：`brew install ffmpeg`（macOS）/ apt（Linux）；CI 已装 |
| 测试红 | 改了 build 调 polish | `build` 对草稿只读（C6）；恢复 |
| 长任务放到 teammate 会话里跑，中途「莫名中断」 | teammate 会话结束会 **SIGKILL** 其子进程 | 长跑构建/合成**必须在主会话后台跑**（或前台等它跑完），不要交给 teammate |

---

## 6. 发布验收（release acceptance）

### 6.1 顺序语义（最容易误判）
- `feed.register_episode()` 结尾是 `eps.insert(0, entry)` → **新注册的集永远落在 manifest 第 1 位**。
- `build_feed()` **按 manifest 数组顺序迭代、完全不排序** → **RSS item 顺序 = manifest 顺序 = 发布顺序**。
- 站点首页是**前端**排序（`templates/feed.js` 按 series 的 `latest_date` 倒序）→ 新集日期最新即置顶。
- ⇒ **验收断言**：manifest 第 1 条 `_key` 应是新集；`feed.xml` 第 1 个 `<item>` 应是新集。
- 条目顺序的 churn 本身在 `build.py` 注释里被明示为"每次部署都变"（不构成问题），
  **但「新集不在第 1 位」仍是异常**——那是 `--force` 全量重注册的副作用（§7）。

### 6.2 只看 HTTP 会误判
- gh-pages 部署是**两段**：① Actions 推 `gh-pages` 分支；② Pages 服务**异步**发布到 CDN。
- ② 滞后几十秒到几分钟 → 此时 `curl` 读到的仍是**旧副本**，容易得出"发布失败"的错误结论。
- ⇒ **权威判据是 `git fetch origin gh-pages` 之后的 blob，不是 HTTP。**
- ⚠️ 不 `git fetch` 时，本地 `origin/gh-pages` 引用也是旧的 → 会得出错误结论。
- 指纹：若只有**含数据**的文件（`manifest.json` / `feed.xml`）不一致、而纯外壳 `index.html` 一致 = CDN 半刷新，**不是内容分歧**。

### 6.3 验收清单（照抄即可）
```bash
git fetch origin gh-pages
git ls-tree -r -l origin/gh-pages -- series/<slug>          # 新集 mp3 + shownotes 在位
git cat-file -p origin/gh-pages:series/<slug>/ep-01/episode.mp3 | head -c4   # 必须是 ID3（裸 blob）
for f in manifest.json feed.xml index.html; do              # 逐字节比对
  [ "$(git hash-object output/$f)" = "$(git rev-parse origin/gh-pages:$f)" ] \
    && echo "OK $f" || echo "DIFF $f"; done
curl -sL <site>/series/<slug>/ep-01/episode.mp3 | shasum -a 256   # 应等于本地 sha256（= LFS oid）
```
- **mp3 必须是裸 blob**：Pages **不支持 LFS**，`gh-pages` 上必须是真实音频字节（`ID3` 开头），
  绝不能是 LFS 指针文本。仓库里音频存两份（main 的 LFS 对象 + gh-pages 的裸 mp3）**都是必需的**，别当冗余去"优化"。
- ⚠️ **`index.html` 是纯 JS 外壳**：它**不含任何系列标题**（连老系列也没有），靠 `feed.js` 运行时 fetch `manifest.json` 渲染。
  ⇒ **「在 index.html 里搜不到新系列标题」不是故障判据**，要查就查 `manifest.json`。

---

## 7. 交付纪律：`--skip-audio --force` 是**诊断**，不是终态 ⚠️

`--force` 会让**全部**集数重新走一遍 `register_episode`，于是产生两个副作用：

1. **所有 `shownotes.md` 的 `date` 被刷成当天**（`feed.py` 取 `meta.get("date", today)`；老集全变成"今天发布"）——
   一次实测在 82 集仓库上凭空产生 ~82 处脏改动。
2. **manifest / RSS 顺序被打乱**：`register_episode` 是 `insert(0)`，全量重注册 = 按 drafts 扫描序倒序重排，
   新集不再在第 1 位（实测掉到第 27 位），RSS 发布顺序随之错乱。

### 正确姿势
```bash
# ① 诊断：验证渲染路径能跑通、确认「失败 0」（这一步是必须的）
python -m src.build drafts/ --skip-audio --force

# ② 还原：把 manifest/feed/index 退回「非 force 构建」的产物
git checkout HEAD -- output/manifest.json output/feed.xml output/index.html
git checkout -- output/series/          # 清掉那批 shownotes 日期漂移
                                        # （本集新增系列是 untracked/新加，不受影响）

# ③ 用「非 force」重注册新集：老集保持原位，新集 insert(0) 回到第 1 位
python -m src.build drafts/<新集-slug> --skip-audio
```
- 还原后 **`git diff HEAD -- output/manifest.json` 应当是「纯新增、0 删除」**——这是还原成功的判据。
- 详见 hard-constraints **C12**。

## 真实验证顺序（commit 前）
1. `python -m src.build drafts/ --skip-audio --force` 必须绿 → **但它是诊断，跑完必须按 §7 还原**。
2. `git status` 确认 output/ 有**预期的**变化（不是 82 个 shownotes 日期漂移）。
3. 跑全量单测（`python -m unittest discover -s tests`），确认血缘/契约守护测试绿。
4. `git add output drafts raw tests && git commit && git push`。
5. 等 CI 绿 → **按 §6.3 用 gh-pages blob 验收**（不要只看 HTTP）。
