# Markdown Podcast Studio

把 Markdown 长文章一键端到端变成上线播客：智能拆脚本 →（可选卡兹克活人感抛光）→ AI 配音（MiniMax / edge-tts / fish-speech 三后端）→ 生成 RSS 与暗色节目站 → 部署 GitHub Pages。

> **当前版本：v1.1.0**（2026-08-20）— 流程管控专家评审应用。
> 详见 [CHANGELOG.md](./CHANGELOG.md)。回滚方式见文末。

## 类型

Team 型（多角色协作团队，5 人）

## 团队成员

| 成员 | 花名 | 职责 |
|---|---|---|
| 播客制作总监 | — | 编排调度、SOP 推进、汇总回报（RACI A 主理人）|
| 脚本编辑 | — | prepare 阶段：元数据、三决策门、分集、生成草稿、ai_stage 生命周期（RACI R）|
| 活人感改稿官 | 卡兹克 | 可选 Phase 1.5：把分集正文改写成"念起来像人在说话"，清模型腔/报告腔/营销腔（RACI R）|
| 配音导演 | — | TTS 阶段：后端选择、选声、prosody、ffmpeg 音频拼接（RACI R）|
| 发布工程师 | — | build 阶段：质量门禁、shownotes、RSS、暗色站点、gh-pages 部署（RACI R）|

## v1.1.0 关键能力（增量）

相比 v1.0.0，v1.1.0 新增 8 项治理层能力：

1. **SOP 元数据** — `SKILL.md` 头部加 `version / owner / effective_from / change_log` 三件套
2. **决策矩阵（D1-D5）** — 5 个决策点（脚手架检测 / plan_episodes fallback / 卡兹克触发 / TTS 后端选择 / 部署路径）
3. **RACI 矩阵** — 7 阶段 × 4 角色，明确 A 与 R 边界
4. **ErrorPolicy（4 类策略）** — `STOP_AND_NOTIFY` / `RETRY_WITH_BACKOFF` / `FALLBACK_BACKEND` / `DEGRADE`
5. **多门禁字段** — 新增 `humanize_stage`（Phase 1.5 评审）+ `audio_reviewed`（Phase 3 音频评审）
6. **episode_hash 改名** — `source_hash` → `episode_hash`（代码层字段名保留作为别名，向后兼容）
7. **并行评审配置** — `parallel_review: bool`（Phase 1.5 与 Phase 2 评审门可并行）
8. **Metrics + PII 文档化建议** — 每阶段指标 + 草稿出口 PII 扫描（当前文档化，src/ 改造作为 v1.2.0 候选）

完整变更清单与变更原因见 [CHANGELOG.md](./CHANGELOG.md)。

## v1.1.0 未改（受范围限制）

`skills/md-podcast-studio/scripts/src/**` 与 `bin/scaffold` 是**冻结资产**，v1.1.0 不动业务代码。下列能力需 src/ 改造，作为 v1.2.0 候选：

- metrics 实际采集（需 `scripts/src/metrics.py` 新文件）
- PII 扫描实际接入 prepare 出口（需 `scripts/src/pii_scan.py` 新文件）
- ErrorPolicy 自动 fallback 实际接入（需 `scripts/src/backends/` 改造）
- `humanize_stage` / `audio_reviewed` 在 prepare/build 中识别（需 `scripts/src/stages.py` + `scripts/src/build.py` 改造）

## 功能

- **智能拆脚本**：基于 frontmatter 三件套（format / voice / split_strategy）+ `plan_episodes(strategy=...)` 拿真实集数。
- **活人感抛光（可选）**：调度 script-humanizer（卡兹克，`skills: [human-writing]`）把分集正文改成"念起来像人在说话"。
- **三后端 TTS**：edge-tts（免密 / CI）/ MiniMax（主用，speech-2.8-hd + 3 次重试）/ fish-speech（Fish Audio OpenAudio S2，含国内访问 4 条踩坑修复）。
- **质量门禁**：validate_script 拦 emoji / 零宽 / markdown 粗体 / 链接 / 引用 / 超长。
- **RSS 2.0 + 暗色站点**：Jinja2 主题 #0b0c10 + #ff7a59 + #7c5cff。
- **续跑与 CI**：`--skip-audio` 幂等跳过已注册集；`--only ep-XX --force` 单集真合成。
- **一键部署**：push `output/` → GitHub Actions 用 `--skip-audio` 重渲并部署到 `gh-pages`。

## 使用示例

- 「把这篇 Markdown 变成一档播客」
- 「配音前让卡兹克先活人感抛光」
- 「用双人对话模式重新生成这期节目」
- 「构建并发布节目站到 GitHub Pages」

## 回滚（v1.1.0 → v1.0.0）

```bash
# 方式 A：从 git tag 回滚（推荐）
cd /Users/jiduobin/.workbuddy/plugins/marketplaces/my-experts/plugins/markdown-podcast-studio
git checkout v1.0.0 -- .

# 方式 B：从物理归档回滚（git 损坏 / tag 误删时）
cd /Users/jiduobin/.workbuddy/plugins/marketplaces/my-experts/plugins/markdown-podcast-studio
rsync -a --delete .archive/v1.0.0/ ./
```

详见 [.archive/README.md](./.archive/README.md)。

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装

将专家包目录放到专家目录下：

```
/Users/jiduobin/.workbuddy/plugins/marketplaces/my-experts/plugins/markdown-podcast-studio/
```

然后运行注册命令使其可见：

```bash
python3 /Users/jiduobin/.workbuddy/plugins/cache/workbuddy-builtin/skill-expert-manager/0.1.0/scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
zip -r markdown-podcast-studio.zip markdown-podcast-studio/ --exclude=.archive --exclude=.git
```