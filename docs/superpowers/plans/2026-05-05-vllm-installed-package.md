# vLLM Installed Package Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `--profile vllm` 在源码目录、editable install、普通 `site-packages/vllm` 安装方式下都能保留 vLLM Python frame，避免用户调试已安装 vLLM 时 trace 为空或缺核心模块。

**Architecture:** 只调整 profile 过滤层：`vllm` package root 永远视为目标源码，常见第三方模块仍按 module root 过滤。Module classification 继续基于路径内容识别 engine、scheduler、kv_cache 等模块。

**Tech Stack:** Python 3.12+、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 site-packages vLLM RED 测试。
- [x] 调整 `_is_vllm_source` 规则。
- [x] 更新 README 说明 installed vLLM 行为。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
rtk uv run pytest tests/test_profiles.py tests/test_cli.py -q
rtk uv run pytest -q
rtk uv run python -m compileall src tests examples
```
