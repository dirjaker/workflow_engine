# 代码审查报告 — Workflow Engine 项目

> 审查时间：2026-06-22 | 审查范围：Python 9 files
> 审查维度：安全漏洞 · 代码质量 · 依赖安全 · 配置问题 · 架构问题

---

## 🔴 致命问题

### S-01 | 远程代码执行（RCE）— `exec()` 直接执行用户代码
- **文件**：`node_executors.py:235,273`
- **描述**：`CodeNodeExecutor` 和 `TransformNodeExecutor` 使用 `exec()` 直接执行用户提交的 Python 代码。虽然限制了 `__builtins__`，但 **Python 沙箱可被轻易绕过**，例如通过 `().__class__.__bases__[0].__subclasses__()` 获取 `os` 模块实现任意命令执行。
- **影响**：任何能创建工作流的用户可获取服务器完全控制权。
- **建议**：(1) 使用容器/Docker 沙箱隔离代码执行；(2) 使用 RestrictedPython 或 PyPy sandbox；(3) 至少移除 `getattr`、`type`、`isinstance` 等可被利用的内置函数。

### S-02 | 远程代码执行 — `eval()` 条件表达式
- **文件**：`node_executors.py:179`
- **描述**：`ConditionNodeExecutor._eval_expression` 使用 `eval()` 执行条件表达式。提供的 `safe_builtins` 包含 `type`、`isinstance`、`hasattr`，均可被用于沙箱逃逸。
- **影响**：同 S-01，攻击者可通过条件节点执行任意代码。
- **建议**：使用安全的表达式引擎（如 `simpleeval` 库）或自定义 AST 解析器替代 `eval`。

### S-03 | 无任何认证/授权机制
- **文件**：`api.py`、`src/web/app.py`
- **描述**：所有 API 端点（创建/删除/执行工作流）完全无身份验证，任何人可访问。结合 S-01/S-02，意味着**任何人都能在服务器上执行任意代码**。
- **建议**：(1) 添加 API Key 或 JWT 认证中间件；(2) 至少在生产环境中要求认证。

### S-04 | CORS 允许所有来源
- **文件**：`api.py:24`、`src/web/app.py:26`
- **描述**：`allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]` 允许任何域名跨域访问所有 API，包括执行工作流。
- **建议**：限制为实际使用的前端域名。

---

## 🟡 警告问题

### W-01 | `await` 缺失 — 异步函数未正确调用
- **文件**：`src/web/app.py:113`、`src/macos/app.py:159`
- **描述**：`executor.execute(wf, inputs=req.inputs)` 是 `async def` 函数，但调用时未使用 `await`。这会返回一个协程对象而非执行结果，导致 API 返回错误数据。
- **建议**：添加 `await`：`result = await executor.execute(wf, inputs=req.inputs)`。

### W-02 | 27KB+ HTML 内嵌在 Python 文件中
- **文件**：`api.py:278-806`
- **描述**：整个 Web UI（HTML + CSS + JavaScript）以字符串形式硬编码在 `api.py` 中，超过 500 行。极难维护、无法利用前端工具链、无法独立测试。
- **建议**：提取为独立的 `static/index.html` 文件，通过 FastAPI 的 `StaticFiles` 或 `HTMLResponse` 加载。

### W-03 | 模块级数据库初始化
- **文件**：`api.py:19`、`src/web/app.py:32`
- **描述**：`db = WorkflowDatabase("data/workflow.db")` 在模块加载时执行，导致无法独立测试、无法配置数据库路径、多进程时可能冲突。
- **建议**：使用 FastAPI 的 lifespan 事件或 `Depends` 进行依赖注入。

### W-04 | 两个重复的 Web 应用入口
- **文件**：`api.py` vs `src/web/app.py`
- **描述**：两个文件都定义了 FastAPI app、CORS 中间件、工作流 CRUD 端点，存在大量重复代码。
- **建议**：统一为一个入口，或使用 FastAPI 的 `APIRouter` 拆分模块。

### W-05 | macOS 应用同步/异步不匹配
- **文件**：`src/macos/app.py:159`
- **描述**：`DAGExecutor.execute()` 是 `async` 函数，但在 tkinter 的同步上下文中直接调用，未使用 `asyncio.run()` 或事件循环。
- **建议**：使用 `asyncio.run()` 包装异步调用，或在单独线程中运行事件循环。

### W-06 | 依赖版本未锁定
- **文件**：`requirements.txt`
- **描述**：所有依赖使用 `>=` 最低版本约束，生产环境可能安装不兼容的版本。
- **建议**：生成锁定文件（`pip freeze > requirements.lock`）。

### W-07 | `sys.path.insert` 路径操作
- **文件**：`src/web/app.py:10`、`src/macos/app.py:12`
- **描述**：手动修改 `sys.path` 来解决导入问题，脆弱且不规范。
- **建议**：使用 `pyproject.toml` + `pip install -e .` 安装为可编辑包，或设置 `PYTHONPATH`。

### W-08 | 工作流定义验证不足
- **文件**：`dag_executor.py:286-301`
- **描述**：`_validate_workflow` 仅检查是否存在 start/end 节点和环，未验证：边引用的节点是否存在、节点类型是否合法、必要配置字段是否齐全。
- **建议**：增加节点引用完整性检查和配置字段校验。

---

## 🔵 建议改进

### A-01 | 添加请求超时和执行限制
- **描述**：虽然节点有 `timeout_seconds` 配置，但整个工作流的 `max_execution_time`（300s）未被实际使用。
- **建议**：在 `DAGExecutor.execute()` 中添加整体超时控制。

### A-02 | 添加执行结果持久化和重试日志
- **描述**：执行记录保存到数据库，但重试过程中的中间状态未记录。
- **建议**：记录每次重试的详细日志，便于调试。

### A-03 | 添加输入验证和清理
- **描述**：变量插值 (`interpolate`) 直接将用户输入替换到模板中，未做任何转义。
- **建议**：对插值结果进行适当的转义，防止注入攻击。

### A-04 | 配置外部化
- **描述**：数据库路径、端口号等硬编码在代码中。虽然有 `config.yaml`，但未被实际加载使用。
- **建议**：实现配置加载逻辑，从 `config.yaml` 或环境变量读取配置。

### A-05 | 添加单元测试
- **描述**：项目无任何测试代码。
- **建议**：为核心模块（`models.py`、`dag_executor.py`、`node_executors.py`）添加单元测试，特别是 DAG 拓扑排序和条件判断逻辑。

### A-06 | 增加日志记录
- **描述**：虽然导入了 `logging` 模块，但日志输出较少，关键操作（API 请求、工作流执行）缺少详细日志。
- **建议**：在 API 入口和执行关键节点添加结构化日志。

---

## 评分

| 维度 | 得分 | 说明 |
|------|------|------|
| 安全漏洞 | **1/10** | 3个 RCE 漏洞 + 无认证 + CORS 全开，最严重的组合 |
| 代码质量 | **6/10** | DAG 引擎设计优秀，模型定义规范，但存在 await 缺失和内嵌 HTML |
| 依赖安全 | **6/10** | 依赖合理，但版本未锁定 |
| 配置问题 | **5/10** | config.yaml 存在但未被使用，关键参数硬编码 |
| 架构问题 | **6/10** | 模块职责清晰（models/dag/executors），但入口重复、缺少测试 |

### 综合评分：**4.8 / 10** — 安全问题极其严重，必须修复后方可部署
