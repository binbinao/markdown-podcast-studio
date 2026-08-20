"""Unit tests for metrics module (v1.2.0+)."""
from __future__ import annotations

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics import (
    Timer,
    emit_phase1,
    emit_phase15,
    emit_phase2_review,
    emit_phase3,
    emit_phase4,
    emit_phase5_summary,
    read_phase,
    _today_str,
)


def test_timer_basic():
    with Timer() as t:
        time.sleep(0.01)
    assert t.duration_sec > 0
    assert t.duration_sec < 1.0


def test_timer_manual_start():
    """Timer 仅支持 context manager 模式（__enter__/__exit__）。"""
    with Timer() as t:
        time.sleep(0.01)
    # 退出时已自动 stop
    assert t.duration_sec > 0


def test_emit_phase1_creates_file(tmp_path):
    emit_phase1(
        tmp_path,
        article_path="raw/test.md",
        episode_count=2,
        decision_gate_skipped=True,
        frontmatter_complete=True,
        duration_sec=10.0,
    )
    data = read_phase(tmp_path, "1")
    assert data is not None
    assert data["episode_count"] == 2
    assert data["stage"] == "phase1"


def test_emit_phase1_atomic_write(tmp_path):
    """原子写入：临时文件存在时主文件不应存在。"""
    import src.metrics as m
    orig = m._write_atomic
    captured = {}

    def spy(out_path, payload):
        captured["out_path"] = out_path
        captured["payload"] = payload
        orig(out_path, payload)

    m._write_atomic = spy
    emit_phase1(
        tmp_path,
        article_path="raw/test.md",
        episode_count=1,
        decision_gate_skipped=False,
        frontmatter_complete=False,
        duration_sec=5.0,
    )
    m._write_atomic = orig
    assert "out_path" in captured


def test_emit_phase15_basic(tmp_path):
    emit_phase15(
        tmp_path,
        episode_path="drafts/test/ep-01.md",
        episodes_polished=3,
        word_count_delta_pct=12.5,
        humanize_rounds=1,
        review_script_failures=0,
        duration_sec=5.0,
    )
    data = read_phase(tmp_path, "1.5")
    assert data["episodes_polished"] == 3


def test_emit_phase2_review_basic(tmp_path):
    emit_phase2_review(tmp_path, episode_path="drafts/test/ep-01.md", stage_from="generated", stage_to="reviewed")
    data = read_phase(tmp_path, "2")
    assert data["stage_to"] == "reviewed"


def test_emit_phase3_basic(tmp_path):
    emit_phase3(
        tmp_path,
        episode_path="ep-01",
        backend="minimax",
        voice_id="audiobook_male_1",
        episodes_synthesized=1,
        episodes_failed=0,
        retries_total=0,
        avg_synth_duration_sec=23.5,
        total_audio_sec=23.5,
        cost_estimate_usd=0.05,
        duration_sec=30.0,
    )
    data = read_phase(tmp_path, "3")
    assert data["backend"] == "minimax"
    assert data["total_audio_sec"] == 23.5


def test_emit_phase4_basic(tmp_path):
    emit_phase4(
        tmp_path,
        validate_script_block_rate=0.0,
        resume_hit_rate=0.75,
        skip_audio=False,
        rss_episodes=8,
        site_html_kb=84,
        deploy_success=True,
        duration_sec=15.0,
    )
    data = read_phase(tmp_path, "4")
    assert data["deploy_success"] is True
    assert data["rss_episodes"] == 8


def test_emit_phase5_summary_basic(tmp_path):
    emit_phase5_summary(
        tmp_path,
        cycle_time_hours=4.2,
        user_review_time_hours=1.5,
        first_attempt_success=True,
        phases_succeeded=["phase1", "phase2", "phase3", "phase4"],
        phases_degraded=[],
    )
    data = read_phase(tmp_path, "5")
    assert data["cycle_time_hours"] == 4.2
    assert data["first_attempt_success"] is True


def test_read_phase_nonexistent(tmp_path):
    data = read_phase(tmp_path, "9")
    assert data is None


def test_metrics_date_field():
    """所有 emit_* 都应有 date 字段。"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        emit_phase1(
            tmp_path,
            article_path="raw/test.md",
            episode_count=1,
            decision_gate_skipped=True,
            frontmatter_complete=True,
            duration_sec=1.0,
        )
        data = read_phase(tmp_path, "1")
        assert data["date"] == _today_str()
