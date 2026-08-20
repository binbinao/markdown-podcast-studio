"""Unit tests for episode_hash module (v1.2.0+)."""
from __future__ import annotations

import sys
from pathlib import Path

# 让 tests/ 能 import src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.episode_hash import (
    episode_hash_of,
    split_frontmatter,
    should_resynthesize,
    hash_episode_body,
)


def test_split_frontmatter_basic():
    fm, body = split_frontmatter("---\nkey: val\n---\n正文")
    assert fm == "---\nkey: val\n---\n"
    assert body == "正文"


def test_split_frontmatter_no_frontmatter():
    fm, body = split_frontmatter("纯正文")
    assert fm == ""
    assert body == "纯正文"


def test_episode_hash_changes_with_content():
    h1 = hash_episode_body("今天讲物理")
    h2 = hash_episode_body("今天讲化学")
    assert h1 != h2
    assert len(h1) == 16  # SHA256 前 16 位


def test_episode_hash_stable_for_same_content():
    h1 = hash_episode_body("同一个内容")
    h2 = hash_episode_body("同一个内容")
    assert h1 == h2


def test_episode_hash_ignores_frontmatter():
    """frontmatter 不计入 hash。"""
    h1 = episode_hash_of({"title": "A"}, "正文")
    h2 = episode_hash_of({"title": "B"}, "正文")
    assert h1 == h2


def test_should_resynthesize_legacy():
    """任一 hash 缺失（legacy）→ 重生成。"""
    assert should_resynthesize(None, None, "a", "b") is True
    assert should_resynthesize("a", "b", None, None) is True


def test_should_resynthesize_no_change():
    """都未变 → 跳过。"""
    assert should_resynthesize("a", "b", "a", "b") is False


def test_should_resynthesize_source_changed():
    """source_hash 变了 → 重生成。"""
    assert should_resynthesize("a", "b", "a2", "b") is True


def test_should_resynthesize_episode_changed():
    """episode_hash 变了 → 重生成（卡兹克改稿场景）。"""
    assert should_resynthesize("a", "b", "a", "b2") is True
