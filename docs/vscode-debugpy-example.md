# VS Code debugpy 示例试用说明

这个示例用于手动验证：你仍然在 VS Code 里正常使用 debugpy 调试，`coderead proxy-server` 在中间自动记录调试停下来的调用链路。

## 1. 启动 proxy-server

在仓库根目录执行：

```bash
uv run coderead proxy-server \
  --host 127.0.0.1 \
  --port 47111 \
  --out-dir .coderead-traces \
  --scenario "验证 normalize_numbers 奇偶分支" \
  --real-adapter python -m debugpy.adapter
```

保持这个 terminal 不要关闭。启动后会看到类似信息：

```text
coderead proxy-server listening on 127.0.0.1:47111
```

当 VS Code 连接进来后，还会在 stderr 打印本次 trace session directory，例如：

```text
.coderead-traces/sess_xxxxxxxxxxxx
```

## 2. 用 VS Code 打开示例目录

打开目录：

```text
examples/python_debuggee
```

示例目录已经包含 `.vscode/launch.json`，里面的关键配置是：

```json
"debugServer": 47111
```

这个配置会让 VS Code 连接本地 `coderead proxy-server`，再由 proxy-server 转发到真实 `debugpy.adapter`。

## 3. 手动调试

建议断点位置：

- `app.py` 的 `main()` 里 `normalized = normalize_numbers(raw_values)` 这一行。
- `normalize_numbers()` 里的 `if value % 2 == 0:` 这一行。
- `summarize()` 里的 `total += value` 这一行。

然后在 VS Code 里选择：

```text
CodeRead: Python debugpy 示例
```

开始调试后，尝试：

- Continue
- Step Over
- Step Into
- Step Out

每次程序停下来后，proxy 会尝试获取当前 `stackTrace` 并写入 `events.jsonl`。

## 4. 检查 trace

回到仓库根目录，查看最近生成的 session：

```bash
find .coderead-traces -maxdepth 2 -type f
```

你应该能看到类似：

```text
.coderead-traces/sess_xxxxxxxxxxxx/session.json
.coderead-traces/sess_xxxxxxxxxxxx/events.jsonl
```

查看事件：

```bash
sed -n '1,20p' .coderead-traces/sess_xxxxxxxxxxxx/events.jsonl
```

把 `sess_xxxxxxxxxxxx` 替换成实际生成的 session 目录。

## 5. 生成流程图和回顾笔记

默认生成更适合源码回顾的 trace-level 阅读图。它会过滤 Python runtime frame 和 module wrapper，隐藏单线程 `thread` label，把调用边显示为更容易阅读的 `call` / `return`。主线节点保持在外层，step into 的函数会用独立 `subgraph` 表达子流程；子流程框内默认展示源码行 summary，并标注 `loop`、`branch`、`return`，不画内部 step/loop 回边。Mermaid 图默认不显示 hit count，减少视觉噪声：

```bash
uv run coderead graph \
  --events .coderead-traces/sess_xxxxxxxxxxxx/events.jsonl \
  --out-dir .coderead-traces/sess_xxxxxxxxxxxx \
  --scenario "验证 normalize_numbers 奇偶分支"
```

生成文件：

- `trace.html`
- `graph.json`
- `graph.mmd`
- `trace.md`

建议优先打开 `trace.html`，它是离线静态页面：左侧显示 Overview 主流程，点击子函数后右侧显示 Subflow 子流程。`trace.md` 保留文字索引，`graph.mmd` 可以继续用于单独 Mermaid 预览。

如果你想查看函数聚合图，可以显式生成 function-level 图：

```bash
uv run coderead graph \
  --events .coderead-traces/sess_xxxxxxxxxxxx/events.jsonl \
  --out-dir .coderead-traces/sess_xxxxxxxxxxxx \
  --view function
```

如果你想查看每一次 debug stop 的逐行细节，可以显式生成 line-level 图：

```bash
uv run coderead graph \
  --events .coderead-traces/sess_xxxxxxxxxxxx/events.jsonl \
  --out-dir .coderead-traces/sess_xxxxxxxxxxxx \
  --view line
```

## 当前已知限制

- 这是手动验证用例，还不是 VS Code extension。
- 当前记录的是 DAP `stopped` 后的 stack frames，不记录 variables。
- 当前 graph 是根据真实停靠点推导流程，不做完整 static control-flow analysis。
- 如果真实 VS Code/debugpy 对 proxy 注入的 `stackTrace` request 有兼容问题，后续会改成监听 VS Code 自身发出的 `stackTrace` response 或实现更完整的 request multiplexing。
