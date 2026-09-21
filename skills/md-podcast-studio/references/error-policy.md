# Error Policy（v1.1.0 文档化，v1.2.0 部分实现）

> **v1.2.0 实际接入**：`FALLBACK_BACKEND` 在 `scripts/src/tts.py:build_episode_with_fallback` 实现；`RETRY_WITH_BACKOFF` 在 `_try_backend` 实现。其他 2 类（`STOP_AND_NOTIFY` / `DEGRADE`）保持文档化建议。

## 4 类错误策略

| 策略 | 行为 | 何时用 |
|---|---|---|
| **`STOP_AND_NOTIFY`** | 抛错 + 主理人升级 + 等用户决策 | 门禁违规 / 数据丢失风险 / 不可恢复 |
| **`RETRY_WITH_BACKOFF`** | 指数退避 N 次（默认 3 次，`time.sleep(2**attempt)`）| 偶发抖动（端点 5xx、网络瞬断）|
| **`FALLBACK_BACKEND`** | 切到备用后端 / 备用 LLM | 主后端连续 3 次 5xx |
| **`DEGRADE`** | 跳过该阶段继续 + 写 metrics 记录 | 可选功能失败（`--skip-audio`）|

## 每阶段 ErrorPolicy 矩阵

| 阶段 | 错误 | 策略 | 实现位置 |
|---|---|---|---|
| Phase 0 脚手架 | `bin/scaffold` 失败 | `STOP_AND_NOTIFY` | `bin/scaffold` |
| Phase 1 脚本生成 | LLM 429 配额耗尽 | `RETRY_WITH_BACKOFF` (3) | `scripts/src/generate.py` |
| Phase 1 脚本生成 | LLM 5xx 连续 3 次 | `FALLBACK_BACKEND`（切备用 LLM）| `scripts/src/generate.py` |
| Phase 1.5 卡兹克 | LLM 改稿失败 | `STOP_AND_NOTIFY`（不写回草稿）| `agents/script-humanizer.md` |
| Phase 2 评审门 | `ai_stage` 未到 reviewed | `STOP_AND_NOTIFY` | `scripts/src/build.py` |
| Phase 2 评审门 | `humanize_stage` 未到 reviewed（Phase 1.5 触发时）| `STOP_AND_NOTIFY` | 文档层契约，代码层未实现 |
| Phase 2 评审门 | `audio_reviewed` 为 false | `DEGRADE`（警告但不阻断）| 文档层契约 |
| Phase 3 TTS | minimax 401 | `STOP_AND_NOTIFY`（密钥错治不了）| `scripts/src/backends/minimax.py` |
| Phase 3 TTS | minimax 5xx 偶发 | `RETRY_WITH_BACKOFF` (3) | `scripts/src/backends/minimax.py`（`_speak` 已内置）|
| Phase 3 TTS | minimax 连续 3 次 5xx | `FALLBACK_BACKEND`（切 edge-tts）| 文档化建议，代码层未自动实现 |
| Phase 3 TTS | fish-speech 4xx | `STOP_AND_NOTIFY`（鉴权/参数错不重试）| `scripts/src/backends/fish.py`（待补）|
| Phase 3 TTS | fish-speech 5xx | `RETRY_WITH_BACKOFF` (3) + 指数退避 | `scripts/src/backends/fish.py`（待补）|
| Phase 3 TTS | ffmpeg exit 234（mp4a 不兼容 silence）| `STOP_AND_NOTIFY` + 提示用 `aformat` 归一化 | hard-constraints C1 |
| Phase 3 TTS | edge-tts "No audio was received" | `STOP_AND_NOTIFY` + 提示检查 `---` 残留 | hard-constraints C5 |
| Phase 4 构建 | `validate_script` BLOCK | `STOP_AND_NOTIFY`（exit 2）| `scripts/src/validate.py` |
| Phase 4 构建 | 单集合成失败 | `STOP_AND_NOTIFY`（exit 1，跳过 RSS/站点重建）| `scripts/src/build.py` |
| Phase 4 部署 | gh-pages push 失败 | `STOP_AND_NOTIFY` | `.github/workflows/publish.yml` |
| Phase 5 汇报 | metrics 文件缺失 | `DEGRADE`（汇报不含 metrics 段）| `output/metrics/<date>.json` |

## 决策流程

```
阶段失败
  ↓
是门禁违规？──是──→ STOP_AND_NOTIFY
  ↓否
是 4xx（鉴权/参数）？──是──→ STOP_AND_NOTIFY（不重试）
  ↓否
是 5xx / 网络瞬断？──是──→ RETRY_WITH_BACKOFF (3)
  ↓仍失败
有备用后端？──是──→ FALLBACK_BACKEND
  ↓否 / 仍失败
是可降级阶段？──是──→ DEGRADE（写 metrics）
  ↓否
STOP_AND_NOTIFY
```

## 与 hard-constraints 关系

- `hard-constraints.md` C1-C9 是**代码级已实现**的硬约束（ffmpeg concat、MiniMax 3 次重试等）
- `error-policy.md` 是**团队级**的错误处理决策框架（覆盖代码级硬约束 + 文档化建议）
- 冲突时以 `hard-constraints.md` 为准（代码真相源）；`error-policy.md` 仅补充未实现策略

## v1.2.0 实际接入（fallback_chain 路径）

`scripts/src/tts.py` 接入：
- `_resolve_fallback_chain(cfg, primary)`：默认 `['edge-tts']`；用户可在 `config.yaml` 用 `tts.fallback_chain` 覆盖
- `_try_backend(...)`：单 backend + 内置 3 次重试 + 指数退避；4xx/参数错不重试，5xx 重试
- `build_episode_with_fallback(...)`：主 backend 失败 → 自动切 fallback chain；返回 `(mp3, duration, metrics)`

配置示例：
```yaml
tts:
  backend: minimax
  fallback_chain: [edge-tts]   # 默认值；设为 [] 关闭 fallback
```

调用点（v1.2.0）：
- `build.run_one()` 调 `build_episode_with_fallback`（替代原 `build_episode_audio`）
- metrics `emit_phase3` 收集 `attempted_backends / success_backend / retries_total / degraded`

未实现（v1.2.1 候选）：
- `STOP_AND_NOTIFY` 在 prepare/build 各阶段的标准化接入（目前抛错由各模块自己处理）
- `DEGRADE` 的具体接入点（如 validate_script 失败但可强制 publish 的场景）