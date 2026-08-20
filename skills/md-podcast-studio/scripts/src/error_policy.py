"""ErrorPolicy：错误处理策略（v1.2.0 引入）。

4 类策略（与 references/error-policy.md 对齐）：
- STOP_AND_NOTIFY: 抛错给主理人升级
- RETRY_WITH_BACKOFF: 指数退避 N 次
- FALLBACK_BACKEND: 切到备用后端
- DEGRADE: 跳过该阶段继续

实现位置：
- `tts.py` 用 RETRY + FALLBACK 处理 backend 失败
- `validate.py` 用 STOP_AND_NOTIFY 处理门禁违规（已有）
- `build.py` 用 STOP_AND_NOTIFY 处理单集失败（已有）
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


# 策略枚举（string，可读性 + JSON 可序列化）
STOP_AND_NOTIFY = "STOP_AND_NOTIFY"
RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
FALLBACK_BACKEND = "FALLBACK_BACKEND"
DEGRADE = "DEGRADE"

ALL_POLICIES: tuple[str, ...] = (
    STOP_AND_NOTIFY,
    RETRY_WITH_BACKOFF,
    FALLBACK_BACKEND,
    DEGRADE,
)


@dataclass
class RetryConfig:
    """指数退避配置。"""
    max_attempts: int = 3
    initial_delay_sec: float = 1.0
    backoff_factor: float = 2.0
    max_delay_sec: float = 30.0

    def delay_for_attempt(self, attempt: int) -> float:
        """第 N 次重试前的等待秒数。attempt 从 1 开始。"""
        delay = self.initial_delay_sec * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay_sec)


def default_retry_config() -> RetryConfig:
    return RetryConfig(
        max_attempts=3,
        initial_delay_sec=1.0,
        backoff_factor=2.0,
        max_delay_sec=30.0,
    )


def should_retry(attempt: int, max_attempts: int) -> bool:
    """是否还有重试机会。attempt 从 1 开始。"""
    return attempt < max_attempts


def is_retryable_exception(exc: BaseException) -> bool:
    """判断异常是否可重试。

    v1.2.0 简化版：网络 / 5xx / Timeout 类可重试；4xx / ValueError 不重试。
    """
    name = type(exc).__name__
    msg = str(exc).lower()
    # 不重试：鉴权 / 参数错 / 业务错误
    non_retryable = (
        "401", "403", "404", "validation", "valueerror", "keyerror", "typeerror",
    )
    for nr in non_retryable:
        if nr in msg or nr in name.lower():
            return False
    # 可重试：超时 / 连接 / 5xx
    retryable = ("timeout", "connection", "5xx", "502", "503", "504", "runtimeerror")
    for r in retryable:
        if r in msg or r in name.lower():
            return True
    # 默认：未知异常 → 不重试（保守）
    return False


def apply_policy(
    policy: str,
    *,
    retry_config: RetryConfig | None = None,
    fallback_chain: list[str] | None = None,
) -> dict[str, Any]:
    """把策略解析成执行参数。"""
    if policy not in ALL_POLICIES:
        raise ValueError(f"未知策略: {policy!r}，合法值 {ALL_POLICIES}")
    return {
        "policy": policy,
        "retry": retry_config or default_retry_config(),
        "fallback_chain": list(fallback_chain or []),
    }


def record_metrics(
    policy: str,
    attempted_backends: list[str],
    success_backend: str | None,
    retries_total: int,
    degraded: bool,
) -> dict[str, Any]:
    """构造 metrics payload 的 errors 段（emit_phase3 调用）。"""
    return {
        "policy": policy,
        "attempted_backends": attempted_backends,
        "success_backend": success_backend,
        "retries_total": retries_total,
        "degraded": degraded,
    }


__all__ = [
    "STOP_AND_NOTIFY",
    "RETRY_WITH_BACKOFF",
    "FALLBACK_BACKEND",
    "DEGRADE",
    "ALL_POLICIES",
    "RetryConfig",
    "default_retry_config",
    "should_retry",
    "is_retryable_exception",
    "apply_policy",
    "record_metrics",
]