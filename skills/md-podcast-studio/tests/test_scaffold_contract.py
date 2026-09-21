"""脚手架契约守护：保证「从本包 scaffold 出来的工程真的能跑」。

这个文件是 2026-09-21 一次真实事故的产物。事故现象：从本包 scaffold 一个工程，
`python -m src.build` 在**最后一步渲染站点**时 FileNotFoundError 崩掉——
`feed.py` 会读 `templates/player.js` / `feed.js` / `style.css`、`tokens.py` 会读
`templates/design-tokens.json`，而这四个文件根本没被收进包里。音频已经白合成完了，
错在最后一步，而且只在那时才暴露。

根因不是"某个人写错了"，而是**缺一条断言**：没有任何测试检查
「src 引用的模板资产在包里都存在」。于是这里补上。

同类问题（本文件一并看守）：
- 文档声称有 `TestBuildReadOnlyContract` 守护，但包内原本没有这个测试 →
  补上，并且用 AST 而不是源码字符串（防 `import x as 旧名` 绕过、防模块改名后断言静默失效）。
- C11 卡兹克门禁要求 humanize_stage ∈ {reviewed, frozen}，文档声称有
  `python -m src.stages mark-humanize-reviewed` 这个入口，但它原本不存在 →
  门禁无法解除，脚手架事实上不可用。这里用行为测试钉住入口真实可用。
- 断点续传判据曾经要求 hash truthy，导致**没有 source: 的稿件每次 build 都重渲** →
  用行为测试钉住两侧语义（正文改了要重跑、只改 frontmatter 不该重跑）。

⚠️ 本文件所有测试**不得依赖网络、不得调用真实 TTS**：门禁相关用例统一用"空正文"
草稿，让流程在校验之前就停下，既确定又不用出网。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent          # md-podcast-studio/
SCRIPTS = ROOT / "scripts"
SRC = SCRIPTS / "src"
TPL = ROOT / "templates"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# 包内应支持的 5 个 TTS 后端（与 build.py 的 voice_key 路由一一对应）
EXPECTED_BACKENDS = {
    "edge-tts": "voices",
    "minimax": "voices_minimax",
    "fish-speech": "voices_fishspeech",
    "qwen-tts": "voices_qwentts",
    "qwen3-local": "voices_qwen3local",
}

# 构建期按路径逐个读的模板资产（scaffold 必须按文件名显式 cp）。
# 少任何一个 → build 的渲染阶段 FileNotFoundError（就是上面说的那次事故）。
REQUIRED_TEMPLATE_ASSETS = [
    "player.js",
    "feed.js",
    "style.css",
    "design-tokens.json",
]

# 整目录铺出去的资产：scaffold 用 `cp -R site/.` 铺，所以脚本里不会出现具体文件名，
# 但包内必须逐个存在（这些是 Jinja2 的 include 目标，缺一个就渲染失败）。
REQUIRED_TEMPLATE_SITE_FILES = [
    "site/base.html",
    "site/partials/header.html",
    "site/partials/series.html",
    "site/partials/latest.html",
    "site/partials/footer.html",
    "site/partials/player.html",
]


class TestScaffoldAssets:
    """src 引用的每个模板资产都必须在包内存在，且必须被 scaffold 铺出去。"""

    def test_src_literal_template_refs_exist(self):
        """扫描 src/*.py 里字面量形式拼接的 templates/<x>，逐个核实文件存在。

        这一条如果红了，说明从本包 scaffold 出的工程会在渲染阶段崩。
        """
        pat = re.compile(r'["\']templates["\']\s*/\s*["\']([^"\']+)["\']')
        missing: list[str] = []
        for f in SRC.rglob("*.py"):
            for m in pat.finditer(f.read_text(encoding="utf-8")):
                name = m.group(1)
                if not (TPL / name).exists():
                    missing.append(f"{f.relative_to(ROOT)} → templates/{name}")
        assert not missing, (
            "src 引用了包内不存在的模板资产，scaffold 出的工程会在渲染阶段崩：\n  "
            + "\n  ".join(sorted(set(missing)))
        )

    @pytest.mark.parametrize("asset", REQUIRED_TEMPLATE_ASSETS + REQUIRED_TEMPLATE_SITE_FILES)
    def test_required_asset_present(self, asset: str):
        assert (TPL / asset).exists(), f"包内缺 templates/{asset}"

    @pytest.mark.parametrize("asset", REQUIRED_TEMPLATE_ASSETS)
    def test_scaffold_copies_asset_by_name(self, asset: str):
        """按名拷贝的资产必须出现在 scaffold 脚本里。

        否则文件在包里、却进不了新工程 —— 这正是事故的形态。
        """
        script = (ROOT / "bin" / "scaffold").read_text(encoding="utf-8")
        assert asset in script, (
            f"bin/scaffold 没有铺设 templates/{asset} —— "
            "包内有这个文件，但 scaffold 出的工程不会有"
        )

    def test_scaffold_copies_site_dir(self):
        """site/ 是整目录铺的，脚本里必须有这条 cp。"""
        script = (ROOT / "bin" / "scaffold").read_text(encoding="utf-8")
        assert "site/." in script, "bin/scaffold 没有铺设 templates/site/"

    def test_scaffold_is_executable(self):
        import os
        assert os.access(ROOT / "bin" / "scaffold", os.X_OK), "bin/scaffold 不可执行"

    def test_local_tts_service_bundled(self):
        """默认后端 qwen3-local 依赖本机服务，服务实现体必须在包里、且被铺出去。"""
        assert (TPL / "scripts" / "start-qwen-tts-local.sh").exists()
        assert (TPL / "scripts" / "qwen3-tts-local" / "server.py").exists()
        script = (ROOT / "bin" / "scaffold").read_text(encoding="utf-8")
        assert "scripts/." in script, "bin/scaffold 没有铺设 templates/scripts/"


