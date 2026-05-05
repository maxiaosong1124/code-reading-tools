# Installable Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让当前代码 push 到 GitHub 后，云服务器可以通过 `uv tool install git+...` 直接安装并使用 `coderead serve/render/watch` 调试 vLLM。

**Architecture:** 把 `debugpy` 放入正式 package dependencies，确保 tool install 会安装 adapter。`coderead serve` 和生成的 task 默认使用 `sys.executable -m debugpy.adapter` 启动 adapter，避免依赖目标开源项目自己的 Python 环境。

**Tech Stack:** Python packaging、uv tool install、debugpy、pytest。

---

## 进度

- [x] 创建实施计划。
- [x] 写正式依赖和 adapter 默认行为测试。
- [x] 把 `debugpy` 加入 `[project].dependencies`。
- [x] 将默认 adapter 改为 `sys.executable -m debugpy.adapter`。
- [x] 更新 README 安装说明。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
