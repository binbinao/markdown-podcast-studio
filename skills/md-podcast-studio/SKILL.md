---
name: md-podcast-studio
description: "Self-contained Markdown-to-Podcast pipeline: scaffold a fresh project, split articles into scripts, direct AI voice (MiniMax / edge-tts / fish-speech), build RSS + dark site, deploy to GitHub Pages. Bundles the verified pipeline code, config, site templates and CI workflow."
---

# Markdown Podcast Studio — Skill

把 Markdown 文章变成可上线播客的完整、可移植流水线。本 skill 自带**已验证可用**的流水线代码与工程模板，能在任意新仓库 scaffold 出一套 Markdown→播客工程。

## 何时使用
- 用户想把一篇 Markdown / 长文 / 白皮书变成播客（单人或双人）。
- 需要从零搭建一套文字转语音播客工程（脚手架）。
- 需要排查 prepare / TTS / build / 部署 各环节的问题。

## 目录布局（本 skill 内）
- `scripts/src/` — 流水线代码（= 已验证的 myPodcast `src/`，**原样打包，不修改逻辑**）
- `templates/` — 可移植工程模板：`config.yaml`、`pyproject.toml`、`requirements.txt`/`requirements.lock`、`site/`（Jinja2 暗色站点）、`github/workflows/publish.yml`（gh-pages 部署）
- `bin/scaffold` — 在新目录实例化整套工程
- `references/`
  - `command-reference.md` — 精确 CLI 调用（prepare / build / 全序列）
  - `config-spec.md` — `config.yaml` 字段规范
  - `hard-constraints.md` — 8 条硬约束（团队必守）
  - `troubleshooting.md` — 已知坑与排错

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

### 三 TTS 后端速选
| 后端 | 密钥 | 何时用 |
|---|---|---|
| `edge-tts` | 无 | 烟雾测试 / CI 默认（`TTS_BACKEND=edge-tts`） |
| `minimax` | `MINIMAX_API_KEY` | 主用：单人 / 反思独白 / 商务节目（8 种情绪 + 22 拟声词） |
| `fish-speech` | `FISH_AUDIO_API_KEY` | Fish Audio OpenAudio S2，hosted API；国内访问有 4 坑（见 hard-constraints C9） |

切换**只改 `config.yaml` 的 `tts.backend`**，不改业务代码。

## 角色分工（与专家团对应）
| 阶段 | 负责角色 | 核心动作 |
|------|----------|----------|
| prepare | 脚本编辑 | 决策门、分集、生成草稿、`ai_stage` 生命周期 |
| TTS | 配音导演 | 选声、prosody、ffmpeg 拼接 |
| build/deploy | 发布工程师 | 质量门禁、RSS、暗色站点、`--skip-audio`、gh-pages |

> 详细命令、配置、约束与排错见 `references/`。**代码是冻结资产**：本 skill 只复制、不修改流水线逻辑；仓库后续演进需重新打包。