class TestBackendRegistry:
    """模板默认后端必须真的已注册，否则开箱第一跑就失败。"""

    @staticmethod
    def _registry() -> dict:
        from src import backends
        return dict(backends.REGISTRY)

    @staticmethod
    def _template_config() -> dict:
        return yaml.safe_load((TPL / "config.yaml").read_text(encoding="utf-8"))

    def test_all_expected_backends_registered(self):
        reg = self._registry()
        missing = set(EXPECTED_BACKENDS) - set(reg)
        assert not missing, f"这些后端没被注册：{sorted(missing)}；已注册：{sorted(reg)}"

    def test_template_default_backend_is_registered(self):
        cfg = self._template_config()
        default = str(cfg["tts"]["backend"]).lower()
        assert default in self._registry(), (
            f"模板 config.yaml 的 tts.backend={default!r} 未注册 → "
            f"scaffold 出的工程开箱即失败。已注册：{sorted(self._registry())}"
        )

    def test_every_backend_has_voice_table(self):
        """每个后端都要有对应的 voices_* 音色表，否则 voice_map 为空。"""
        cfg = self._template_config()
        missing = [key for key in EXPECTED_BACKENDS.values() if key not in cfg]
        assert not missing, f"模板 config.yaml 缺这些音色表：{missing}"

    def test_build_routes_every_backend_to_its_table(self):
        """build.py 的 voice_key 路由必须覆盖全部后端，且指向存在的音色表。"""
        src = (SRC / "build.py").read_text(encoding="utf-8")
        cfg = self._template_config()
        for backend, key in EXPECTED_BACKENDS.items():
            assert f'"{backend}"' in src, f"build.py 的 voice_key 路由没有覆盖 {backend}"
            assert key in src, f"build.py 没有引用音色表 {key}"
            assert key in cfg, f"模板 config.yaml 缺音色表 {key}"


