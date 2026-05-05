# Debug Flow Trace MVP 实施计划

> **给 agentic workers:** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`，或使用 `superpowers:executing-plans` 按任务执行。本计划使用 checkbox (`- [ ]`) 跟踪进度。

**目标:** 构建一个可运行的 MVP：能标准化 debugger stop events，写入 JSONL，推导 flow graph，导出 Mermaid，并提供最小 DAP proxy 入口。

**架构:** MVP 是一个名为 `coderead` 的 Python package。先实现可离线测试的 trace core，再实现 DAP framing 和 proxy forwarding 薄层，后续再接入 VS Code。CUDA metadata 先作为 optional metadata 保留，真实 cuda-gdb enrichment 放到后续阶段。

**Tech Stack:** Python 3.12 standard library、uv、pytest、JSONL、Mermaid flowchart output。

---

## 执行规则

- 每完成一个 step，立即把本文件对应 checkbox 从 `[ ]` 改为 `[x]`。
- 每完成一个功能或 task，运行本计划中对应测试命令。
- 测试失败时先修复并重新验证，不跳过失败结果。
- Python 环境和命令统一使用 `uv`；验证命令使用 `rtk uv run ...`。
- 所有新增文档和面向用户说明使用中文；专业术语保留英文。
- 当前仓库已初始化 git；提交时使用清晰的中文或英文 conventional commit message。

## 文件结构

- 创建 `pyproject.toml`：package metadata、uv dev dependency group、pytest 配置、console script。
- 创建 `src/coderead/__init__.py`：package version。
- 创建 `src/coderead/models.py`：source location、trace event、graph node、graph edge dataclasses。
- 创建 `src/coderead/store.py`：session directory 创建和 JSONL event writer。
- 创建 `src/coderead/graph.py`：trace events 到 flow graph 的 inference。
- 创建 `src/coderead/mermaid.py`：Mermaid flowchart renderer。
- 创建 `src/coderead/dap.py`：DAP `Content-Length` framing parser/writer。
- 创建 `src/coderead/proxy.py`：最小 async transparent DAP proxy。
- 创建 `src/coderead/cli.py`：`coderead trace`、`coderead graph`、`coderead proxy` commands。
- 创建 `tests/test_graph.py`：graph inference tests。
- 创建 `tests/test_store.py`：JSONL store tests。
- 创建 `tests/test_dap.py`：DAP framing tests。
- 创建 `tests/test_cli.py`：CLI graph command test。
- 创建 `README.md`：MVP 使用方式和当前范围。

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/coderead/__init__.py`
- Create: `README.md`

- [x] **Step 1: 添加 project metadata**

创建 `pyproject.toml`，使用 setuptools package，配置 uv dev dependency group、pytest path，并添加 `coderead` console script 指向 `coderead.cli:main`。

- [x] **Step 2: 添加 package init**

创建 `src/coderead/__init__.py`，内容包含 `__version__ = "0.1.0"`。

- [x] **Step 3: 添加 README**

创建 `README.md`，说明当前 MVP：offline graph generation 和 experimental DAP proxy。

- [x] **Step 4: 验证 package import**

Run: `rtk uv run python -m compileall src`

Expected: compilation succeeds。

## Task 2: Trace Models And Graph Inference

**Files:**
- Create: `tests/test_graph.py`
- Create: `src/coderead/models.py`
- Create: `src/coderead/graph.py`

- [x] **Step 1: 编写 failing graph tests**

创建 tests 覆盖 linear flow、branch inference、repeated edge counts、loop detection、function enter、function return、thread switch annotations。

- [x] **Step 2: 运行 graph tests 并确认失败**

Run: `rtk uv run pytest tests/test_graph.py -q`

Expected: fails because `coderead.models` or `coderead.graph` does not exist。

- [x] **Step 3: 实现 models 和 graph inference**

实现 dataclasses：

- `SourceLocation`
- `StackFrame`
- `TraceEvent`
- `FlowNode`
- `FlowEdge`
- `FlowGraph`

