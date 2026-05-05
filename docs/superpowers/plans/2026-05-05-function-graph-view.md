# Function Graph View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将默认流程图从 line-level debug stop 图改为更清爽的 function-level 阅读图，并保留 `--view line` 查看原始细节。

**Architecture:** 在 `coderead.graph` 中新增 function-level graph builder，按 `function + file` 聚合节点、过滤 Python runtime 栈、压缩连续重复停靠点。`coderead graph` CLI 增加 `--view function|line`，默认 `function`，输出仍复用 `graph.json` 和 `graph.mmd`。

**Tech Stack:** Python 3.12+、argparse、pytest、Mermaid。

---

## 文件结构

- 修改 `src/coderead/graph.py`：新增 `GraphView` 选择和 function-level graph 构建逻辑。
- 修改 `src/coderead/cli.py`：为 `graph` command 增加 `--view` 参数，默认 `function`。
- 修改 `src/coderead/mermaid.py`：让 function-level 节点显示更适合阅读的行范围和 hit count。
- 修改 `tests/test_graph.py`：覆盖 function-level 聚合、runtime 过滤、line view 保留。
- 修改 `tests/test_cli.py`：覆盖 CLI 默认 view 和 `--view line`。
- 修改 `README.md`、`docs/vscode-debugpy-example.md`：更新渲染说明。

## 进度

- [x] 创建实施计划。
- [x] 写 function-level graph failing tests。
- [x] 运行测试确认 RED。
- [x] 实现 function-level graph。
- [x] 运行 graph tests 确认 GREEN。
- [x] 写 CLI view failing tests。
- [x] 运行测试确认 RED。
- [x] 实现 CLI `--view function|line`。
- [x] 更新 Mermaid label 和文档。
- [x] 运行全量 pytest 和 compileall。
- [x] 更新本计划最终状态。

## 验证命令

```bash
uv run pytest tests/test_graph.py -q
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
