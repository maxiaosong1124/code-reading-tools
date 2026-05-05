# VS Code debugpy 示例验证实施计划

## 目标

为用户提供一个可以在 VS Code 中手动试用的 Python debugpy 示例，使用户可以验证：

- VS Code 正常调试 Python 示例代码。
- DAP 流量经过 `coderead proxy`。
- Step Over / Step Into / Continue 后生成 `events.jsonl`。
- `coderead graph` 可以从 trace 生成 `graph.json` 和 `graph.mmd`。

## 进度

- [x] 创建本实施计划。
- [x] 新增 `proxy-server` CLI，用于让 VS Code 通过 `debugServer` 连接 DAP proxy。
- [x] 为 `proxy-server` 添加自动化测试。
- [x] 新增最小 Python 示例项目。
- [x] 新增 VS Code `launch.json` 示例配置。
- [x] 新增中文试用文档。
- [x] 运行 pytest 和 compileall 验证。
- [x] 更新 README 中的下一步入口。

## 验证命令

```bash
rtk uv run pytest -q
rtk uv run python -m compileall src tests examples
```

## 手动验证范围

用户在 VS Code 中执行：

1. 启动 `coderead proxy-server`。
2. 选择示例 `launch.json` 中的配置。
3. 设置断点并调试 `examples/python_debuggee/app.py`。
4. 使用 Step Over / Step Into / Continue。
5. 检查 `.coderead-traces/.../events.jsonl`。
6. 执行 `coderead graph` 生成流程图。