实现 `build_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph`。

- [x] **Step 4: 运行 graph tests 并确认通过**

Run: `rtk uv run pytest tests/test_graph.py -q`

Expected: all tests pass。

## Task 3: Store And Mermaid Export

**Files:**
- Create: `tests/test_store.py`
- Modify: `src/coderead/models.py`
- Create: `src/coderead/store.py`
- Create: `src/coderead/mermaid.py`

- [x] **Step 1: 编写 failing store 和 Mermaid tests**

创建 tests 覆盖写入 `session.json`、append `events.jsonl`、读取 events、以及把 repeated edges 渲染为 `xN`。

- [x] **Step 2: 运行 tests 并确认失败**

Run: `rtk uv run pytest tests/test_store.py tests/test_graph.py -q`

Expected: store 和 Mermaid imports fail。

- [x] **Step 3: 实现 store 和 Mermaid renderer**

实现 `TraceStore`、`load_events_jsonl(path)`、`dump_graph_json(graph, path)`、`render_mermaid(graph)`。

- [x] **Step 4: 运行 tests 并确认通过**

Run: `rtk uv run pytest tests/test_store.py tests/test_graph.py -q`

Expected: all tests pass。

## Task 4: DAP Framing

**Files:**
- Create: `tests/test_dap.py`
- Create: `src/coderead/dap.py`

- [x] **Step 1: 编写 failing DAP tests**

创建 tests 覆盖 DAP message encoding、解析一个完整 framed message、以及解析分 chunk 到达的多个 framed messages。

- [x] **Step 2: 运行 DAP tests 并确认失败**

Run: `rtk uv run pytest tests/test_dap.py -q`

Expected: fails because `coderead.dap` does not exist。

- [x] **Step 3: 实现 DAP framing**

实现 `encode_message(message: dict) -> bytes` 和 `DapMessageBuffer.feed(data: bytes) -> list[dict]`。

- [x] **Step 4: 运行 DAP tests 并确认通过**

Run: `rtk uv run pytest tests/test_dap.py -q`

Expected: all tests pass。

## Task 5: CLI And Proxy

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/coderead/cli.py`
- Create: `src/coderead/proxy.py`

- [x] **Step 1: 编写 failing CLI test**

创建 test：写入 sample `events.jsonl`，运行 `coderead graph`，验证 `graph.json` 和 `graph.mmd` 被创建。

- [x] **Step 2: 运行 CLI test 并确认失败**

Run: `rtk uv run pytest tests/test_cli.py -q`

Expected: fails because `coderead.cli` does not exist。

- [x] **Step 3: 实现 CLI**

实现：

- `coderead graph --events EVENTS --out-dir OUT_DIR`
- `coderead trace --out-dir OUT_DIR`
- `coderead proxy --real-adapter COMMAND... --out-dir OUT_DIR`

`trace` 创建空 session directory 并打印路径。`proxy` 暴露 command shape 并调用 proxy 实现。

- [x] **Step 4: 实现 proxy**

实现可 import 和后续测试的 transparent subprocess-based proxy function。它负责转发 stdin/stdout bytes，并接收 optional observer callbacks，用于观察 VS Code-to-adapter 和 adapter-to-VS Code byte chunks。

- [x] **Step 5: 运行 CLI test 并确认通过**

Run: `rtk uv run pytest tests/test_cli.py -q`

Expected: all tests pass。

## Task 6: Final Verification

**Files:**
- Modify as needed only if verification exposes defects。

- [x] **Step 1: 运行完整 test suite**

Run: `rtk uv run pytest -q`

Expected: all tests pass。

- [x] **Step 2: 运行 compile check**

Run: `rtk uv run python -m compileall src tests`

Expected: compilation succeeds。

- [x] **Step 3: 检查 git status**

Run: `rtk git status --short`

Expected: only intended files are modified or added。

- [ ] **Step 4: 提交 MVP**

Run:

```bash
git add .
git commit -m "feat: add debug flow trace MVP"
```

Expected: commit succeeds。
