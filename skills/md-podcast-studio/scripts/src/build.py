"""myPodcast 流水线编排 CLI。

用法:
    python -m src.build episodes/demo.md
    python -m src.build episodes/demo.md --out output --config config.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .core import EXIT_GATE_VIOLATION, EXIT_PIPELINE_FAIL, GateViolation, PipelineError
from typing import Any

import yaml

from .error_policy import stop_and_notify
from .feed import build_feed, build_index, register_episode, write_shownotes
from .log import logger as log
from .ingest import parse_script, slugify
from .stages import (
    humanize_stage_of,
    humanize_stage_warning,
    is_humanize_approved,
    stage_of,
    stage_warning,
)
from .tts import build_episode_with_fallback
from .voicecaster import cast as vc_cast


def run_one(
    episode_path: Path,
    out_dir: Path,
    cfg: dict[str, Any],
    voice_override: str | None = None,
    *,
    skip_humanize: bool = False,
) -> None:
    raw = Path(episode_path).read_text(encoding="utf-8")

    # draft 只读契约：build 不再对草稿做二次 LLM 改写。
    # 重构前 `polished = polish(raw, cfg)` 会把 drafts/ 里的人工修改喂给 LLM 重写一遍
    # → 人工改动被吃、LLM 成本翻倍、同一 draft 每次 build 输出不同（不可复现）。
    # 现在正文逐字节来自 draft；stage 只决定告警等级（src/stages.py）。
    log.info(f"[1/5] 读取 draft: {episode_path.name}")

    log.info("[2/5] 解析分段")
    meta, segments = parse_script(raw)
    warn = stage_warning(stage_of(meta))
    if warn:
        log.warning(f"      ⚠ {warn}")

    # 卡兹克必做强阻断（hard-constraint C11）：humanize_stage ∈ {reviewed, frozen}
    # 才允许 build，否则 PipelineError 抛错。`--skip-humanize` 是唯一豁免口，
    # 只给 CI / 烟雾测试用；正常制作流程请走 `src.stages mark-humanize-reviewed`。
    if not skip_humanize:
        h_stage = humanize_stage_of(meta)
        if not is_humanize_approved(h_stage):
            stop_and_notify(
                "phase1.5",
                f"卡兹克活人感抛光未完成（humanize_stage={h_stage or '(missing)'}）："
                f"{humanize_stage_warning(h_stage)}",
                hint=(
                    "卡兹克必做（hard-constraint C11）：先调度 script-humanizer 改稿，"
                    "再跑 `python -m src.stages mark-humanize-reviewed <path>`。"
                    " CI / 烟雾测试用 `--skip-humanize` 豁免。"
                ),
            )
        log.info(f"      ✓ 卡兹克门禁通过 (humanize_stage={h_stage})")
    else:
        log.warning("      ⚠ --skip-humanize: 卡兹克门禁豁免（仅 CI/烟雾测试用）")

    if not segments:
        raise PipelineError(
            "没有可朗读的内容，检查脚本格式或 frontmatter。",
            hint="脚本是否只有 frontmatter 没有 [host]/[guest] 段？",
        )
    title = meta.get("title") or Path(episode_path).stem
    log.info(f"      共 {len(segments)} 段，标题《{title}》")

    # 脚本质量校验：BLOCK 硬门 + WARN 软告警（Phase 3 落地重构路线图 P0-B）
    # 重构前只 report_and_warn，emoji/井号直接进 TTS 烧钱；
    # 现在 has_blocking → raise PipelineError，让 run() 计入 failed 列表并 sys.exit(1)。
    from .validate import has_blocking, report_and_warn, validate_script
    # 把 frontmatter 与正文分离
    import re as _re
    fm_match = _re.match(r"^---\n.*?\n---\n(.*)$", raw, flags=_re.S)
    body_text = fm_match.group(1) if fm_match else raw
    warnings = validate_script(meta, body_text)
    report_and_warn(episode_path.name, warnings)
    if has_blocking(warnings):
        from .validate import blocking_summary
        raise PipelineError(
            f"脚本质量 BLOCK（{episode_path.name}）",
            hint=blocking_summary(warnings),
        )

    backend = cfg.get("tts", {}).get("backend", "edge-tts").lower()
    log.info(f"[3/5] 生成音频 (backend={backend})")
    if backend == "minimax":
        voice_key = "voices_minimax"
    elif backend == "fish-speech":
        voice_key = "voices_fishspeech"
    elif backend == "qwen-tts":
        voice_key = "voices_qwentts"
    elif backend == "qwen3-local":
        voice_key = "voices_qwen3local"
    else:
        voice_key = "voices"
    voice_map = dict(cfg.get(voice_key, {}))  # 拷贝，避免改全局配置

    # 音色选型：仅 minimax backend 用 voicecaster（Fish Audio voice ID 是平台分配的，
    # voicecaster 词典是 minimax 专用的）；duo 节目保留 host/guest 映射
    fmt = str(meta.get("format", "")).lower()
    if backend in ("minimax", "qwen-tts", "qwen3-local") and fmt != "duo":
        # 优先级：CLI --voice > frontmatter voice > voicecaster 自动
        # qwen-tts / qwen3-local 的 voicecaster 词典是 minimax 专用，跳过自动选型，
        # 直接用 frontmatter voice / voices_<backend>.default
        explicit = voice_override or meta.get("voice")
        if backend in ("qwen-tts", "qwen3-local"):
            # Qwen3-TTS 音色名是英文（qwen-tts 云：Ethan/Cherry/…；
            # qwen3-local 本机：Vivian/Serena/Uncle_Fu/…），frontmatter 的
            # minimax 音色 ID（male-qn-jingying / audiobook_male_1）不适用。
            # 仅接受「显式指定」或「看起来不是 minimax ID」的值。
            if voice_override:
                voice_map["default"] = voice_override
                log.info(f"      voice CLI 覆盖 → {voice_override}")
            elif meta.get("voice") and not str(meta.get("voice")).startswith(
                    ("male-", "female-", "audiobook_")):
                voice_map["default"] = meta.get("voice")
                log.info(f"      frontmatter voice → {meta.get('voice')}")
            else:
                log.info(f"      {backend} default voice → {voice_map.get('default')}")
        else:
            source_rel = meta.get("source")
            article_text = raw
            if source_rel:
                src_path = Path(source_rel)
                if src_path.exists():
                    article_text = src_path.read_text(encoding="utf-8")
            chosen = vc_cast(article_text, cfg, explicit=explicit)
            voice_map["default"] = chosen
            if voice_override:
                log.info(f"      voice CLI 覆盖 → {voice_override}")
            else:
                log.info(f"      voicecaster → {chosen}")
    elif backend in ("minimax", "fish-speech", "qwen-tts", "qwen3-local") and fmt == "duo":
        # duo 节目：尊重 frontmatter host_voice / guest_voice；都缺再回退到
        # voices_<backend> 的 host/guest 配置。CLI --voice 在 duo 模式下不适用
        # （需要分别覆盖两个音色，应走 frontmatter 而不是 CLI 单值）。
        host_v = meta.get("host_voice") or voice_map.get("host")
        guest_v = meta.get("guest_voice") or voice_map.get("guest")
        # qwen3-local：历史稿件的 frontmatter 存的是 minimax 音色 ID（audiobook_male_1 /
        # female-chengshu），本机音色表里没有。此时忽略 frontmatter，回退到
        # voices_qwen3local 的 host/guest，而不是直接报错——保证已有稿件零改动可跑。
        if backend == "qwen3-local":
            from .backends.qwen3_local import SPEAKERS as _LOCAL_SPEAKERS
            if host_v and host_v not in _LOCAL_SPEAKERS:
                log.info(f"      host_voice={host_v!r} 非本机音色，回退 {voice_map.get('host')}")
                host_v = voice_map.get("host")
            if guest_v and guest_v not in _LOCAL_SPEAKERS:
                log.info(f"      guest_voice={guest_v!r} 非本机音色，回退 {voice_map.get('guest')}")
                guest_v = voice_map.get("guest")
        if host_v:
            voice_map["host"] = host_v
        if guest_v:
            voice_map["guest"] = guest_v
        if voice_override:
            log.warning("      --voice 对 duo 节目不生效，请改 frontmatter 的 host_voice / guest_voice")
        log.info(f"      duo voices → host={voice_map.get('host')} / guest={voice_map.get('guest')}")

    series_slug = meta.get("series_slug", "")
    series_title_v = meta.get("series", "")
    ep_index = int(meta.get("episode", 1) or 1)

    if SKIP_AUDIO:
        # 跳过 TTS 生成：用现有 mp3 元数据（用于纯重渲 index/feed/shownotes）
        from .naming import ep_output_dir as _ep_out_dir
        ep_dir = Path(_ep_out_dir(str(out_dir), series_title_v, ep_index, series_slug))
        mp3 = ep_dir / "episode.mp3"
        if not mp3.exists():
            # --skip-audio 但没有现成 mp3：常见于 CI 拿到一批新 draft 但还没 build 过音频。
            # 不再 raise（之前会直接 SystemExit 让 CI 红），改成 warning + 跳过本集。
            log.warning(f"      ⊘ {mp3} 不存在，跳过本集（先跑一次非 skip-audio build 生音频）")
            return "skipped"  # 信号给 run() 区分「正常跳过（TTS 跳）」和「无产物跳过」
        duration = _ffprobe_duration(mp3)
        size = mp3.stat().st_size
        log.info(f"      → (skip) {mp3}  ({duration // 60}分{duration % 60}秒, {size // 1024}KB)")
    else:
        # 走带 fallback 的版本（ErrorPolicy：主 backend 失败自动切备用），并采集 metrics
        mp3, duration, tts_metrics = build_episode_with_fallback(
            segments, voice_map, cfg, out_dir,
            title=title,
            series_title=series_title_v,
            series_slug=series_slug,
            ep_index=ep_index,
        )
        ep_dir = mp3.parent
        size = mp3.stat().st_size
        log.info(f"      → {mp3}  ({duration // 60}分{duration % 60}秒, {size // 1024}KB)")
        # emit_phase3 metrics（每集），best-effort
        try:
            from .metrics import emit_phase3
            emit_phase3(
                out_dir,
                episode_path=str(episode_path),
                backend=tts_metrics.get("success_backend") or backend,
                voice_id=str(voice_map.get("default", "")),
                episodes_synthesized=1,
                episodes_failed=0,
                retries_total=tts_metrics.get("retries_total", 0),
                avg_synth_duration_sec=round(duration, 2),
                total_audio_sec=duration,
                cost_estimate_usd=None,
                duration_sec=0.0,
            )
        except Exception as e:  # noqa: BLE001
            log.warning(f"⚠ emit_phase3 失败（不影响 build）: {e}")

    log.info("[4/5] 写 shownotes")
    write_shownotes(ep_dir, meta, segments, duration)

    log.info("[5/5] 更新 RSS / 节目站")
    slug = meta.get("series_slug") or slugify(meta.get("series") or title)
    # 传 body：register_episode 用它算 episode_hash（草稿正文指纹）
    register_episode(out_dir, meta, slug, duration, size, body=body_text)


SKIP_AUDIO = False


def _is_unchanged(meta_pre: dict[str, Any], old: dict[str, Any], body_pre: str = "") -> bool:
    """已注册的一集，内容指纹是否未变（决定断点续传能否跳过）。

    两道指纹各管一段，都有才比对：

    1. ``episode_hash`` —— 草稿正文（不含 frontmatter）的 hash，管「草稿正文改没改」
       （卡兹克写回、人工改字都应触发重渲）。旧条目没这字段（legacy）则跳过这道。
    2. ``source_hash`` —— raw 源文章的 hash，管「原文改没改」。

    ⚠️ 历史上这里写成 ``if src_h and old.get("source_hash") == src_h``，要求指纹
    **truthy**：于是**没有 ``source:`` 的稿子（早期 demo 稿）每次都被判为「已变」**，
    每次 build 都重渲 —— manifest 的 ``updated``、条目顺序、feed.xml 每部署一次就变，
    断点续传对它们彻底失效（2026-09-21 修复的真实缺陷）。

    现在的规则：
    - 两侧都有 episode_hash 且不等 → 已变
    - 无 ``source:`` → 只认 episode_hash；两条都没有 → 视为未变（不重渲）
    - 有 ``source:`` 但文件缺失 → 视为已变，不静默放过，让它重跑并在下游暴露问题
    """
    from .episode_hash import episode_hash_of
    from .feed import _hash_source

    new_ep = episode_hash_of(meta_pre, body_pre)
    old_ep = old.get("episode_hash")
    if new_ep and old_ep and new_ep != old_ep:
        return False

    src_field = str(meta_pre.get("source", "") or "")
    if not src_field:
        return True
    src_h = _hash_source(src_field)
    if not src_h:
        return False
    return old.get("source_hash") == src_h


def _ffprobe_duration(mp3: Path) -> int:
    import subprocess
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(mp3)],
        capture_output=True, text=True,
    )
    try:
        return int(float(r.stdout.strip()))
    except ValueError:
        return 0


def run(
    target: Path, out_dir: Path, config_path: Path,
    *,
    only: str | None = None,
    from_ep: str | None = None,
    retry_failed: bool = False,
    force: bool = False,
    voice_override: str | None = None,
    skip_humanize: bool = False,
) -> None:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    out_dir = Path(out_dir)

    if target.is_dir():
        # 递归收集 drafts 下所有 ep-XX.md（命名重构后：drafts/<series>/ep-XX.md 嵌套结构）
        # 只匹配 ep-XX.md 形式，过滤潜在的 README/笔记文件
        scripts = sorted(
            p for p in target.glob("**/*.md") if re.match(r"^ep-\d+\.md$", p.name)
        )
        if not scripts:
            raise PipelineError(
                f"目录 {target} 下没有 ep-XX.md 脚本",
                hint="确认 drafts/<series>/ep-XX.md 嵌套结构存在；README/笔记不被识别。",
            )
    else:
        scripts = [target]  # 单文件路径（local 调试用）

    # 过滤脚本列表（断点续传）
    if only:
        scripts = [s for s in scripts if s.stem == only]
        if not scripts:
            raise PipelineError(
                f"--only {only} 找不到对应 draft",
                hint="ep 文件名应为 ep-01.md / ep-02.md 形式。",
            )
    if from_ep:
        idx = next((i for i, s in enumerate(scripts) if s.stem == from_ep), None)
        if idx is None:
            raise PipelineError(f"--from {from_ep} 找不到")
        scripts = scripts[idx:]

    # 读 manifest（断点续传参考）
    from .feed import load_manifest
    manifest = load_manifest(out_dir)
    existing_keys = {e.get("_key"): e for e in manifest.get("episodes", [])}

    n_total = len(scripts)
    skipped: list[str] = []
    failed: list[str] = []
    n_run = 0
    for i, s in enumerate(scripts, 1):
        # 预解析 frontmatter 拿 series_slug + ep_index 算 _key
        from .episode_hash import split_frontmatter
        from .ingest import parse_script
        raw_pre = s.read_text(encoding="utf-8")
        meta_pre, _ = parse_script(raw_pre)
        _, body_pre = split_frontmatter(raw_pre)
        series_slug = meta_pre.get("series_slug", "")
        ep_idx = int(meta_pre.get("episode", 1) or 1)
        key = f"{series_slug}::ep-{ep_idx:02d}"

        # 断点续传：已成功且内容指纹未变 → 跳过
        if not force and not retry_failed and key in existing_keys:
            if _is_unchanged(meta_pre, existing_keys[key], body_pre):
                # 检查 mp3 是否真存在
                mp3 = out_dir / "series" / series_slug / f"ep-{ep_idx:02d}" / "episode.mp3"
                if mp3.exists():
                    skipped.append(s.name)
                    log.info(f"  [{i}/{n_total}] ⊝ 跳过 {s.name} (manifest 已注册)")
                    continue

        log.info(f"===== [{i}/{n_total}] {s.name} =====")
        try:
            result = run_one(s, out_dir, cfg, voice_override=voice_override, skip_humanize=skip_humanize)
            if result == "skipped":
                skipped.append(s.name)
            else:
                n_run += 1
        except Exception as e:  # noqa: BLE001
            failed.append(s.name)
            log.error(f"  ✗ {s.name} 失败: {e}")
            if force or from_ep:
                raise  # --only/--from 模式下任何失败立即停

    log.info(
        f"\n完成 · 运行 {n_run} / 跳过 {len(skipped)} / 失败 {len(failed)}"
    )
    if skipped:
        log.info(f"  跳过: {', '.join(skipped)}")
    if failed:
        log.error(f"  失败: {', '.join(failed)}")

    # 退出码契约：失败非空 → sys.exit(1)，不重建 RSS/index（避免发布残缺站点）。
    if failed:
        sys.exit(EXIT_PIPELINE_FAIL)

    feed = build_feed(out_dir, cfg.get("podcast", {}))
    index = build_index(out_dir, cfg.get("podcast", {}))
    log.info(f"  RSS : {feed}")
    log.info(f"  站点: {index}")

    # emit_phase5_summary（端到端 cycle time + first_attempt_success），best-effort
    try:
        from .metrics import emit_phase5_summary
        phases_succeeded = ["phase0", "phase1", "phase3", "phase4"]
        phases_degraded: list[str] = []
        if skip_humanize:
            phases_degraded.append("phase1.5")
        else:
            phases_succeeded.append("phase1.5")
            phases_succeeded.append("phase2")
        emit_phase5_summary(
            out_dir,
            # build 内算不出完整 cycle（要从 phase1 时间戳往前推），不臆造数字
            cycle_time_hours=0.0,
            user_review_time_hours=None,
            first_attempt_success=(not failed),
            phases_succeeded=phases_succeeded,
            phases_degraded=phases_degraded,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(f"⚠ emit_phase5_summary 失败（不影响 build）: {e}")


def main() -> None:
    global SKIP_AUDIO
    from .log import configure
    ap = argparse.ArgumentParser(description="myPodcast 文字转语音流水线")
    ap.add_argument("episode", help="播客脚本 markdown 路径，或含多个脚本的目录（如 drafts/xxx）")
    ap.add_argument("--out", default="output", help="输出目录 (默认 output)")
    ap.add_argument("--config", default="config.yaml", help="配置文件 (默认 config.yaml)")
    ap.add_argument("--skip-audio", action="store_true",
                    help="跳过 TTS 生成，仅用现有 mp3 重渲 shownotes/RSS/index（命名重构后修复 manifest 用）")
    ap.add_argument("--only", default=None, metavar="ep-XX",
                    help="只处理单集（如 ep-01），常配合 --force 调试")
    ap.add_argument("--from", dest="from_ep", default=None, metavar="ep-XX",
                    help="从指定集开始（断点续传）。失败时立即停")
    ap.add_argument("--retry-failed", action="store_true",
                    help="只跑上次失败的集（manifest 没 source_hash 的视为失败）")
    ap.add_argument("--force", action="store_true",
                    help="强制重生成已有 mp3，忽略 source_hash")
    ap.add_argument("--log-file", default=None, help="追加日志到此文件（默认仅 stdout）")
    ap.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR（默认 INFO）")
    ap.add_argument("--voice", dest="voice_override", default=None, metavar="VOICE_ID",
                    help="覆盖 frontmatter voice 字段，仅 solo 节目生效（duo 走 host/guest 映射）"
                         " 用于快速调音，不必重跑 prepare")
    ap.add_argument("--skip-humanize", action="store_true",
                    help="豁免卡兹克活人感抛光门禁（hard-constraint C11）。"
                         "仅 CI / 烟雾测试用；正常制作流程请用 `python -m src.stages mark-humanize-reviewed`")
    args = ap.parse_args()
    configure(level=args.log_level, log_file=args.log_file)
    SKIP_AUDIO = args.skip_audio
    try:
        run(
            Path(args.episode), Path(args.out), Path(args.config),
            only=args.only,
            from_ep=args.from_ep,
            retry_failed=args.retry_failed,
            force=args.force,
            voice_override=args.voice_override,
            skip_humanize=args.skip_humanize,
        )
    except PipelineError as e:
        log.error(f"\n✗ 流水线失败: {e}")
        if e.hint:
            log.error(f"  提示: {e.hint}")
        sys.exit(e.code)


if __name__ == "__main__":
    main()
