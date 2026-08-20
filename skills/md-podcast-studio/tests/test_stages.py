"""Unit tests for stages module (v1.2.1 卡兹克必做门禁)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.stages import (
    STAGE_REVIEWED,
    HUMANIZE_SKELETON, HUMANIZE_HUMANIZED, HUMANIZE_REVIEWED, HUMANIZE_FROZEN,
    ALL_HUMANIZE_STAGES,
    humanize_stage_of,
    is_humanize_approved,
    humanize_stage_warning,
    set_humanize_stage,
    init_humanize_stage,
)


def test_all_humanize_stages():
    assert ALL_HUMANIZE_STAGES == (
        HUMANIZE_SKELETON,
        HUMANIZE_HUMANIZED,
        HUMANIZE_REVIEWED,
        HUMANIZE_FROZEN,
    )


def test_humanize_stage_of_empty():
    assert humanize_stage_of({}) == ""


def test_humanize_stage_of_valid():
    assert humanize_stage_of({"humanize_stage": "reviewed"}) == "reviewed"


def test_humanize_stage_of_invalid():
    assert humanize_stage_of({"humanize_stage": "bogus"}) == ""


def test_is_humanize_approved():
    assert is_humanize_approved(HUMANIZE_REVIEWED) is True
    assert is_humanize_approved(HUMANIZE_FROZEN) is True
    assert is_humanize_approved(HUMANIZE_HUMANIZED) is False
    assert is_humanize_approved(HUMANIZE_SKELETON) is False
    assert is_humanize_approved("") is False


def test_humanize_stage_warning_empty():
    """reviewed/frozen → 无警告。"""
    assert humanize_stage_warning(HUMANIZE_REVIEWED) == ""
    assert humanize_stage_warning(HUMANIZE_FROZEN) == ""


def test_humanize_stage_warning_skeleton():
    """skeleton → 卡兹克未跑警告。"""
    w = humanize_stage_warning(HUMANIZE_SKELETON)
    assert "卡兹克" in w or "humanize" in w


def test_humanize_stage_warning_humanized():
    """humanized → 卡兹克改完但未评审。"""
    w = humanize_stage_warning(HUMANIZE_HUMANIZED)
    assert "评审" in w or "review" in w


def test_init_humanize_stage(tmp_path):
    """没有 humanize_stage 字段时初始化为 skeleton。"""
    f = tmp_path / "ep-01.md"
    f.write_text("---\nai_stage: generated\n---\n正文", encoding="utf-8")
    old = init_humanize_stage(f)
    assert old == ""
    text = f.read_text(encoding="utf-8")
    assert "humanize_stage: skeleton" in text


def test_init_humanize_stage_existing(tmp_path):
    """已有 humanize_stage 时保留。"""
    f = tmp_path / "ep-01.md"
    f.write_text("---\nai_stage: generated\nhumanize_stage: reviewed\n---\n正文", encoding="utf-8")
    old = init_humanize_stage(f)
    assert old == "reviewed"
    text = f.read_text(encoding="utf-8")
    # 仍只有一处 humanize_stage
    assert text.count("humanize_stage:") == 1


def test_set_humanize_stage_valid(tmp_path):
    f = tmp_path / "ep-01.md"
    f.write_text("---\nhumanize_stage: skeleton\n---\n正文", encoding="utf-8")
    old = set_humanize_stage(f, HUMANIZE_HUMANIZED)
    assert old == "skeleton"
    text = f.read_text(encoding="utf-8")
    assert "humanize_stage: humanized" in text


def test_set_humanize_stage_invalid_value(tmp_path):
    f = tmp_path / "ep-01.md"
    f.write_text("---\nhumanize_stage: skeleton\n---\n正文", encoding="utf-8")
    with pytest.raises(ValueError):
        set_humanize_stage(f, "bogus")


def test_set_humanize_stage_no_frontmatter(tmp_path):
    f = tmp_path / "ep-01.md"
    f.write_text("纯正文", encoding="utf-8")
    with pytest.raises(ValueError):
        set_humanize_stage(f, HUMANIZE_REVIEWED)
