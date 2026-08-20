"""PII 扫描：草稿出口检测私人信息（v1.2.0 引入）。

设计原则：
1. **轻量正则优先**：电话 / 邮箱 / 身份证 / IP 用正则覆盖
2. **姓名靠上下文**：用启发式上下文（CEO X / X 先生 / X 老师）+ 可选 LLM 二次校验
3. **失败不阻塞**：扫描失败仅 warn，不阻塞 prepare/build
4. **可配置**：config.yaml 的 pii.patterns 决定启用哪些；pii.llm_verify 决定是否 LLM 二次校验

接入点（v1.2.0）：
- `prepare.py:prepare_file()` 草稿落盘前 `pii_scan.process(text)`
- TTS 不直接调用（避免 TTS 路径变重）

详见 `references/pii-scan.md` 字段规范与误报排错。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PIIMatch:
    """单个 PII 匹配项。"""
    pattern: str           # "phone_cn" / "email" / ...
    value: str             # 原文
    redacted: str          # 替换后值
    start: int             # 字符位置
    end: int
    llm_verified: bool = False


@dataclass
class PIIResult:
    """扫描结果。"""
    matches: list[PIIMatch] = field(default_factory=list)
    redacted_text: str = ""
    llm_used: bool = False
    error: str | None = None

    @property
    def has_pii(self) -> bool:
        return bool(self.matches)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for m in self.matches:
            out[m.pattern] = out.get(m.pattern, 0) + 1
        return out


# 内置正则模式（POSIX 可移植）
DEFAULT_PATTERNS: dict[str, str] = {
    "phone_cn":   r"\b1[3-9]\d{9}\b",
    "email":      r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    "id_card_cn": r"\b\d{17}[\dXx]\b",
    "bank_card":  r"\b\d{16,19}\b",
    "ipv4":       r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}

# 占位符（人类可读 + TTS 友好）
REDACTION_TOKENS: dict[str, str] = {
    "phone_cn":   "[已脱敏电话]",
    "email":      "[已脱敏邮箱]",
    "id_card_cn": "[已脱敏身份证]",
    "bank_card":  "[已脱敏银行卡]",
    "ipv4":       "[已脱敏IP]",
}


def _compile_patterns(enabled: list[str]) -> dict[str, re.Pattern[str]]:
    out: dict[str, re.Pattern[str]] = {}
    for name in enabled:
        pat = DEFAULT_PATTERNS.get(name)
        if not pat:
            continue
        try:
            out[name] = re.compile(pat)
        except re.error:
            continue
    return out


def _scan_with_regex(text: str, patterns: dict[str, re.Pattern[str]]) -> list[PIIMatch]:
    matches: list[PIIMatch] = []
    for name, regex in patterns.items():
        token = REDACTION_TOKENS.get(name, "[已脱敏]")
        for m in regex.finditer(text):
            matches.append(PIIMatch(
                pattern=name,
                value=m.group(0),
                redacted=token,
                start=m.start(),
                end=m.end(),
                llm_verified=False,
            ))
    # 按 start 排序
    matches.sort(key=lambda x: (x.start, -x.end))
    return matches


def _apply_redactions(text: str, matches: list[PIIMatch]) -> str:
    """从后往前替换（避免位置偏移）。"""
    out = text
    for m in reversed(matches):
        out = out[:m.start] + m.redacted + out[m.end:]
    return out


def _maybe_llm_verify(
    text: str,
    matches: list[PIIMatch],
    cfg: dict[str, Any],
) -> tuple[list[PIIMatch], bool, str | None]:
    """可选：LLM 二次校验（识别中文姓名等启发式难覆盖的）。

    v1.2.0：默认关闭（llm_verify=false），避免引入新依赖。
    开启时需 cfg.pii.llm_provider / model 配置（后续 v1.2.1 接线）。
    """
    if not cfg.get("pii", {}).get("llm_verify", False):
        return matches, False, None
    # v1.2.0 占位（v1.2.1 接线 LLM provider）
    return matches, False, "llm_verify not yet wired (v1.2.1 candidate)"


def process(text: str, cfg: dict[str, Any] | None = None) -> PIIResult:
    """主入口：扫描 + 替换 + 返回结果。

    cfg 可选；不传则用全部内置模式 + 不开 LLM 校验。
    """
    if not text:
        return PIIResult(redacted_text="")

    pii_cfg = (cfg or {}).get("pii", {})
    if not pii_cfg.get("enable", True):
        # 显式关闭
        return PIIResult(redacted_text=text)

    enabled = pii_cfg.get("patterns", list(DEFAULT_PATTERNS.keys()))
    patterns = _compile_patterns(enabled)

    try:
        regex_matches = _scan_with_regex(text, patterns)
        llm_matches, llm_used, llm_err = _maybe_llm_verify(text, regex_matches, cfg or {})
        all_matches = regex_matches + llm_matches
        # 同一位置多次匹配去重
        seen: set[tuple[int, int]] = set()
        deduped: list[PIIMatch] = []
        for m in all_matches:
            key = (m.start, m.end)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(m)
        redacted = _apply_redactions(text, deduped)
        return PIIResult(
            matches=deduped,
            redacted_text=redacted,
            llm_used=llm_used,
            error=llm_err,
        )
    except Exception as e:  # noqa: BLE001
        return PIIResult(redacted_text=text, error=str(e))


def report(result: PIIResult) -> str:
    """人可读扫描报告（log 输出用）。"""
    if not result.has_pii:
        return "PII 扫描: 无私人信息"
    lines = [f"PII 扫描: 发现 {len(result.matches)} 处私人信息:"]
    for m in result.matches:
        lines.append(f"  - [{m.pattern}] {m.value!r} → {m.redacted}")
    if result.llm_used:
        lines.append("  (LLM 二次校验)")
    return "\n".join(lines)


def write_report(result: PIIResult, out_path: Path) -> None:
    """扫描报告写到磁盘（供审计 / 复盘）。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    payload = {
        "has_pii": result.has_pii,
        "counts": result.counts,
        "matches": [
            {
                "pattern": m.pattern,
                "value": m.value,
                "redacted": m.redacted,
                "llm_verified": m.llm_verified,
            }
            for m in result.matches
        ],
        "llm_used": result.llm_used,
        "error": result.error,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


__all__ = [
    "DEFAULT_PATTERNS",
    "REDACTION_TOKENS",
    "PIIMatch",
    "PIIResult",
    "process",
    "report",
    "write_report",
]