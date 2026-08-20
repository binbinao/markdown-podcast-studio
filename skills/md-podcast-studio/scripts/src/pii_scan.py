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
    "name_cn":    "[已脱敏姓名]",
}

# 中文姓名启发式上下文（v1.2.1 接入 LLM 二次校验）
# 触发模式：称谓在姓名前或后，姓名 2-3 个汉字（限制避免吞并后续称谓）
# 第一分支：称谓在前 + 姓名（name 后必须是标点空白或 TITLE_FOLLOW，避免吞并）
# 第二分支：姓名 + 称谓在后（lookahead 收紧，name 后跟 0+空白 + TITLE_FOLLOW）
_TITLE_FOLLOW = r"先生|女士|老师|总|哥|姐|兄|弟|小姐|教授|博士|校长|院长|部长|司长|局长|主任|经理"
_NAME_CONTEXT_RE = re.compile(
    r"(?:CEO|CTO|COO|CFO|CMO|VP|创始人|总裁|总监|老板|同学|同事|朋友|客户|嘉宾|主播|主持|讲师|合作伙伴)"
    r"\s+"
    r"(?P<name>[一-龥]{2,3})"
    r"(?=\s*(?:[,，。.!?:；]|\Z)|(?=" + _TITLE_FOLLOW + r"))"
    r"|(?<![一-龥])"
    r"(?P<name2>[一-龥]{2,3})"
    r"(?=\s*(?:" + _TITLE_FOLLOW + r"))"
)


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


def _find_name_suspects(text: str, existing_matches: list[PIIMatch]) -> list[tuple[int, int, str]]:
    """v1.2.1：找启发式上下文疑似的姓名位置。

    返回 [(start, end, name)]；排除已被正则匹配的位置。
    """
    out: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()
    for m in _NAME_CONTEXT_RE.finditer(text):
        # 两条分支共享同名 group 不可行（re 不支持），用 group("name") 或 group("name2")
        name = m.group("name") or m.group("name2")
        if not name:
            continue
        # groupdict() 中只有匹配上的那个有值，另一个是 None
        s = (m.start("name") if m.group("name") else m.start("name2"))
        e = (m.end("name") if m.group("name") else m.end("name2"))
        # 排除已被现有正则匹配覆盖的位置
        if any(pm.start <= s and e <= pm.end for pm in existing_matches):
            continue
        if (s, e) in seen:
            continue
        seen.add((s, e))
        out.append((s, e, name))
    return out


def _maybe_llm_verify(
    text: str,
    matches: list[PIIMatch],
    cfg: dict[str, Any],
) -> tuple[list[PIIMatch], bool, str | None]:
    """v1.2.1：LLM 二次校验识别中文姓名（启发式难覆盖）。

    设计：
    1. 默认关闭（llm_verify=false），失败 fallback 正则-only 不阻塞
    2. 开启时：启发式找"上下文疑似姓名" → 调 LLM 确认 → 添加到 matches
    3. 复用 `polish.llm_complete()`（已有 LLM helper）

    cfg.pii 配置：
    - llm_verify: bool（默认 False）
    - llm_provider / llm_model / llm_api_key_env（透传给 polish.llm_complete）
    """
    pii_cfg = (cfg or {}).get("pii", {})
    if not pii_cfg.get("llm_verify", False):
        return matches, False, None

    suspects = _find_name_suspects(text, matches)
    if not suspects:
        return matches, False, None

    try:
        from .polish import llm_complete as _llm_complete
    except ImportError:
        return matches, False, "polish.llm_complete 不可用，llm_verify 跳过"

    # 构建 prompt：让 LLM 逐个判断
    numbered = "\n".join(f"{i+1}. {name}" for i, (_, _, name) in suspects)
    system_prompt = (
        "你是中文 PII 识别助手。用户给一组 2-4 字汉字（候选姓名），"
        "判断哪些是真人的姓名（不是产品名 / 公司名 / 抽象词）。"
        "只输出编号+结果，每行一个，格式："
        "N:确认 或 N:否定（不解释）。如果都不确认，输出：none"
    )
    user_prompt = f"候选列表：\n{numbered}\n"

    try:
        raw = _llm_complete(system_prompt, user_prompt, cfg)
    except Exception as e:  # noqa: BLE001
        # LLM 调用失败 → fallback 正则-only，不阻塞
        return matches, False, f"llm_verify 调用失败（fallback 正则-only）: {e}"

    # 解析 LLM 输出
    verified: list[PIIMatch] = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.lower() == "none":
            continue
        m = re.match(r"^\s*(\d+)\s*[:：]\s*(确认|肯定|是|yes|y|true)\s*$", line, re.I)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(suspects)):
            continue
        s, e, name = suspects[idx]
        verified.append(PIIMatch(
            pattern="name_cn",
            value=name,
            redacted=REDACTION_TOKENS["name_cn"],
            start=s,
            end=e,
            llm_verified=True,
        ))

    return matches + verified, True, None


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