class TestNoStalePolishModule:
    """`polish` 已更名为 `llm`，任何残留引用都是死链或会静默失效的断言。"""

    def test_polish_module_gone(self):
        assert not (SRC / "polish.py").exists(), "src/polish.py 应已更名为 src/llm.py"
        assert (SRC / "llm.py").exists(), "src/llm.py 不存在"

    def test_no_code_imports_polish(self):
        bad: list[str] = []
        for f in list(SRC.rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
            text = f.read_text(encoding="utf-8")
            if re.search(r"^\s*from\s+\.polish\s+import|^\s*import\s+polish\b", text, re.M):
                bad.append(str(f.relative_to(ROOT)))
        assert not bad, f"仍在 import polish（应为 llm）：{bad}"


class TestBuildReadOnlyContract:
    """契约守卫：build.py 不得对 draft 做 LLM 文本改写。

    重构前 build.py 调 polish() 二次改写，吃掉人工在 drafts/ 的修改。
    规范若只写在注释里就会被后人改回去，所以用 AST 机械 enforce。

    要点（踩过的坑）：断言必须**同时**覆盖 `polish` 与 `llm` 两个名字。
    模块从 polish.py 更名为 llm.py 后，只查旧名的断言会因为"那个名字不再出现"
    而永远通过——显示绿色，实际什么都没守。
    """

    @staticmethod
    def _tree() -> ast.Module:
        return ast.parse((SRC / "build.py").read_text(encoding="utf-8"))

    def test_no_llm_module_import(self):
        """build.py 不得直接 import llm —— 只读契约要求 build 不改写正文。"""
        names: set[str] = set()
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
        for banned in ("llm", "polish"):
            assert banned not in names, f"build.py 不得 import {banned}（draft 只读契约）"

    def test_no_text_rewrite_call(self):
        """AST 查真实 Call 节点，覆盖 `from .x import y as llm_complete` 这类绕过。"""
        called = {
            node.func.id
            for node in ast.walk(self._tree())
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for name in ("llm_complete", "heuristic_clean", "polish"):
            assert name not in called, f"build.py 不得调用 {name}() —— 会改写 drafts/ 正文"

    def test_no_llm_complete_string(self):
        """源码字符串层面也不该出现（比 AST 更宽的兜底）。"""
        src = (SRC / "build.py").read_text(encoding="utf-8")
        assert "llm_complete" not in src


# 门禁用例专用草稿：frontmatter 齐全但**正文为空**。
# 空正文让 run_one 在校验/合成之前就停下，于是用例不依赖网络、也不产出音频。
GATE_DRAFT_NO_SEGMENTS = """---
title: 门禁测试
series: 门禁测试
series_slug: gate-test
episode: 1
total: 1
format: solo
voice: zh-CN-XiaoxiaoNeural
ai_stage: generated
humanize_stage: skeleton
---
"""


class TestHumanizeGateOperable:
    """C11 门禁必须"可解除"，否则脚手架事实上不可用。

    门禁要求 humanize_stage ∈ {reviewed, frozen} 才允许 build，
    而 prepare 只会初始化成 skeleton。如果没有任何入口能把状态推进到 reviewed，
    使用者就只能手改 frontmatter —— 文档声称的命令必须真实存在。
    """

    @pytest.fixture()
    def draft(self, tmp_path: Path) -> Path:
        p = tmp_path / "gate-test" / "ep-01.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(GATE_DRAFT_NO_SEGMENTS, encoding="utf-8")
        return p

    def test_skeleton_value_is_initial_state(self, draft: Path):
        """草稿的初始 humanize_stage 就是 skeleton —— 也就是默认会被门禁拦住。"""
        from src.ingest import parse_script
        from src.stages import humanize_stage_of, is_humanize_approved

        meta, _ = parse_script(draft.read_text(encoding="utf-8"))
        assert humanize_stage_of(meta) == "skeleton"
        assert is_humanize_approved("skeleton") is False

    def test_gate_blocks_skeleton(self, draft: Path, tmp_path: Path):
        """skeleton 必须被硬阻断（不是告警）。"""
        from src import build
        from src.core import PipelineError

        with pytest.raises(PipelineError) as ei:
            build.run_one(draft, tmp_path / "output", {})
        assert "卡兹克" in str(ei.value), "阻断信息应点名卡兹克门禁"

    def test_skip_humanize_escapes_gate(self, draft: Path, tmp_path: Path):
        """--skip-humanize 必须真的绕过门禁：报错应换成后一步的"没有可朗读内容"。"""
        from src import build
        from src.core import PipelineError

        with pytest.raises(PipelineError) as ei:
            build.run_one(draft, tmp_path / "output", {}, skip_humanize=True)
        assert "卡兹克" not in str(ei.value), "skip_humanize 没有生效"
        assert "没有可朗读" in str(ei.value), "应当推进到分段检查那一步"

    def test_cli_marks_humanize_reviewed(self, draft: Path):
        """`python -m src.stages mark-humanize-reviewed` 必须真实可用。"""
        from src import stages

        assert stages.main(["mark-humanize-reviewed", str(draft.parent)]) == 0
        text = draft.read_text(encoding="utf-8")
        assert "humanize_stage: reviewed" in text
        assert text.count("humanize_stage:") == 1, "不应重复插入字段"

    def test_gate_passes_after_cli(self, draft: Path, tmp_path: Path):
        """走完 CLI 后门禁必须放行（报错换成"没有可朗读内容"）。"""
        from src import build, stages
        from src.core import PipelineError

        stages.main(["mark-humanize-reviewed", str(draft.parent)])
        with pytest.raises(PipelineError) as ei:
            build.run_one(draft, tmp_path / "output", {})
        assert "卡兹克" not in str(ei.value), "门禁没有被解除"

    def test_cli_rejects_unknown_stage(self, draft: Path):
        from src import stages

        with pytest.raises(ValueError):
            stages.mark_humanize_reviewed(draft.parent, "bogus")

    def test_cli_show_reports_status(self, draft: Path, capsys):
        from src import stages

        assert stages.main(["show", str(draft.parent)]) == 0
        out = capsys.readouterr().out
        assert "humanize_stage=skeleton" in out
        assert "阻断" in out


class TestResumeFingerprint:
    """断点续传判据（`build._is_unchanged`）的两侧语义。

    历史缺陷：判据写成 `if src_h and old == src_h`，要求指纹 truthy →
    **没有 source: 的稿件每次都判为"已变"**，于是每次 build 都重渲，
    manifest.updated / 条目顺序 / feed.xml 每部署一次就变，续跑彻底失效。
    """

    @staticmethod
    def _ep_hash(body: str) -> str:
        from src.episode_hash import episode_hash_of
        return episode_hash_of({}, body)

    def test_no_source_is_unchanged_when_body_untouched(self):
        from src.build import _is_unchanged

        meta = {"series_slug": "s", "episode": 1}
        old = {"episode_hash": self._ep_hash("[host] 正文")}
        assert _is_unchanged(meta, old, "[host] 正文") is True

    def test_no_source_reruns_when_body_changed(self):
        from src.build import _is_unchanged

        meta = {"series_slug": "s", "episode": 1}
        old = {"episode_hash": self._ep_hash("[host] 老正文")}
        assert _is_unchanged(meta, old, "[host] 新正文") is False

    def test_legacy_entry_without_any_hash_is_unchanged(self):
        """两条指纹都没有（legacy 条目）→ 不重渲，否则每次 build 都白跑。"""
        from src.build import _is_unchanged

        assert _is_unchanged({"episode": 1}, {}, "") is True

    def test_missing_source_file_is_changed(self, tmp_path: Path):
        """写了 source: 但文件不存在 → 视为已变，不静默放过。"""
        from src.build import _is_unchanged

        meta = {"source": str(tmp_path / "nope.md")}
        assert _is_unchanged(
            meta, {"source_hash": "deadbeef", "episode_hash": "x"}, ""
        ) is False

    def test_source_hash_change_is_detected(self, tmp_path: Path):
        from src.build import _is_unchanged
        from src.feed import _hash_source

        src_file = tmp_path / "a.md"
        src_file.write_text("原文", encoding="utf-8")
        meta = {"source": str(src_file)}
        stale = {"source_hash": "stale", "episode_hash": "x"}
        assert _is_unchanged(meta, stale, "") is False

        good = {"source_hash": _hash_source(str(src_file)), "episode_hash": "x"}
        assert _is_unchanged(meta, good, "") is True


class TestManifestDualHash:
    """register_episode 必须把两条指纹都写进 manifest（缺一条续跑判据就残废）。"""

    def test_register_writes_both_hashes(self, tmp_path: Path):
        from src.feed import load_manifest, register_episode

        meta = {
            "series_slug": "dual", "series": "双指纹", "episode": 1,
            "title": "双指纹测试", "total": 1,
        }
        register_episode(tmp_path, meta, "dual", 12, 345, body="[host] 正文内容")
        ep = load_manifest(tmp_path)["episodes"][0]
        assert ep["_key"] == "dual::ep-01"
        assert ep["episode_hash"], "episode_hash 没写进 manifest"
        # 无 source → source_hash 为 None 是正常的（无可比对）
        assert ep["source_hash"] is None
        assert ep["duration"] == 12 and ep["size"] == 345

    def test_episode_hash_differs_for_different_body(self, tmp_path: Path):
        from src.feed import load_manifest, register_episode

        base = {"series_slug": "d2", "series": "x", "episode": 1, "title": "t", "total": 1}
        register_episode(tmp_path, base, "d2", 1, 1, body="正文 A")
        first = load_manifest(tmp_path)["episodes"][0]["episode_hash"]
        register_episode(tmp_path, base, "d2", 1, 1, body="正文 B")
        second = load_manifest(tmp_path)["episodes"][0]["episode_hash"]
        assert first != second
