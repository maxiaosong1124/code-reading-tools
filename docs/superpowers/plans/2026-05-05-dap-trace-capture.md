# DAP Trace Capture 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按任务执行。本计划使用 checkbox (`- [ ]`) 跟踪进度。

**目标:** 让 Trace Proxy 不只转发 bytes，还能观察 DAP messages，在 `stopped` 后结合 `stackTrace` response 生成 `TraceEvent` 并写入 JSONL。

**架构:** 新增 `coderead.dap_capture` 作为协议状态机，负责解析 client-to-adapter commands、adapter-to-client events/responses、追踪 request seq 与 command 的关系，并在拿到 stack frames 后输出标准 `TraceEvent`。`proxy.py` 只负责双向转发和把 byte chunks 交给 capture observer，`cli.py` 负责创建 `TraceStore` 并把 capture 接入 proxy。

**Tech Stack:** Python 3.12 standard library、uv、pytest、DAP、JSONL。

---

## 执行规则

- 每完成一个 step，立即把本文件对应 checkbox 从 `[ ]` 改为 `[x]`。
- 每完成一个功能或 task，运行本计划中对应测试命令。
- Python 环境和命令统一使用 `uv`；验证命令使用 `rtk uv run ...`。
- 新增文档和面向用户说明使用中文；专业术语保留英文。
- 遵循 TDD：先写 failing test，再实现。

## 文件结构

- 创建 `src/coderead/dap_capture.py`：DAP trace capture 状态机。
- 修改 `src/coderead/proxy.py`：支持 capture observer 注入，保持 transparent forwarding。
- 修改 `src/coderead/cli.py`：`proxy` command 创建 `TraceStore` 并接入 DAP capture。
- 修改 `src/coderead/models.py`：补充 DAP frame 字段兼容逻辑。
- 创建 `tests/test_dap_capture.py`：DAP capture 状态机测试。
- 修改 `tests/test_cli.py`：覆盖 proxy command 的 store wiring。
- 修改 `README.md`：补充下一阶段 proxy 使用说明和限制。

## Task 1: DAP Capture 状态机

**Files:**
- Create: `tests/test_dap_capture.py`
- Create: `src/coderead/dap_capture.py`
- Modify: `src/coderead/models.py`

- [x] **Step 1: 编写 failing DAP capture tests**

创建 tests 覆盖：

- client `next` request 被记录为最近 command。
- adapter `stopped` event 后，capture 产生 `stackTrace` request bytes。
- adapter `stackTrace` response 到达后，capture 输出一个 `TraceEvent`。
- DAP frame 中 `source.path`、`name`、`line`、`column` 被转换为 `StackFrame`。

- [x] **Step 2: 运行 DAP capture tests 并确认失败**

Run: `rtk uv run pytest tests/test_dap_capture.py -q`

Expected: fails because `coderead.dap_capture` does not exist。

- [x] **Step 3: 实现 DAP capture 状态机**

实现：

- `DapTraceCapture`
- `observe_client_bytes(data: bytes) -> list[bytes]`
- `observe_adapter_bytes(data: bytes) -> list[bytes]`
- `pop_events() -> list[TraceEvent]`

`observe_adapter_bytes` 在收到 `stopped` event 后生成一个 DAP `stackTrace` request，response 到达后生成 `TraceEvent`。

- [x] **Step 4: 运行 DAP capture tests 并确认通过**

Run: `rtk uv run pytest tests/test_dap_capture.py -q`

Expected: all tests pass。

## Task 2: Proxy 接入 Capture

**Files:**
- Modify: `src/coderead/proxy.py`
- Create: `tests/test_proxy.py`

- [x] **Step 1: 编写 failing proxy observer tests**

创建 test 验证 `_pipe` 会把 observer 返回的 bytes 写到同一个 writer，用来支持 capture 注入 `stackTrace` request。

- [x] **Step 2: 运行 proxy tests 并确认失败**

Run: `rtk uv run pytest tests/test_proxy.py -q`

Expected: fails because `_pipe` currently ignores observer returned bytes。

- [x] **Step 3: 实现 observer injected bytes**

修改 `_pipe`：observer 可以返回 `bytes`、`list[bytes]` 或 awaitable，对这些返回 bytes 先写到同一个 writer，再写原始 chunk，保证 DAP request 能注入到 adapter 方向。

- [x] **Step 4: 运行 proxy tests 并确认通过**

Run: `rtk uv run pytest tests/test_proxy.py -q`

Expected: all tests pass。

## Task 3: CLI Proxy Store Wiring

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/coderead/cli.py`

- [x] **Step 1: 编写 failing CLI proxy wiring test**

创建 test 验证 `_create_proxy_capture` 或等价 helper 会创建 `TraceStore`，并在 capture 输出事件后 append 到 `events.jsonl`。

- [x] **Step 2: 运行 CLI tests 并确认失败**

Run: `rtk uv run pytest tests/test_cli.py -q`

Expected: fails because CLI proxy 尚未接入 `DapTraceCapture`。

- [x] **Step 3: 实现 CLI proxy capture wiring**

修改 `proxy` command：

- 创建 session directory。
- 构造 `DapTraceCapture`。
- 将 client/adapter observer 注入 `run_proxy`。
- observer 每次处理 DAP bytes 后 flush capture events 到 `TraceStore`。

- [x] **Step 4: 运行 CLI tests 并确认通过**

Run: `rtk uv run pytest tests/test_cli.py -q`

Expected: all tests pass。

## Task 4: 文档和完整验证

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-05-dap-trace-capture.md`

- [x] **Step 1: 更新 README**

补充 DAP capture 当前能力、proxy 使用方式和限制：当前先在协议层生成 trace events，真实 VS Code/debugpy 端到端验证是下一步。

- [x] **Step 2: 运行完整 tests**

Run: `rtk uv run pytest -q`

Expected: all tests pass。

- [x] **Step 3: 运行 compile check**

Run: `rtk uv run python -m compileall src tests`

Expected: compilation succeeds。

- [x] **Step 4: 检查 git status**

Run: `rtk git status --short`

Expected: only intended files are modified or added。

- [x] **Step 5: 提交 DAP trace capture**

Run:

```bash
git add .
git commit -m "feat: capture DAP stopped stack traces"
```

Expected: commit succeeds。
