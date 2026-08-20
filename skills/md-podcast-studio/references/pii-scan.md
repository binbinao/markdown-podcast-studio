# PII 扫描建议（v1.1.0 新增，G3）

> **当前为文档化建议**。实际接入需 `scripts/src/prepare.py` 出口加 `pii_scan.py`（冻结资产，不在 v1.1.0 范围）。

## 为什么播客必须 PII 扫描

播客是**公开发布**的内容。一旦 TTS 把私人姓名 / 电话 / 邮箱念出来并发布到 RSS / gh-pages：
- 难以撤回（订阅者已下载）
- 涉及 GDPR / 个保法等隐私合规
- 用户被"社死"风险

## 风险场景

| 场景 | 风险 | 示例 |
|---|---|---|
| 草稿提到"我们 CEO 张三" | 真人姓名曝光 | 商业稿件 / 内部事件 |
| 草稿提到客户邮箱"customer@example.com" | 邮箱被爬虫收集 | 售后案例 / 客户故事 |
| 草稿提到"我的电话 13800138000" | 电话被骚扰 | 个人独白 |
| 草稿提到具体地址 | 住址被定位 | 旅行 / 探店 |
| 草稿提到身份证 / 银行卡号 | 严重合规问题 | 财务案例 |

## 扫描策略

### 1. 正则识别（轻量）
```python
PATTERNS = {
    "phone_cn":     r"\b1[3-9]\d{9}\b",
    "email":        r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    "id_card_cn":   r"\b\d{17}[\dXx]\b",
    "bank_card":    r"\b\d{16,19}\b",
    "ipv4":         r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}
```

### 2. 中文姓名识别（启发式，需要 LLM 辅助）
- 上下文"我们 CEO X" / "客户 X" / "朋友 X" → 高概率姓名
- 上下文"X 先生 / X 女士 / X 老师 / X 总" → 高概率姓名
- 单字 X（"X 同意了"）→ 低概率，可能是代词

**推荐用 LLM 二次校验**（降低误报）：
```python
prompt = """以下中文文本可能含私人姓名 / 电话 / 邮箱 / 地址。请识别并标出：
<text>
...
</text>
"""
```

### 3. 处置策略
- **自动置占位**：检测到 → 替换为 `[REDACTED_NAME]` / `[REDACTED_PHONE]` 等
- **生成扫描报告**：让用户审阅
- **可配置**：用户可在 config.yaml 关闭某类扫描（如商业稿件想保留客户名）

## 接入位置（v1.1.0 未实现）

```
scripts/src/prepare.py
  ingest → ... → generate → 草稿落盘前 → pii_scan → [可配置] 二次 LLM 校验 → 草稿落盘
```

```yaml
# config.yaml（建议）
pii:
  enable: true
  scan_level: standard   # standard | strict
  redact_strategy: placeholder   # placeholder | raise（直接抛错）
  patterns: [phone_cn, email, id_card_cn]  # 选启用哪些
  llm_verify: true                # 是否二次 LLM 校验
```

## 排错

| 现象 | 根因 | 解法 |
|---|---|---|
| 误报把"小明"也置 REDACTED | 启发式过激 | 关闭 llm_verify = false 或调高阈值 |
| 漏掉真实姓名 | 单字姓名难识别 | 开 llm_verify |
| TTS 把 REDACTED 念出来 | 占位符需要朗读友好 | 用 `[已脱敏]` 代替 `[REDACTED]` |
| 客户案例需要保留姓名 | 业务需求 | `pii.patterns: []` 关闭 |

## 与 CHANGELOG 的关系

PII 扫描接入 → 写入 CHANGELOG.md 的 "Future / Out of Scope" 段，作为 v1.2.0 候选。

## 实现路径（不在 v1.1.0）

```
1. scripts/src/pii_scan.py（新文件，正则 + LLM 校验）
2. scripts/src/prepare.py 出口调 pii_scan.process(text)
3. test_pii_scan.py（误报 / 漏报测试）
4. 文档：CHANGELOG + troubleshooting 增加 PII 章节
```

估时：4 小时（含测试）。建议作为 v1.2.0 主要变更。