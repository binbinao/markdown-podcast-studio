"""draft 生命周期状态机（`ai_stage` frontmatter 字段）。

drafts/ 是评审门：prepare 写入，人工审阅，build **只读**消费。
`ai_stage` 是这条契约的唯一机器可读标记。

    skeleton  ── prepare 拿不到 LLM key 时的骨架稿，未口语化
    generated ── prepare 经 LLM 改写产出，未经人工审阅
    reviewed  ── 人工审阅通过（`prepare --mark-reviewed`）
    frozen    ── 锁稿：语义同 reviewed，额外声明"不要再重生成覆盖"

**build 对所有 stage 一律只读**——stage 只决定告警等级，永不改变正文。
重构前 build 会跑 `polish()` 二次 LLM 改写，导致：人工在 drafts/ 的修改被吃、
LLM 成本翻倍、同一 draft 每次 build 输出不同（不可复现）。

legacy draft（无 ai_stage 字段）按"未知"处理：告警但不阻断，保证存量可跑。
"""
from __future__ import annotations

import re
from pathlib import Path

STAGE_SKELETON = "skeleton"
STAGE_GENERATED = "generated"
STAGE_REVIEWED = "reviewed"
STAGE_FROZEN = "frozen"

ALL_STAGES: tuple[str, ...] = (
    STAGE_SKELETON,
    STAGE_GENERATED,
    STAGE_REVIEWED,
    STAGE_FROZEN,
)

# 人工已认领的 stage：build 不再告警
_HUMAN_APPROVED: frozenset[str] = frozenset({STAGE_REVIEWED, STAGE_FROZEN})

# frontmatter 块（前后 --- 包裹）。DOTALL 让 . 吃换行，非贪婪停在第一个闭合 ---。
_FM_RE = re.compile(r"^(---[ \t]*\n)(.*?)(\n---[ \t]*\n)", re.DOTALL)
_STAGE_LINE_RE = re.compile(r"^ai_stage:[ \t]*(\S+)[ \t]*$", re.M)

# v1.2.1：humanize_stage 字段（卡兹克抛光阶段，与 ai_stage 并列的另一条生命周期）
# skeleton    → 草稿产出但未抛卡兹克（默认初始值）
# humanized   → 卡兹克已改稿 in-place 写回
# reviewed    → 用户评完卡兹克版（人工认领）
# frozen      → 用户 freeze（不再重生成）
HUMANIZE_SKELETON = "skeleton"
HUMANIZE_HUMANIZED = "humanized"
HUMANIZE_REVIEWED = "reviewed"
HUMANIZE_FROZEN = "frozen"

ALL_HUMANIZE_STAGES: tuple[str, ...] = (
    HUMANIZE_SKELETON,
    HUMANIZE_HUMANIZED,
    HUMANIZE_REVIEWED,
    HUMANIZE_FROZEN,
)

_HUMANIZE_APPROVED: frozenset[str] = frozenset({HUMANIZE_REVIEWED, HUMANIZE_FROZEN})
_HUMANIZE_LINE_RE = re.compile(r"^humanize_stage:[ \t]*(\S+)[ \t]*$", re.M)

# 只有 ep-XX.md 是 draft；README/笔记不参与 stage 流转（与 build.py 收集规则一致）
_EP_FILE_RE = re.compile(r"^ep-\d+\.md$")


def stage_of(meta: dict) -> str:
    """从 draft frontmatter 读 ai_stage。缺字段或非法值返回 ""（legacy/未知）。"""
    raw = str(meta.get("ai_stage", "") or "").strip().lower()
    return raw if raw in ALL_STAGES else ""


def is_human_approved(stage: str) -> bool:
    """人工是否已认领这份稿子。"""
    return stage in _HUMAN_APPROVED


def humanize_stage_of(meta: dict) -> str:
    """v1.2.1：从 draft frontmatter 读 humanize_stage。缺字段或非法值返回 ""。"""
    raw = str(meta.get("humanize_stage", "") or "").strip().lower()
    return raw if raw in ALL_HUMANIZE_STAGES else ""


def is_humanize_approved(stage: str) -> bool:
    """v1.2.1：用户是否已认领卡兹克抛光稿（reviewed/frozen）。"""
    return stage in _HUMANIZE_APPROVED


def humanize_stage_warning(stage: str) -> str:
    """v1.2.1：build 消费 draft 时的卡兹克阶段告警文案。

    卡兹克是必做（hard-constraint C11），build 前必须 humanize_stage ∈ {reviewed, frozen}，
    否则 PipelineError 强阻断。这里只返回文案由 build 决定是否抛错。
    """
    if is_humanize_approved(stage):
        return ""
    if stage == HUMANIZE_SKELETON:
        return (
            "draft 未走卡兹克活人感抛光（humanize_stage: skeleton）。"
            " v1.2.1 起卡兹克必做：build 前必须调度卡兹克改稿并用户评审到 reviewed/frozen。"
        )
    if stage == HUMANIZE_HUMANIZED:
        return (
            "draft 已卡兹克改稿但未人工评审（humanize_stage: humanized）。"
            " 评审后跑 `python -m src.stages mark-humanize-reviewed <path>`。"
        )
    return (
        "draft 无 humanize_stage 字段（v1.2.0 之前 legacy）。"
        " 强制走卡兹克：跑 `python -m src.stages mark-humanize-reviewed <path>` 补标记。"
    )


