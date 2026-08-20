"""Unit tests for error_policy module (v1.2.0+)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.error_policy import (
    STOP_AND_NOTIFY,
    RETRY_WITH_BACKOFF,
    FALLBACK_BACKEND,
    DEGRADE,
    ALL_POLICIES,
    RetryConfig,
    default_retry_config,
    should_retry,
    is_retryable_exception,
    apply_policy,
    record_metrics,
    stop_and_notify,
    degrade,
)


def test_all_policies():
    assert ALL_POLICIES == (
        STOP_AND_NOTIFY,
        RETRY_WITH_BACKOFF,
        FALLBACK_BACKEND,
        DEGRADE,
    )


def test_retry_config_defaults():
    rc = default_retry_config()
    assert rc.max_attempts == 3
    assert rc.initial_delay_sec == 1.0
    assert rc.backoff_factor == 2.0


def test_retry_config_exponential_delay():
    rc = RetryConfig(max_attempts=5, initial_delay_sec=1.0, backoff_factor=2.0, max_delay_sec=100.0)
    assert rc.delay_for_attempt(1) == 1.0
    assert rc.delay_for_attempt(2) == 2.0
    assert rc.delay_for_attempt(3) == 4.0
    assert rc.delay_for_attempt(4) == 8.0
    assert rc.delay_for_attempt(10) == 100.0  # capped


def test_should_retry():
    assert should_retry(1, 3) is True
    assert should_retry(2, 3) is True
    assert should_retry(3, 3) is False
    assert should_retry(4, 3) is False


def test_is_retryable_timeout():
    assert is_retryable_exception(TimeoutError("connection timeout")) is True


def test_is_retryable_5xx():
    assert is_retryable_exception(RuntimeError("503 Service Unavailable")) is True


def test_is_not_retryable_auth():
    assert is_retryable_exception(ValueError("401 Unauthorized")) is False


def test_is_not_retryable_valueerror():
    assert is_retryable_exception(ValueError("bad input")) is False


def test_apply_policy():
    cfg = apply_policy(RETRY_WITH_BACKOFF, retry_config=RetryConfig(max_attempts=5))
    assert cfg["policy"] == RETRY_WITH_BACKOFF
    assert cfg["retry"].max_attempts == 5


def test_apply_policy_invalid():
    with pytest.raises(ValueError):
        apply_policy("UNKNOWN")


def test_record_metrics():
    m = record_metrics(
        policy=FALLBACK_BACKEND,
        attempted_backends=["minimax", "edge-tts"],
        success_backend="edge-tts",
        retries_total=6,
        degraded=True,
    )
    assert m["policy"] == FALLBACK_BACKEND
    assert m["degraded"] is True


def test_stop_and_notify_raises():
    from src.core import PipelineError
    with pytest.raises(PipelineError) as exc_info:
        stop_and_notify("phase1.5", "卡兹克门禁未通过", hint="调度 script-humanizer")
    assert "卡兹克" in str(exc_info.value)


def test_degrade_does_not_raise():
    """degrade 不抛错，仅 warn。"""
    degrade("phase3", "validate_script 软告警", reason="block rate 0%")
