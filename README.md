# AI 工作流编排引擎

一个可视化的 AI 工作流编排引擎，支持 DAG 调度、LLM 节点、条件分支、并行执行。

## ✨ 特性

- 🎨 **可视化编排** — 拖拽式节点编辑
- 🔄 **DAG 调度** — 拓扑排序、并行执行
- 🤖 **LLM 节点** — 支持多种大模型
- ❓ **条件分支** — 表达式 / LLM 判断
- 💻 **代码节点** — 沙箱执行 Python 代码
- 📊 **执行追踪** — 节点状态、耗时、日志

## 🚀 快速开始

```bash
# 1. 启动服务
python api.py

# 2. 访问 Web UI
# http://localhost:8001

# 3. 查看 API 文档
# http://localhost:8001/docs
```

## 📖 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/workflows` | GET/POST | 工作流 CRUD |
| `/api/workflows/{id}` | GET/PUT/DELETE | 单个工作流操作 |
| `/api/workflows/{id}/run` | POST | 执行工作流 |
| `/api/workflows/{id}/run/stream` | POST | 流式执行（SSE） |
| `/api/executions` | GET | 执行记录列表 |
| `/api/templates` | GET | 工作流模板 |
| `/api/stats` | GET | 统计信息 |

## 🧩 节点类型

| 类型 | 说明 | 配置项 |
|------|------|--------|
| `start` | 开始节点 | - |
| `end` | 结束节点 | - |
| `llm` | LLM 调用 | system_prompt, user_prompt, model |
| `tool` | 工具调用 | tool_name, tool_arguments |
| `condition` | 条件判断 | condition_expression, condition_type |
| `code` | 代码执行 | code (Python) |
| `transform` | 数据转换 | code (Python) |

## 🔧 变量引用

在节点配置中可以使用 `{{变量引用}}` 语法：

- `{{inputs.key}}` — 引用工作流输入
- `{{variables.key}}` — 引用全局变量
- `{{node_id.output}}` — 引用某节点的输出

## 📝 工作流模板

内置 3 个模板：

1. **simple_llm** — 简单的 LLM 调用流程
2. **conditional_branch** — 条件分支流程
3. **parallel_tasks** — 并行任务执行

## 🏗️ 架构

```
用户层 (Web UI / API)
    ↓
API 服务层 (FastAPI)
    ↓
DAG 执行引擎
    ├── 拓扑排序
    ├── 并行调度
    ├── 状态管理
    └── 变量传递
    ↓
节点执行器
    ├── LLM 节点
    ├── 工具节点
    ├── 条件节点
    ├── 代码节点
    └── 转换节点
    ↓
存储层 (SQLite)
```

## 📄 License

MIT
