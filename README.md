<div align="center">

# ⚙️ Workflow Engine

### DAG 工作流编排引擎

[![节点](https://img.shields.io/badge/节点-6-blue?style=flat-square)]()
[![API](https://img.shields.io/badge/API-5-green?style=flat-square)]()
[![框架](https://img.shields.io/badge/框架-FastAPI-orange?style=flat-square)]()
[![更新](https://img.shields.io/badge/更新-2025.06-red?style=flat-square)]()

*DAG 依赖编排 · 节点并行执行 · 变量传递 · 断点恢复 · Web 监控*

</div>

---

# AI 工作流编排引擎

> 基于 DAG 的可视化 AI 工作流编排引擎，支持拖拽式编辑、多节点类型、并行调度与实时执行追踪。

---

## 项目概览

| 项目 | 说明 |
|------|------|
| 项目名称 | AI 工作流编排引擎 (Workflow Engine) |
| 核心能力 | DAG 调度、可视化编排、执行追踪 |
| 节点类型 | 7 种：Start / End / LLM / Code / HTTP / Condition / Parallel |
| 后端框架 | FastAPI (Python) |
| 前端框架 | Vue 3 + TypeScript |
| 数据存储 | SQLite |
| 协议 | MIT License |

---

## 功能特性

### 可视化编排

- 拖拽式节点编辑器，所见即所得
- 节点间连线构建 DAG 拓扑关系
- 支持画布缩放、平移、对齐等操作
- 节点配置面板，可视化设置参数

### DAG 调度引擎

- 拓扑排序自动解析节点执行顺序
- 循环依赖检测与报错
- 并行分支自动并发执行
- 条件分支动态路由

### 执行追踪

- 节点级执行状态实时更新（等待 / 运行中 / 成功 / 失败）
- 每个节点的输入输出日志记录
- 执行耗时统计
- 支持流式执行（SSE），实时推送进度

### 节点能力

- **LLM 节点**：支持多种大语言模型，可配置 system prompt、user prompt、模型参数
- **Code 节点**：沙箱执行 Python 代码，用于数据处理与自定义逻辑
- **HTTP 节点**：调用外部 API 接口
- **Condition 节点**：基于表达式或 LLM 判断进行条件分支
- **Parallel 节点**：并行执行多个下游分支

### 模板系统

内置多个工作流模板，开箱即用：

| 模板名称 | 说明 |
|----------|------|
| `simple_llm` | 简单的 LLM 调用流程 |
| `conditional_branch` | 条件分支流程 |
| `parallel_tasks` | 并行任务执行 |

---

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| FastAPI | Web 框架，提供 REST API |
| SQLite | 轻量级本地数据库 |
| Uvicorn | ASGI 服务器 |
| Pydantic | 数据校验与序列化 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3 | 前端框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Vue Flow | DAG 可视化编辑器 |
| Pinia | 状态管理 |

---

## 系统架构

整体采用前后端分离架构，分为四层：

**用户交互层**

提供 Web UI 和 REST API 两种接入方式。Web UI 基于 Vue 3 构建，包含工作流编辑器和执行监控面板。

**API 服务层**

FastAPI 提供 RESTful 接口，处理工作流的增删改查、执行触发、状态查询等请求。

**DAG 执行引擎**

核心调度模块，负责拓扑排序、并行调度、状态管理和变量传递。引擎将工作流 DAG 解析为可执行计划，按拓扑顺序驱动各节点执行器。

**节点执行器**

各类型节点的执行逻辑实现，包括 LLM 调用、代码沙箱、HTTP 请求、条件判断和并行分发。

**存储层**

SQLite 存储工作流定义、执行记录和节点日志。

| 层级 | 职责 | 技术 |
|------|------|------|
| 用户交互层 | 可视化编辑、执行监控 | Vue 3, Vue Flow |
| API 服务层 | REST 接口、请求处理 | FastAPI |
| DAG 执行引擎 | 拓扑排序、并行调度、变量传递 | Python |
| 节点执行器 | LLM / Code / HTTP / Condition / Parallel | Python |
| 存储层 | 工作流定义、执行记录持久化 | SQLite |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 pnpm

### 后端启动

```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动服务
python api.py
```

服务默认运行在 `http://localhost:8001`。

### 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:5173`。

### 访问

| 地址 | 说明 |
|------|------|
| `http://localhost:8001/docs` | API 文档（Swagger UI） |
| `http://localhost:8001/redoc` | API 文档（ReDoc） |
| `http://localhost:5173` | Web UI |

---

## API 接口

### 工作流管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/workflows` | GET | 获取工作流列表 |
| `/api/workflows` | POST | 创建工作流 |
| `/api/workflows/{id}` | GET | 获取单个工作流详情 |
| `/api/workflows/{id}` | PUT | 更新工作流 |
| `/api/workflows/{id}` | DELETE | 删除工作流 |

### 执行相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/workflows/{id}/run` | POST | 执行工作流 |
| `/api/workflows/{id}/run/stream` | POST | 流式执行（SSE） |
| `/api/executions` | GET | 执行记录列表 |
| `/api/executions/{id}` | GET | 执行记录详情 |

### 其他

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/templates` | GET | 获取工作流模板列表 |
| `/api/stats` | GET | 获取统计信息 |

---

## 节点类型

| 节点类型 | 类型标识 | 说明 | 主要配置项 |
|----------|----------|------|------------|
| 开始节点 | `start` | 工作流入口，定义输入参数 | 输入参数定义 |
| 结束节点 | `end` | 工作流出口，汇总输出结果 | 输出变量映射 |
| LLM 节点 | `llm` | 调用大语言模型 | `model`, `system_prompt`, `user_prompt`, `temperature` |
| 代码节点 | `code` | 沙箱执行 Python 代码 | `code`（Python 脚本） |
| HTTP 节点 | `http` | 调用外部 HTTP 接口 | `method`, `url`, `headers`, `body` |
| 条件节点 | `condition` | 条件分支判断 | `condition_type`, `condition_expression` |
| 并行节点 | `parallel` | 并行执行多个下游分支 | 并行分支定义 |

### 变量引用语法

在节点配置中可使用 `{{变量引用}}` 语法引用上下文数据：

| 语法 | 说明 | 示例 |
|------|------|------|
| `{{inputs.key}}` | 引用工作流输入参数 | `{{inputs.user_query}}` |
| `{{variables.key}}` | 引用全局变量 | `{{variables.api_key}}` |
| `{{node_id.output}}` | 引用某节点的输出 | `{{llm_1.output}}` |

---

## 项目结构

```
workflow_engine/
├── backend/                    # 后端服务
│   ├── api.py                  # FastAPI 入口
│   ├── engine/                 # DAG 执行引擎
│   │   ├── dag.py              # DAG 解析与拓扑排序
│   │   ├── scheduler.py        # 调度器
│   │   ├── executor.py         # 执行引擎主逻辑
│   │   └── variable.py         # 变量管理
│   ├── nodes/                  # 节点执行器
│   │   ├── base.py             # 节点基类
│   │   ├── llm_node.py         # LLM 节点
│   │   ├── code_node.py        # 代码节点
│   │   ├── http_node.py        # HTTP 节点
│   │   ├── condition_node.py   # 条件节点
│   │   └── parallel_node.py    # 并行节点
│   ├── models/                 # 数据模型
│   │   ├── workflow.py         # 工作流模型
│   │   └── execution.py        # 执行记录模型
│   ├── database.py             # SQLite 数据库连接
│   ├── templates/              # 工作流模板
│   └── requirements.txt        # Python 依赖
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── views/              # 页面组件
│   │   │   ├── Editor.vue      # 工作流编辑器
│   │   │   ├── Executions.vue  # 执行记录页
│   │   │   └── Dashboard.vue   # 仪表盘
│   │   ├── components/         # 通用组件
│   │   │   ├── nodes/          # 节点组件
│   │   │   ├── panels/         # 配置面板
│   │   │   └── toolbar/        # 工具栏
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── api/                # API 请求封装
│   │   └── types/              # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

## License

MIT


---

## Web 仪表盘

独立的暗色主题仪表盘，管理工作流和执行。

### 启动

```bash
python src/web/app.py
# 访问 http://localhost:8083
```

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/workflows` | GET | 列出所有工作流 |
| `/api/workflows` | POST | 创建工作流 |
| `/api/workflows/{id}` | GET | 获取工作流详情 |
| `/api/workflows/{id}` | DELETE | 删除工作流 |
| `/api/workflows/{id}/run` | POST | 执行工作流 |
| `/api/templates` | GET | 获取模板列表 |
| `/api/stats` | GET | 系统统计 |

### 仪表盘功能

- 系统概览与节点类型展示
- 工作流的创建、查看、删除
- 一键执行工作流
- 模板浏览

---

## macOS 应用

### tkinter 桌面版

```bash
python src/macos/app.py
```

### py2app 打包

```bash
# 在 macOS 上执行
python packaging/py2app_setup.py py2app
# 产物位于 dist/Workflow Engine.app
```
