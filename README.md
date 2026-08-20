# Markdown Podcast Studio

把 Markdown 长文章一键端到端变成上线播客：智能拆脚本 →（可选卡兹克活人感抛光）→ AI 配音（MiniMax / edge-tts / fish-speech 三后端）→ 生成 RSS 与暗色节目站 → 部署 GitHub Pages。

## 类型

Team 型（多角色协作团队）

## 团队成员

| 成员 | 花名 | 职责 |
|---|---|---|
| 播客制作总监 | — | 编排调度、SOP 推进、汇总回报 |
| 脚本编辑 | — | prepare 阶段：元数据、三决策门、分集、生成草稿、ai_stage 生命周期 |
| 活人感改稿官 | 卡兹克 | 可选 Phase 1.5：把分集正文改写成"念起来像人在说话"，清模型腔/报告腔/营销腔，保留 frontmatter 与 ai_stage 不动 |
| 配音导演 | — | TTS 阶段：后端选择、选声、prosody、ffmpeg 音频拼接 |
| 发布工程师 | — | build 阶段：质量门禁、shownotes、RSS、暗色站点、gh-pages 部署 |

## 功能

- **智能拆脚本**：基于 frontmatter 三件套（format / voice / split_strategy）+ plan_episodes 拿真实集数，避免 AI 推荐与实际生成不一致。
- **活人感抛光（可选）**：调度 script-humanizer（卡兹克）把分集正文改成"念起来像人在说话"，保留事实、数字、专有名词与 frontmatter 不动；方法论基于 `human-writing` Skill。
- **三后端 TTS**：edge-tts（免密 / CI）/ MiniMax（主用，speech-2.8-hd + 3 次重试）/ fish-speech（Fish Audio OpenAudio S2，含国内访问 4 条踩坑修复）。
- **质量门禁**：validate_script 拦 emoji / 零宽 / markdown 粗体 / 链接 / 引用 / 超长正文，避免发 broken 站点。
- **RSS 2.0 + 暗色站点**：Jinja2 主题 #0b0c10 + #ff7a59 + #7c5cff，5 sections（Hero/Series/Latest/About/Subscribe）。
- **续跑与 CI**：`--skip-audio` 幂等跳过已注册集；`--only ep-XX --force` 单集真合成；CI 用 `--skip-audio` 复用 git-LFS mp3 重渲。
- **一键部署**：push `output/` → GitHub Actions 用 `--skip-audio` 重渲并部署到 `gh-pages`。

## 使用示例

- 「把这篇 Markdown 变成一档播客」
- 「配音前让卡兹克先活人感抛光」
- 「用双人对话模式重新生成这期节目」
- 「构建并发布节目站到 GitHub Pages」

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
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
zip -r markdown-podcast-studio.zip markdown-podcast-studio/
```