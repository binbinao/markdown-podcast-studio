# 排错指南（已知坑 + 解法）

## 1. TTS 阶段
| 现象 | 根因 | 解法 |
|------|------|------|
| `No audio was received`（edge-tts） | 分集残留 `---` 水平线（C5） | 确保 `split._strip_md` 剔除；手工检查草稿正文无裸 `---` |
| ffmpeg **exit 234** | minimax mp3 标 mp4a，与 silence 拼接不兼容（C1） | concat 前 `aformat=sample_fmts=fltp:sample_rates=32000:channel_layouts=mono` + `aresample=32000` 归一化 |
| LLM 返回 content 为空 | MiniMax 未发 `thinking.disabled` + `reasoning_split`（C3） | 检查 LLM 调用是否带这两个字段；否则 token 烧在 reasoning |
| 集数异常短 | `max_tokens` 被硬编码（曾 4000 以下）（C3） | 从 config 读 `llm.max_tokens`（默认 4000） |
| TTS 偶发失败 | 端点抖动 | `_speak` 已内置 3 次重试；仍是网络问题则重试整集 |

## 2. 密钥
| 现象 | 根因 | 解法 |
|------|------|------|
| minimax 401/无音频 | `MINIMAX_API_KEY` 未设 | `export MINIMAX_API_KEY=...`（绝不要写进 config/代码） |
| LLM 调用失败 | `LLM_API_KEY`/`MINIMAX_API_KEY`/`OPENAI_API_KEY` 均未设 | 设任一 env；`resolve_api_key` 按优先级取 |
| 想免密钥 | — | 用 edge-tts 后端：`tts.backend: edge-tts`，CI 设 `TTS_BACKEND=edge-tts` |

## 3. build / 部署
| 现象 | 根因 | 解法 |
|------|------|------|
| build 跑完但 output 无变化 | 把「没报错」当「验证通过」（C7 注释） | 看 `git status` 是否有变化才是真信号；`--skip-audio` 在已注册集上**幂等跳过整集** |
| 想真重渲 RSS/站点 | `--skip-audio` 跳过音频但 manifest 未变 | `python -m src.build drafts/ --skip-audio --force` 强制重渲 |
| 单集真合成调试 | `--skip-audio` 不合成 | `python -m src.build drafts/ --only ep-XX --force` |
| 发布 broken 站点 | 某集失败仍重建 RSS | 不会：失败 → `exit 1` 且**跳过** RSS/站点重建 |
| 诡异 output 路径 | frontmatter YAML 被双引号破边界（C4） | grep log 看有无 frontmatter YAML warning；用 `yaml.safe_dump` 重写；手工改中文引号 |

## 4. 决策门 / 草稿
| 现象 | 根因 | 解法 |
|------|------|------|
| 每次都走交互决策门 | frontmatter 缺三件套 | 写齐 `format`+`voice`+`split_strategy` 跳过 |
| duo 用 `--voice` 不生效 | CLI `--voice` 对 duo 不生效（C8 注释） | 用 frontmatter `host_voice`/`guest_voice` 透传 |
| 命名被改 | 误以为 `naming_enforce` 自动 | 它**未接入** prepare/CI（hard-constraints ⚠）；手动跑 `python -m src.naming_enforce --apply`；作者命名自主 |

## 5. 环境
| 现象 | 根因 | 解法 |
|------|------|------|
| `import audioop` 报错 | Python 3.13 无 audioop，误用 pydub | 一律 ffmpeg concat（C1）；不要用 pydub |
| `ffmpeg: command not found` | ffmpeg 非 pip 包 | 系统安装：`brew install ffmpeg`（macOS）/ apt（Linux）；CI 已装 |
| 测试红 | 改了 build 调 polish | `build` 对草稿只读（C6）；恢复 |

## 真实验证顺序（commit 前）
1. `python -m src.build drafts/ --skip-audio --force` 必须绿。
2. `git status` 确认 output/ 有预期变化。
3. 再 `git add output drafts && git commit && git push`。
