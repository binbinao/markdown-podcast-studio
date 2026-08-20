"""episode_hash：草稿正文指纹（v1.2.0 引入）。

与 source_hash（源稿 `raw/<slug>.md` 指纹）的区别：
- `source_hash`：源稿指纹，raw 变了才变 → 触发重生成（raw 改了草稿也得重生成）
- `episode_hash`：草稿正文指纹（**不含** frontmatter），草稿正文变了才变
  → 卡兹克写回 / 用户评审改字 / 改 frontmatter 都不计入

build 续跑逻辑（v1.2.0）：
1. source_hash + episode_hash 都未变 → 跳过（纯 frontmatter 改动 / 啥都没改）
2. episode_hash 变 → 重生成（草稿正文改了）
3. source_hash 变 → 重生成（raw 改了）

用法：
    from .episode_hash import episode_hash_from_body, hash_episode_body

    body_text = ...   # 草稿正文（不含 frontmatter）
    h = hash_episode_body(body_text)
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

# frontmatter 块（前后 --- 包裹，DOTALL 多行匹配）
_FM_RE = re.compile(r"^---[ \t]*\n.*?\n---[ \t]*\n", re.DOTALL)

# 与 feed.py 的 _hash_source 保持一致的截断长度
_HASH_LEN = 16


def hash_episode_body(body: str) -> str:
    """对草稿正文（不含 frontmatter）算 SHA256 前 16 位。"""
    if not body:
        return ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:_HASH_LEN]


def episode_hash_from_body(body: str) -> str:
    """alias：与 source_hash 命名风格一致（_hash_source / episode_hash_from_body）。"""
    return hash_episode_body(body)


def episode_hash_of(meta: dict, body: str) -> str:
    """从 frontmatter dict + 正文算 episode_hash。

    优先读 frontmatter 里已有的 `episode_hash` 字段（手动 override）；否则现算。
    """
    override = str(meta.get("episode_hash", "") or "").strip()
    if override:
        return override[:_HASH_LEN]
    return hash_episode_body(body)


def split_frontmatter(raw: str) -> tuple[str, str]:
    """把 draft 拆成 (frontmatter, body)。

    frontmatter 含前后 ---；body 是 frontmatter 之后的所有内容。
    没有 frontmatter 时 frontmatter = ""，body = raw。
    """
    m = _FM_RE.match(raw)
    if not m:
        return "", raw
    return m.group(0), raw[m.end():]


def should_resynthesize(
    old_source_hash: Optional[str],
    old_episode_hash: Optional[str],
    new_source_hash: Optional[str],
    new_episode_hash: Optional[str],
) -> bool:
    """判断 build 是否需要重合成 mp3。

    规则：
    - 任意一个 hash 缺失（legacy / 首次 build）→ 重生成
    - source_hash 变了 → 重生成（raw 改了）
    - episode_hash 变了 → 重生成（草稿正文改了，卡兹克写回 / 用户改字）
    - 都未变 → 跳过
    """
    if not old_source_hash or not old_episode_hash:
        return True
    if not new_source_hash or not new_episode_hash:
        return True
    return old_source_hash != new_source_hash or old_episode_hash != new_episode_hash


__all__ = [
    "hash_episode_body",
    "episode_hash_from_body",
    "episode_hash_of",
    "split_frontmatter",
    "should_resynthesize",
]