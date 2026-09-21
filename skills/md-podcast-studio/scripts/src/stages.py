"""draft 生命周期状态机。

两条并行的生命周期，都写在 frontmatter 里，互不覆盖：

1. ``ai_stage`` —— 稿子本身的成熟度（prepare 写入，人工认领）
2. ``humanize_stage`` —— 卡兹克活人感抛光走到哪一步（C11 硬门禁的判据）

drafts/ 是评审门：prepare 写入，人工审阅，build **只读**消费。

``ai_stage``::

    skeleton  ── prepare 拿不到 LLM key 时的骨架稿，未口语化
    generated ── prepare 经 LLM 改写产出，未经人工审阅
    reviewed  ── 人工审阅通过（`python -m src.stages mark-reviewed`）
    frozen    ── 锁稿：语义同 reviewed，额外声明"不要再重生成覆盖"

``humanize_stage``::

    skeleton  ── 草稿产出但还没抛给卡兹克（prepare 的初始值）
    humanized ── 卡兹克已改稿 in-place 写回
    reviewed  ── 用户评完卡兹克版（`mark-humanize-reviewed`）
    frozen    ── 用户 freeze（不再重生成）

**build 对所有 stage 一律只读**——stage 只决定告警等级，永不改变正文。
重构前 build 会跑 ``polish()`` 二次 LLM 改写，导致：人工在 drafts/ 的修改被吃、
LLM 成本翻倍、同一 draft 每次 build 输出不同（不可复现）。

两条生命周期的阻断强度不同：
- ``ai_stage`` 缺失/未审 → **只告警**（存量稿全无此字段，硬拦会堵死现有工作流）
- ``humanize_stage`` 不在 {reviewed, frozen} → **硬阻断 build**（hard-constraint C11），
  可用 ``build --skip-humanize`` 豁免（仅 CI / 烟雾测试）

CLI::

    python -m src.stages mark-humanize-reviewed drafts/<slug>
    python -m src.stages mark-reviewed          drafts/<slug>
    python -m src.stages show                   drafts/<slug>
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

# 卡兹克抛光阶段（与 ai_stage 并列的另一条生命周期）
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

# 卡兹克门禁只认这两个值
_HUMANIZE_APPROVED: frozenset[str] = frozenset({HUMANIZE_REVIEWED, HUMANIZE_FROZEN})

# frontmatter 块（前后 --- 包裹）。DOTALL 让 . 吃换行，非贪婪停在第一个闭合 ---。
_FM_RE = re.compile(r"^(---[ \t]*\n)(.*?)(\n---[ \t]*\n)", re.DOTALL)
_STAGE_LINE_RE = re.compile(r"^ai_stage:[ \t]*(\S+)[ \t]*$", re.M)
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
    """从 draft frontmatter 读 humanize_stage。缺字段或非法值返回 ""。"""
    raw = str(meta.get("humanize_stage", "") or "").strip().lower()
    return raw if raw in ALL_HUMANIZE_STAGES else ""


def is_humanize_approved(stage: str) -> bool:
    """用户是否已认领卡兹克抛光稿（reviewed/frozen）。"""
    return stage in _HUMANIZE_APPROVED


def humanize_stage_warning(stage: str) -> str:
    """build 消费 draft 时的卡兹克阶段告警文案。返回 "" 表示已通过。

    卡兹克是必做（hard-constraint C11）：build 前必须 humanize_stage ∈ {reviewed, frozen}。
    这里只返回文案，由 build 决定是否抛错（抛错走 error_policy.stop_and_notify）。
    """
    if is_humanize_approved(stage):
        return ""
    if stage == HUMANIZE_SKELETON:
        return (
            "draft 未走卡兹克活人感抛光（humanize_stage: skeleton）。"
            " 卡兹克必做：build 前必须调度 script-humanizer 改稿并评审到 reviewed/frozen。"
        )
    if stage == HUMANIZE_HUMANIZED:
        return (
            "draft 已卡兹克改稿但未人工评审（humanize_stage: humanized）。"
            " 评审后跑 `python -m src.stages mark-humanize-reviewed <path>`。"
        )
    return (
        "draft 无 humanize_stage 字段（早于本字段引入的 legacy）。"
        " 走完卡兹克后跑 `python -m src.stages mark-humanize-reviewed <path>` 补标记。"
    )


def stage_warning(stage: str) -> str:
    """build 消费 draft 时的告警文案。返回 "" 表示无需告警。

    这里刻意只告警不阻断：存量 draft 可能全无 ai_stage，硬拦会直接堵死现有工作流。
    卡兹克那条生命周期的强阻断由 humanize_stage_warning + C11 负责。
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
            " 审完跑 `python -m src.stages mark-reviewed <路径>` 消除此告警。"
        )
    return (
        "draft 无 ai_stage 标记（legacy）。"
        " 跑 `python -m src.stages mark-reviewed <路径>` 补标记。"
    )


