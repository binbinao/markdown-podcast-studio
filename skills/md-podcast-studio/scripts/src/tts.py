"""TTS 编排门面：根据 cfg['tts']['backend'] 路由到对应 backend。

具体 backend 在 src/backends/ 注册：新加 backend 只需新建文件用 @register，
config.yaml 的 tts.backend 即生效。

v1.2.0：新增 `build_episode_with_fallback` 支持 ErrorPolicy 自动切换 backend。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .error_policy import (
    FALLBACK_BACKEND,
    is_retryable_exception,
    should_retry,
)


def _enrich_with_emotion(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """给每个 segment 注入 emotion 字段（按 prosody 启发式 / LLM）。
    当前实现：整段 emotion 取该段第一句 prosody 的标签。"""
    from .prosody import plan_sentences
    out = []
    for seg in segments:
        sents = plan_sentences(seg["text"], cfg)
        emo = sents[0]["emotion"] if sents else "calm"
        out.append({**seg, "emotion": emo})
    return out


def _resolve_fallback_chain(cfg: dict[str, Any], primary: str) -> list[str]:
    """从 config 读 fallback chain。

    默认：['edge-tts']（边缘兜底，最稳定 / 免密）
    用户可在 config.yaml 覆盖：tts.fallback_chain: [edge-tts, ...]
    """
    fb = cfg.get("tts", {}).get("fallback_chain")
    if fb is None:
        # 默认：主 backend 不是 edge-tts → 兜底到 edge-tts
        return ["edge-tts"] if primary != "edge-tts" else []
    return [b.lower() for b in fb if b.lower() != primary]


def _try_backend(
    backend_name: str,
    segments: list[dict[str, Any]],
    voice_map: dict[str, str],
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    series_title: str,
    series_slug: str,
    ep_index: int,
    retries: int = 3,
) -> tuple[Path, int]:
    """单 backend + 内置重试（指数退避）。失败抛 RuntimeError。"""
    import asyncio
    from . import backends  # noqa: F401
    from .log import logger as log
    from .error_policy import is_retryable_exception as _is_retryable, should_retry as _should_retry

    if backend_name not in backends.REGISTRY:
        raise RuntimeError(f"backend '{backend_name}' 未注册。可用：{list(backends.REGISTRY.keys())}")
    backend = backends.get_backend(backend_name)

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if backend_name == "minimax":
                enriched = _enrich_with_emotion(segments, cfg)
            else:
                enriched = segments
            return backend.build_episode(
                enriched, voice_map, cfg, out_dir,
                series_title=series_title, series_slug=series_slug, ep_index=ep_index,
            )
        except Exception as e:  # noqa: BLE001
            last_err = e
            if not _is_retryable(e):
                raise RuntimeError(
                    f"backend '{backend_name}' 失败（不可重试）: {e}"
                ) from e
            if not _should_retry(attempt, retries):
                break
            wait = 2 ** (attempt - 1)
            log.warning(
                f"⚠ backend '{backend_name}' 第 {attempt}/{retries} 次失败: {e}；"
                f"{wait}s 后重试"
            )
            import time as _t
            _t.sleep(wait)
    raise RuntimeError(
        f"backend '{backend_name}' 连续 {retries} 次失败: {last_err}"
    ) from last_err


def build_episode_with_fallback(
    segments: list[dict[str, Any]],
    voice_map: dict[str, str],
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    title: str,
    series_title: str = "",
    series_slug: str = "",
    ep_index: int = 1,
) -> tuple[Path, int, dict[str, Any]]:
    """v1.2.0：主 backend 失败 → 自动切 fallback_chain → 返回 (mp3, duration, metrics)。

    metrics 字段：
    - policy: 'FALLBACK_BACKEND'
    - attempted_backends: ['minimax', 'edge-tts']
    - success_backend: 'edge-tts'
    - retries_total: 6（minimax 3 + edge-tts 3）
    - degraded: True（说明走过 fallback）
    """
    from .log import logger as log

    if not (series_title and series_slug):
        from .naming import chinese_to_ascii
        series_title = series_title or title
        series_slug = series_slug or chinese_to_ascii(series_title)

    primary = cfg.get("tts", {}).get("backend", "edge-tts").lower()
    chain = [primary] + _resolve_fallback_chain(cfg, primary)
    attempted: list[str] = []
    retries_total = 0
    last_err: Exception | None = None

    for backend_name in chain:
        attempted.append(backend_name)
        try:
            mp3, duration = _try_backend(
                backend_name, segments, voice_map, cfg, out_dir,
                series_title=series_title, series_slug=series_slug, ep_index=ep_index,
            )
            degraded = backend_name != primary
            if degraded:
                log.warning(
                    f"⚠ 主 backend '{primary}' 失败，已 fallback 到 '{backend_name}'"
                )
            return mp3, duration, {
                "policy": FALLBACK_BACKEND,
                "attempted_backends": attempted,
                "success_backend": backend_name,
                "retries_total": retries_total,
                "degraded": degraded,
            }
        except RuntimeError as e:
            last_err = e
            # 估算重试次数（每个 backend 最多 3 次）
            retries_total += 3
            log.warning(f"⚠ backend '{backend_name}' 全部失败: {e}")
            continue

    # 全部 backend 都失败
    raise RuntimeError(
        f"全部 backend 都失败: {attempted}; 最后错误: {last_err}"
    ) from last_err


def generate_audio(
    segments: list[dict[str, Any]],
    voice_map: dict[str, str],
    cfg: dict[str, Any],
    out_path: Path,
) -> int:
    """同步入口：选 backend → 调 generate，返回时长秒。"""
    import asyncio
    backend_name = cfg.get("tts", {}).get("backend", "edge-tts").lower()
    # 触发 backend 注册（如果上层未触发）
    from . import backends  # noqa: F401
    backend = backends.get_backend(backend_name)
    # 给 minimax 类 backend 注入 emotion（edge-tts 忽略 emotion 字段）
    if backend_name == "minimax":
        segments = _enrich_with_emotion(segments, cfg)
    return asyncio.run(backend.generate(segments, voice_map, cfg, out_path))


def build_episode_audio(
    segments: list[dict[str, Any]],
    voice_map: dict[str, str],
    cfg: dict[str, Any],
    out_dir: Path,
    title: str,
    series_title: str = "",
    series_slug: str = "",
    ep_index: int = 1,
) -> tuple[Path, int]:
    """生成一集音频到 output/series/<slug>/ep-XX/episode.mp3。

    v1.2.0：默认走 `build_episode_with_fallback`（ErrorPolicy 自动切 backend）。
    关闭 fallback：config.yaml 设 `tts.fallback_chain: []`。
    """
    mp3, duration, _metrics = build_episode_with_fallback(
        segments, voice_map, cfg, out_dir,
        title=title,
        series_title=series_title, series_slug=series_slug, ep_index=ep_index,
    )
    return mp3, duration