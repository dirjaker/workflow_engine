# 开发指南

> 本文档面向开发者，介绍如何搭建开发环境、理解项目架构以及参与贡献。

---

## 一、环境要求

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.11 | 推荐 3.12 |
| Conda | 最新 | 用于环境管理 |
| SQLite | ≥ 3.35 | 自带于 Python 标准库 |
| Node.js | 可选 | 如需前端开发 |

---

## 二、环境搭建

```bash
# 克隆仓库
git clone https://github.com/dirjaker/workflow_engine.git
cd workflow_engine

# 切换到 dev 分支
git checkout dev

# 创建并激活 Conda 环境
conda create -n workflow_engine python=3.12 -y
conda activate workflow_engine

# 安装依赖
pip install -r requirements.txt
```

---

## 三、启动服务

### 3.1 Web API 服务

```bash
python api.py
```

默认启动在 `http://0.0.0.0:8001`，包含完整的可视化编辑器和 API。

### 3.2 Web Dashboard（独立版）

```bash
python src/web/app.py
```

启动在 `http://0.0.0.0:8083`，提供独立的暗色主题仪表盘。

### 3.3 macOS 桌面应用

```bash
python src/macos/app.py
```

启动 tkinter 桌面 GUI。

### 3.4 macOS 打包

```bash
python packaging/py2app_setup.py py2app
```

---

## 四、项目架构

### 4.1 核心模块

```
┌──────────────────────────────────────────────────┐
│                   API 层                          │
│   api.py / src/web/app.py                        │
│   FastAPI 服务，提供 REST API + Web UI            │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│                执行引擎层                          │
│   dag_executor.py                                 │
│   DAGExecutor: 拓扑排序 → 并行调度 → 状态管理     │
│   ExecutionContext: 变量传递、插值                  │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│              节点执行器层                          │
│   node_executors.py                               │
│   7 种 NodeExecutor 子类                          │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│               数据层                              │
│   models.py     — Pydantic 数据模型                │
│   database.py   — SQLite 持久化                    │
└──────────────────────────────────────────────────┘
```

### 4.2 数据流

```
用户输入 → API 接收 → 加载工作流定义 → DAGExecutor.execute()
    → 验证（环检测、起止节点检查）
    → 拓扑排序（BFS 分层）
    → 按层执行（同层 asyncio.gather 并行）
    → 每个节点：解析输入 → 执行器处理 → 写入上下文
    → 收集输出 → 保存执行记录 → 返回结果
```

### 4.3 变量插值语法

在节点配置中使用 `{{}}` 引用变量：

| 语法 | 说明 | 示例 |
|------|------|------|
| `{{inputs.xxx}}` | 引用工作流输入参数 | `{{inputs.query}}` |
| `{{variables.xxx}}` | 引用全局变量 | `{{variables.api_key}}` |
| `{{node_id.output}}` | 引用上游节点输出 | `{{llm1.content}}` |

---

## 五、开发规范

### 5.1 代码风格

- 遵循 PEP 8 规范
- 使用类型注解（Type Hints）
- 模块、类、函数均需编写中文文档字符串
- Pydantic 模型使用 `BaseModel` 定义

### 5.2 提交规范

采用 Conventional Commits 格式：

```
<type>: <description>

feat: 新功能
fix: 修复
docs: 文档
refactor: 重构
chore: 杂务
```

### 5.3 分支策略

| 分支 | 用途 |
|------|------|
| `main` | 稳定发布版本 |
| `dev` | 开发分支 |
| `feature/*` | 功能分支 |

---

## 六、配置说明

配置文件 `config.yaml` 支持以下配置项：

```yaml
server:
  host: "0.0.0.0"     # 服务监听地址
  port: 8001           # 服务端口

database:
  path: "data/workflow.db"  # 数据库文件路径

agent:
  default_model: "deepseek-chat"  # 默认模型
  max_steps: 10                    # 最大步骤数
  temperature: 0.7                 # 模型温度
  max_tokens: 4096                 # 最大 Token 数
```

同时支持环境变量 `CORS_ORIGINS` 控制跨域访问来源，默认限制为本地访问。

---

## 七、内置模板

项目内置 3 个工作流模板，可通过 API 快速创建：

| 模板名称 | 说明 |
|----------|------|
| `simple_llm` | 简单 LLM 调用流程（开始 → LLM → 结束） |
| `conditional_branch` | 条件分支流程（根据文本长度选择不同处理路径） |
| `parallel_tasks` | 并行任务执行（同时执行情感分析、关键词提取、摘要生成） |

---

## 八、扩展节点

自定义节点执行器只需继承 `NodeExecutor` 基类：

```python
from dag_executor import NodeExecutor, ExecutionContext
from models import Node

class MyCustomExecutor(NodeExecutor):
    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        # 你的逻辑
        return {"result": "..."}
```

然后注册到执行器集合中：

```python
from models import NodeType

executors = create_default_executors()
executors[NodeType.YOUR_TYPE] = MyCustomExecutor()
```

---

## 九、相关文档

- [README](../README.md) — 项目总览
- [变更日志](CHANGELOG.md) — 版本历史
- [技术文档](../docs/技术文档.md) — 详细技术设计
- [代码审查报告](../REVIEW.md) — 安全和质量分析