def _rewrite_fm_line(path: Path, pattern: re.Pattern[str], key: str, value: str) -> str:
    """把 frontmatter 里的 `<key>:` 行改写为 `<key>: <value>`，返回旧值。

    键不存在则在 frontmatter 末尾追加一行。正文与其余字段逐字节保留。
    无 frontmatter 时抛 ValueError。
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} 没有 frontmatter，不是合法 draft")

    head, fm_body, fm_tail = m.group(1), m.group(2), m.group(3)
    hit = pattern.search(fm_body)
    if hit:
        old = hit.group(1).strip().lower()
        new_fm = pattern.sub(f"{key}: {value}", fm_body, count=1)
    else:
        old = ""
        new_fm = f"{fm_body}\n{key}: {value}"

    path.write_text(head + new_fm + fm_tail + text[m.end():], encoding="utf-8")
    return old


def set_stage(path: Path, stage: str) -> str:
    """改写单个 draft 的 ai_stage，返回旧值（legacy 返回 ""）。"""
    if stage not in ALL_STAGES:
        raise ValueError(f"未知 stage: {stage!r}，合法值 {ALL_STAGES}")
    return _rewrite_fm_line(path, _STAGE_LINE_RE, "ai_stage", stage)


def set_humanize_stage(path: Path, stage: str) -> str:
    """改写单个 draft 的 humanize_stage，返回旧值（未设返回 ""）。

    与 set_stage 对称：只动 frontmatter 的 humanize_stage 一行，
    正文与其余字段逐字节保留。
    """
    if stage not in ALL_HUMANIZE_STAGES:
        raise ValueError(f"未知 humanize_stage: {stage!r}，合法值 {ALL_HUMANIZE_STAGES}")
    return _rewrite_fm_line(path, _HUMANIZE_LINE_RE, "humanize_stage", stage)


def iter_drafts(target: Path) -> list[Path]:
    """收集 target 下的 draft 文件。target 可以是单个 ep-XX.md 或含它们的目录。"""
    target = Path(target)
    if target.is_file():
        return [target]
    return sorted(p for p in target.glob("**/*.md") if _EP_FILE_RE.match(p.name))


def _project_root(target: Path) -> Path:
    """从 drafts 路径启发式上溯到工程根（含 config.yaml 或 raw/）。"""
    proj = Path(target).resolve()
    for _ in range(5):
        if (proj / "config.yaml").exists() or (proj / "raw").exists():
            return proj
        parent = proj.parent
        if parent == proj:
            break
        proj = parent
    return Path(target).resolve()


def mark_reviewed(target: Path, stage: str = STAGE_REVIEWED) -> list[tuple[Path, str]]:
    """把 target 下所有 draft 标为 reviewed，返回 [(路径, 旧 stage)]。"""
    drafts = iter_drafts(target)
    if not drafts:
        raise ValueError(f"{target} 下没有 ep-XX.md draft")
    results = [(p, set_stage(p, stage)) for p in drafts]
    # emit_phase2_review metrics（best-effort，失败不阻塞评审门）
    try:
        from .metrics import emit_phase2_review
        proj = _project_root(target)
        for p, old in results:
            emit_phase2_review(proj, episode_path=str(p), stage_from=old, stage_to=stage)
    except Exception:  # noqa: BLE001
        pass
    return results


def mark_humanize_reviewed(
    target: Path, stage: str = HUMANIZE_REVIEWED
) -> list[tuple[Path, str]]:
    """把 target 下所有 draft 标为 humanize_stage=reviewed，返回 [(路径, 旧值)]。

    这是解除 C11 卡兹克门禁的**唯一正规入口**：不跑它 build 会被硬阻断。
    """
    drafts = iter_drafts(target)
    if not drafts:
        raise ValueError(f"{target} 下没有 ep-XX.md draft")
    return [(p, set_humanize_stage(p, stage)) for p in drafts]


def init_humanize_stage(path: Path) -> str:
    """草稿生成时初始化 humanize_stage=skeleton（如果还没有字段）。

    prepare_file() 在草稿落盘后调用，确保每集都有 humanize_stage 字段。
    返回旧值（未设→""，已设→旧值）。
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if not _FM_RE.match(text):
        return ""
    hit = _HUMANIZE_LINE_RE.search(_FM_RE.match(text).group(2))
    if hit:
        return hit.group(1).strip().lower()
    return set_humanize_stage(path, HUMANIZE_SKELETON)


def main(argv: list[str] | None = None) -> int:
    """CLI：mark-reviewed / mark-humanize-reviewed / show。"""
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        prog="python -m src.stages",
        description="draft 生命周期标记（ai_stage / humanize_stage）",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_r = sub.add_parser("mark-reviewed", help="标记 ai_stage（默认 reviewed）")
    p_r.add_argument("path", help="drafts/<slug> 目录或单个 ep-XX.md")
    p_r.add_argument("--stage", default=STAGE_REVIEWED, choices=list(ALL_STAGES))

    p_h = sub.add_parser("mark-humanize-reviewed", help="标记 humanize_stage，解除 C11 门禁")
    p_h.add_argument("path", help="drafts/<slug> 目录或单个 ep-XX.md")
    p_h.add_argument("--stage", default=HUMANIZE_REVIEWED, choices=list(ALL_HUMANIZE_STAGES))

    p_s = sub.add_parser("show", help="打印 draft 的两条生命周期状态")
    p_s.add_argument("path", help="drafts/<slug> 目录或单个 ep-XX.md")

    args = ap.parse_args(argv)

    if args.cmd == "show":
        from .ingest import parse_script
        drafts = iter_drafts(Path(args.path))
        if not drafts:
            print(f"{args.path} 下没有 ep-XX.md draft", file=sys.stderr)
            return 1
        for p in drafts:
            meta, _ = parse_script(p.read_text(encoding="utf-8"))
            ai = stage_of(meta) or "(missing)"
            hu = humanize_stage_of(meta) or "(missing)"
            gate = "通过" if is_humanize_approved(hu) else "阻断"
            print(f"{p}\n    ai_stage={ai}  humanize_stage={hu}  → C11 门禁：{gate}")
        return 0

    fn = mark_reviewed if args.cmd == "mark-reviewed" else mark_humanize_reviewed
    try:
        results = fn(Path(args.path), args.stage)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    key = "ai_stage" if args.cmd == "mark-reviewed" else "humanize_stage"
    for p, old in results:
        print(f"  {p.name}: {key} {old or '(未设)'} → {args.stage}")
    print(f"✓ 已更新 {len(results)} 个 draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
