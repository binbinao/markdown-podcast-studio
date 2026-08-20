# Metrics 采集实现（v1.2.0 已接入，Y4）

> **v1.2.0 已实现**。`scripts/src/metrics.py` 实际采集；prepare / mark-reviewed / build 各阶段自动 emit。
> v1.1.0 时是"建议"——v1.2.0 起是"实现"。

## 设计原则（流程治理）

1. **反馈环入口**：metrics 写入 `output/metrics/<date>/`，下个迭代可被 SOP 引用
2. **每阶段独立 metrics**：避免一个汇总文件丢失即全丢
3. **机器可读 + 人可读**：JSON 字段为主，关键字段在 Markdown summary 复述
4. **不要把 metrics 当监控告警**：本建议只采集"事后回顾"指标；实时告警用另外的系统

## 每阶段指标

### Phase 1 脚本生成 → `output/metrics/<date>/phase1.json`

```json
{
  "date": "2026-08-20",
  "stage": "phase1",
  "episode_count": 8,
  "decision_gate_skipped": true,
  "frontmatter_complete": true,
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M2.5",
    "tokens_in": 12453,
    "tokens_out": 8921,
    "duration_sec": 87
  },
  "duration_sec": 142,
  "errors": []
}
```

**关键指标**：
- `decision_gate_skipped` 比率（建议 < 30%，否则用户频繁被打断）
- LLM token 消耗（成本监控）
- 单集生成耗时（性能基线）

### Phase 1.5 卡兹克 → `output/metrics/<date>/phase1.5.json`

```json
{
  "date": "2026-08-20",
  "stage": "phase1.5",
  "episodes_polished": 8,
  "word_count_delta_pct": 12.5,
  "humanize_rounds": 1,
  "review_script_failures": 0,
  "duration_sec": 340,
  "errors": []
}
```

**关键指标**：
- `word_count_delta_pct`（字数漂移率，>30% 提示偏离原意）
- `review_script_failures`（复核脚本失败数，>0 提示事实风险）
- 单集抛光耗时

### Phase 3 TTS → `output/metrics/<date>/phase3.json`

```json
{
  "date": "2026-08-20",
  "stage": "phase3",
  "backend": "minimax",
  "voice_id": "audiobook_male_1",
  "episodes_synthesized": 8,
  "episodes_failed": 0,
  "retries_total": 2,
  "avg_synth_duration_sec": 23,
  "total_audio_sec": 1840,
  "cost_estimate_usd": 1.85,
  "errors": []
}
```

**关键指标**：
- `episodes_failed / episodes_synthesized`（成功率）
- `retries_total`（抖动频率）
- `cost_estimate_usd`（成本）

### Phase 4 构建发布 → `output/metrics/<date>/phase4.json`

```json
{
  "date": "2026-08-20",
  "stage": "phase4",
  "validate_script_block_rate": 0.0,
  "resume_hit_rate": 0.75,
  "skip_audio": false,
  "rss_episodes": 8,
  "site_html_kb": 84,
  "deploy_success": true,
  "duration_sec": 67,
  "errors": []
}
```

**关键指标**：
- `validate_script_block_rate`（门禁违规率）
- `resume_hit_rate`（续跑命中率，越高越省成本）
- `deploy_success`（上线是否成功）

### Phase 5 端到端 → `output/metrics/<date>/phase5.json`

```json
{
  "date": "2026-08-20",
  "stage": "phase5",
  "cycle_time_hours": 4.2,
  "user_review_time_hours": 1.5,
  "first_attempt_success": true,
  "phases_succeeded": ["phase0", "phase1", "phase1.5", "phase2", "phase3", "phase4", "phase5"],
  "phases_degraded": []
}
```

**关键指标**：
- `cycle_time_hours`（**端到端最核心指标**——用户输入到上线的小时数）
- `user_review_time_hours`（用户在评审门上卡了多久）
- `first_attempt_success`（是否一次跑通）
- `phases_degraded`（降级跑过的阶段，应小）

## 反馈环（最重要的部分）

下个迭代启动 SOP 时，先读上次的 `output/metrics/<date>/phase5.json`：

```python
# 伪代码（v1.1.0 未实现，仅示意）
metrics = json.load(open('output/metrics/<date>/phase5.json'))
if metrics['cycle_time_hours'] > 8:
    log.warning('⚠ 端到端周期过长，建议启用 parallel_review')
if metrics['phases_degraded']:
    log.warning(f'⚠ 上次降级阶段：{metrics["phases_degraded"]}')
if metrics['user_review_time_hours'] > 2:
    log.warning('⚠ 用户评审卡顿，建议拆小批次')
```

## 与 CHANGELOG 的关系

metrics 触发的 SOP 改进 → 写入 CHANGELOG.md 的 "Future / Out of Scope" 段，让用户在下一次版本演进时看到"哪些指标建议接线"。

## 实现路径（v1.2.0 已完成）

```
1. ✅ scripts/src/metrics.py（新文件，JSON 写入 + 时间戳 + Timer + atomic write）
2. ✅ scripts/src/prepare.py:prepare_file() 出口 → emit_phase1
3. ✅ scripts/src/stages.py:mark_reviewed() 出口 → emit_phase2_review（best-effort）
4. ✅ scripts/src/build.py:run_one() 出口 → emit_phase3（含 ErrorPolicy metrics）
5. ⏳ scripts/src/build.py:run() 末尾 → emit_phase5_summary（v1.2.1 候选）
6. ⏳ test_metrics.py（v1.2.1 候选）
```

实际估时：4 小时（v1.2.0 完成）。单元测试作为 v1.2.1 候选。