def stage_warning(stage: str) -> str:
    """build 消费 draft 时的告警文案。返回 "" 表示无需告警。

    这里刻意只告警不阻断：存量 26 个 draft 全无 ai_stage，硬拦会直接堵死现有工作流。
    """
    if is_human_approved(stage):
        return ""
    if stage == STAGE_SKELETON:
        return (
            "draft 是 skeleton 骨架稿（prepare 时无 LLM key），未口语化。"
            " build 只读不改写 —— 配好 key 重跑 prepare 才能拿到口播稿。"
        )
    if stage == STAGE_GENERATED:
        return (
            "draft 未经人工审阅（ai_stage: generated）。"
            " 审完跑 `python -m src.prepare --mark-reviewed <路径>` 消除此告警。"
        )
    return (
        "draft 无 ai_stage 标记（legacy）。"
        " 跑 `python -m src.prepare --mark-reviewed <路径>` 补标记。"
    )


def set_stage(path: Path, stage: str) -> str:
    """改写单个 draft 的 ai_stage，返回旧值（legacy 返回 ""）。

    只动 frontmatter 内的 ai_stage 一行，正文与其余字段逐字节保留。
    """
    if stage not in ALL_STAGES:
        raise ValueError(f"未知 stage: {stage!r}，合法值 {ALL_STAGES}")
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} 没有 frontmatter，不是合法 draft")

    head, fm_body, fm_tail = m.group(1), m.group(2), m.group(3)
    hit = _STAGE_LINE_RE.search(fm_body)
    if hit:
        old = hit.group(1).strip().lower()
        new_fm = _STAGE_LINE_RE.sub(f"ai_stage: {stage}", fm_body, count=1)
    else:
        old = ""
        new_fm = f"{fm_body}\nai_stage: {stage}"

    path.write_text(head + new_fm + fm_tail + text[m.end():], encoding="utf-8")
    return old


def iter_drafts(target: Path) -> list[Path]:
    """收集 target 下的 draft 文件。target 可以是单个 ep-XX.md 或含它们的目录。"""
    target = Path(target)
    if target.is_file():
        return [target]
    return sorted(p for p in target.glob("**/*.md") if _EP_FILE_RE.match(p.name))


def mark_reviewed(target: Path, stage: str = STAGE_REVIEWED) -> list[tuple[Path, str]]:
    """把 target 下所有 draft 标为 reviewed，返回 [(路径, 旧 stage)]。"""
    drafts = iter_drafts(target)
    if not drafts:
        raise ValueError(f"{target} 下没有 ep-XX.md draft")
    results = [(p, set_stage(p, stage)) for p in drafts]
    # v1.2.0：emit_phase2_review metrics（best-effort，失败不阻塞评审门）
    try:
        from .metrics import emit_phase2_review
        # 启发式找 project root（含 raw/ 或 config.yaml）
        proj = Path(target).resolve()
        for _ in range(5):
            if (proj / "config.yaml").exists() or (proj / "raw").exists():
                break
            parent = proj.parent
            if parent == proj:
                break
            proj = parent
        for p, old in results:
            emit_phase2_review(
                proj,
                episode_path=str(p),
                stage_from=old,
                stage_to=stage,
            )
    except Exception:  # noqa: BLE001
        pass
    return results


def set_humanize_stage(path: Path, stage: str) -> str:
    """v1.2.1：改写单个 draft 的 humanize_stage，返回旧值（legacy 返回 ""）。

    与 set_stage 对称：只动 frontmatter 的 humanize_stage 一行，正文与其余字段逐字节保留。
    """
    if stage not in ALL_HUMANIZE_STAGES:
        raise ValueError(f"未知 humanize_stage: {stage!r}，合法值 {ALL_HUMANIZE_STAGES}")
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} 没有 frontmatter，不是合法 draft")

    head, fm_body, fm_tail = m.group(1), m.group(2), m.group(3)
    hit = _HUMANIZE_LINE_RE.search(fm_body)
    if hit:
        old = hit.group(1).strip().lower()
        new_fm = _HUMANIZE_LINE_RE.sub(f"humanize_stage: {stage}", fm_body, count=1)
    else:
        old = ""
        new_fm = f"{fm_body}\nhumanize_stage: {stage}"

    path.write_text(head + new_fm + fm_tail + text[m.end():], encoding="utf-8")
    return old


def mark_humanize_reviewed(
    target: Path, stage: str = HUMANIZE_REVIEWED
) -> list[tuple[Path, str]]:
    """v1.2.1：把 target 下所有 draft 标为 humanize_stage=reviewed，返回 [(路径, 旧 stage)]。

    用法：`python -m src.stages mark-humanize-reviewed <drafts/<slug>>`
    """
    drafts = iter_drafts(target)
    if not drafts:
        raise ValueError(f"{target} 下没有 ep-XX.md draft")
    return [(p, set_humanize_stage(p, stage)) for p in drafts]


def init_humanize_stage(path: Path) -> str:
    """v1.2.1：草稿生成时初始化 humanize_stage=skeleton（如果还没有字段）。

    prepare_file() 在草稿落盘前调用，确保每集都有 humanize_stage 字段。
    返回旧值（"未设"→""，已设→旧值）。
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return ""
    head, fm_body, fm_tail = m.group(1), m.group(2), m.group(3)
    hit = _HUMANIZE_LINE_RE.search(fm_body)
    if hit:
        return hit.group(1).strip().lower()
    new_fm = f"{fm_body}\nhumanize_stage: skeleton"
    path.write_text(head + new_fm + fm_tail + text[m.end():], encoding="utf-8")
    return ""
