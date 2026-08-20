"""metrics：每阶段指标采集（v1.2.0 引入）。

设计原则（v1.2.0）：
1. **反馈环入口**：metrics 写到 `output/metrics/<date>/`，下个迭代可被 SOP 引用
2. **每阶段独立**：避免一个汇总文件丢失即全丢
3. **机器可读 + 人可读**：JSON 字段为主
4. **不替代告警**：本模块只采集事后回顾指标；实时告警另说

阶段→函数对应：
- prepare_file() 后 → emit_phase1(...)
- mark_reviewed() 后 → emit_phase2_review(...)
- run_one() 完成后 → emit_phase3(...)/emit_phase4(...)
- run() 完成后 → emit_phase5_summary(...)

参见 `references/metrics.md` 字段规范。
"""
from __future__ import annotations

import json
import time
from datetime import date as _date
from pathlib import Path
from typing import Any


def _today_str() -> str:
    return _date.today().isoformat()


def _metrics_dir(out_dir: Path, phase: str) -> Path:
    """每个阶段独立目录：output/metrics/<date>/phase<phase>.json"""
    d = out_dir / "metrics" / _today_str()
    d.mkdir(parents=True, exist_ok=True)
    return d / f"phase{phase}.json"


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """原子写入（先写 .tmp 再 rename），避免半截文件。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


class Timer:
    """上下文管理器：with Timer() as t: ... t.duration_sec 自动记。"""

    def __init__(self) -> None:
        self.start: float = 0.0
        self.duration_sec: float = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.duration_sec = round(time.monotonic() - self.start, 2)


def emit_phase1(
    out_dir: Path,
    *,
    article_path: str,
    episode_count: int,
    decision_gate_skipped: bool,
    frontmatter_complete: bool,
    llm: dict[str, Any] | None = None,
    duration_sec: float,
    errors: list[str] | None = None,
) -> None:
    """Phase 1 prepare 完成时调用。"""
    payload = {
        "date": _today_str(),
        "stage": "phase1",
        "article": article_path,
        "episode_count": episode_count,
        "decision_gate_skipped": decision_gate_skipped,
        "frontmatter_complete": frontmatter_complete,
        "llm": llm or {},
        "duration_sec": duration_sec,
        "errors": errors or [],
    }
    _write_atomic(_metrics_dir(out_dir, "1"), payload)


def emit_phase15(
    out_dir: Path,
    *,
    episode_path: str,
    episodes_polished: int,
    word_count_delta_pct: float,
    humanize_rounds: int,
    review_script_failures: int,
    duration_sec: float,
    errors: list[str] | None = None,
) -> None:
    """Phase 1.5 卡兹克抛光完成时调用。"""
    payload = {
        "date": _today_str(),
        "stage": "phase1.5",
        "episode": episode_path,
        "episodes_polished": episodes_polished,
        "word_count_delta_pct": round(word_count_delta_pct, 2),
        "humanize_rounds": humanize_rounds,
        "review_script_failures": review_script_failures,
        "duration_sec": duration_sec,
        "errors": errors or [],
    }
    _write_atomic(_metrics_dir(out_dir, "1.5"), payload)


def emit_phase2_review(
    out_dir: Path,
    *,
    episode_path: str,
    stage_from: str,
    stage_to: str,
    review_duration_min: float | None = None,
) -> None:
    """Phase 2 评审门 mark-reviewed/freeze 时调用。"""
    payload = {
        "date": _today_str(),
        "stage": "phase2",
        "episode": episode_path,
        "stage_from": stage_from,
        "stage_to": stage_to,
        "review_duration_min": review_duration_min,
    }
    _write_atomic(_metrics_dir(out_dir, "2"), payload)


def emit_phase3(
    out_dir: Path,
    *,
    episode_path: str,
    backend: str,
    voice_id: str,
    episodes_synthesized: int,
    episodes_failed: int,
    retries_total: int,
    avg_synth_duration_sec: float,
    total_audio_sec: int,
    cost_estimate_usd: float | None = None,
    duration_sec: float,
    errors: list[str] | None = None,
) -> None:
    """Phase 3 TTS 完成时调用。"""
    payload = {
        "date": _today_str(),
        "stage": "phase3",
        "episode": episode_path,
        "backend": backend,
        "voice_id": voice_id,
        "episodes_synthesized": episodes_synthesized,
        "episodes_failed": episodes_failed,
        "retries_total": retries_total,
        "avg_synth_duration_sec": round(avg_synth_duration_sec, 2),
        "total_audio_sec": total_audio_sec,
        "cost_estimate_usd": cost_estimate_usd,
        "duration_sec": duration_sec,
        "errors": errors or [],
    }
    _write_atomic(_metrics_dir(out_dir, "3"), payload)


def emit_phase4(
    out_dir: Path,
    *,
    validate_script_block_rate: float,
    resume_hit_rate: float,
    skip_audio: bool,
    rss_episodes: int,
    site_html_kb: int,
    deploy_success: bool,
    duration_sec: float,
    errors: list[str] | None = None,
) -> None:
    """Phase 4 build/发布完成时调用。"""
    payload = {
        "date": _today_str(),
        "stage": "phase4",
        "validate_script_block_rate": round(validate_script_block_rate, 4),
        "resume_hit_rate": round(resume_hit_rate, 4),
        "skip_audio": skip_audio,
        "rss_episodes": rss_episodes,
        "site_html_kb": site_html_kb,
        "deploy_success": deploy_success,
        "duration_sec": duration_sec,
        "errors": errors or [],
    }
    _write_atomic(_metrics_dir(out_dir, "4"), payload)


def emit_phase5_summary(
    out_dir: Path,
    *,
    cycle_time_hours: float,
    user_review_time_hours: float | None,
    first_attempt_success: bool,
    phases_succeeded: list[str],
    phases_degraded: list[str],
) -> None:
    """Phase 5 端到端完成时调用（汇总指标）。"""
    payload = {
        "date": _today_str(),
        "stage": "phase5",
        "cycle_time_hours": round(cycle_time_hours, 2),
        "user_review_time_hours": (
            round(user_review_time_hours, 2) if user_review_time_hours is not None else None
        ),
        "first_attempt_success": first_attempt_success,
        "phases_succeeded": phases_succeeded,
        "phases_degraded": phases_degraded,
    }
    _write_atomic(_metrics_dir(out_dir, "5"), payload)


def read_phase(out_dir: Path, phase: str) -> dict[str, Any] | None:
    """读取某阶段的指标（供下次迭代 feedback loop）。"""
    p = _metrics_dir(out_dir, phase)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


__all__ = [
    "Timer",
    "emit_phase1",
    "emit_phase15",
    "emit_phase2_review",
    "emit_phase3",
    "emit_phase4",
    "emit_phase5_summary",
    "read_phase",
]