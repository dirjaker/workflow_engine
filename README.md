<div align="center">

<img src="assets/banner.svg" width="100%" alt="AI 工作流编排引擎">

<br>

### ⚙️ AI 工作流编排引擎

[![Stars](https://img.shields.io/github/stars/dirjaker/workflow_engine?style=flat-square&label=Stars&color=FFD700)](https://github.com/dirjaker/workflow_engine/stargazers)
[![Forks](https://img.shields.io/github/forks/dirjaker/workflow_engine?style=flat-square&label=Forks&color=4A90D9)](https://github.com/dirjaker/workflow_engine/network/members)
[![Contributors](https://img.shields.io/github/contributors/dirjaker/workflow_engine?style=flat-square&label=Contributors&color=8B4513)](https://github.com/dirjaker/workflow_engine/graphs/contributors)
[![License](https://img.shields.io/github/license/dirjaker/workflow_engine?style=flat-square&label=License&color=20B2AA)](https://github.com/dirjaker/workflow_engine/blob/dev/LICENSE)

</div>

---

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 📊 **DAG 调度** | 有向无环图结构的任务依赖管理 |
| 🎨 **可视化编辑器** | 拖拽式工作流设计界面 |
| 🧩 **7 种节点** | 开始、结束、任务、条件、并行、循环、子流程 |
| 🔀 **条件分支** | 基于表达式的动态分支路由 |
| ⚡ **并行执行** | 支持任务并行和扇出/扇入模式 |
| 📋 **执行历史** | 完整的执行记录和日志追踪 |


## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/dirjaker/workflow_engine.git
cd workflow_engine

# 创建虚拟环境
conda create -n workflow_engine python=3.12 -y
conda activate workflow_engine

# 安装依赖
pip install -r requirements.txt

# 运行项目
python main.py
```

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | FastAPI, SQLAlchemy |
| **前端** | Vue.js, LogicFlow |
| **调度** | Python, asyncio |
| **数据库** | SQLite |

## 📝 开发日志

- [x] DAG 调度引擎
- [x] 可视化编辑器
- [x] 7 种节点类型
- [x] 条件分支
- [x] 并行执行
- [ ] 定时触发器
- [ ] Webhook 触发
- [ ] 分布式执行

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

🔗 **GitHub**: [dirjaker/workflow_engine](https://github.com/dirjaker/workflow_engine)

⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！

</div>
