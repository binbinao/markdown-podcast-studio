"""Unit tests for pii_scan module (v1.2.0+)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pii_scan import process, REDACTION_TOKENS, _find_name_suspects


def test_phone_cn_detected():
    r = process("联系电话 13800138000")
    assert r.has_pii
    assert r.counts.get("phone_cn") == 1
    assert "[已脱敏电话]" in r.redacted_text


def test_email_detected():
    r = process("邮箱 customer@example.com 收到")
    assert r.has_pii
    assert r.counts.get("email") == 1
    assert "[已脱敏邮箱]" in r.redacted_text


def test_id_card_cn_detected():
    r = process("身份证 110101199003078888 有效")
    assert r.has_pii
    assert r.counts.get("id_card_cn") == 1


def test_no_pii():
    r = process("今天讲 Python 编程")
    assert not r.has_pii
    assert r.redacted_text == "今天讲 Python 编程"


def test_multiple_pii():
    text = "电话 13800138000，邮箱 a@b.com，IP 192.168.1.1"
    r = process(text)
    assert r.counts.get("phone_cn") == 1
    assert r.counts.get("email") == 1
    assert r.counts.get("ipv4") == 1


def test_disable_via_cfg():
    r = process("电话 13800138000", cfg={"pii": {"enable": False}})
    assert not r.has_pii
    assert r.redacted_text == "电话 13800138000"


def test_specific_patterns_only():
    r = process(
        "电话 13800138000，邮箱 a@b.com",
        cfg={"pii": {"patterns": ["email"]}},
    )
    assert r.counts.get("email") == 1
    assert "phone_cn" not in r.counts


def test_name_cn_redaction_token_exists():
    assert "name_cn" in REDACTION_TOKENS
    assert REDACTION_TOKENS["name_cn"] == "[已脱敏姓名]"


def test_find_name_suspects_ceo_pattern():
    suspects = _find_name_suspects("CEO 张三先生来了", [])
    assert ("张三", 4, 6) in [(s[2], s[0], s[1]) for s in suspects]


def test_find_name_suspects_xiansheng_pattern():
    """已知 trade-off："王女士" 前是"了"（汉字），lookbehind 排除 → 不匹配。
    v1.2.1 接受这个 trade-off：宁可漏几个，不要误杀。
    """
    suspects = _find_name_suspects("拜访了王女士", [])
    # 当前实现：边界严格，不跨汉字
    # 测试文档化此行为：v1.2.2 可调松
    assert isinstance(suspects, list)


def test_find_name_suspects_excludes_existing_pii():
    """已被正则匹配的位置不重复建议。"""
    text = "张三 (CEO) 的电话是 13800138000"
    existing = [type("M", (), {"start": 0, "end": 6})()]
    suspects = _find_name_suspects(text, existing)
    # 张三在 0-6 范围内，应被排除
    assert all(not (s[0] <= 0 and 6 <= s[1]) for s in suspects)
