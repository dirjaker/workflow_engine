"""FastAPI Web 服务 — 工作流编排引擎 API"""

import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import WorkflowDefinition, ExecutionRecord, NodeType
from database import WorkflowDatabase
from dag_executor import DAGExecutor
from node_executors import create_default_executors

logger = logging.getLogger(__name__)

# 初始化
db = WorkflowDatabase("data/workflow.db")
executors = create_default_executors()  # 无模型客户端，使用模拟模式
executor = DAGExecutor(executors)

app = FastAPI(title="AI 工作流编排引擎", version="1.0.0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class RunRequest(BaseModel):
    inputs: dict = {}


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ==================== 工作流 CRUD ====================

@app.post("/api/workflows")
async def create_workflow(workflow: WorkflowDefinition):
    """创建工作流"""
    workflow.created_at = datetime.now()
    workflow.updated_at = datetime.now()
    db.save_workflow(workflow)
    return {"id": workflow.id, "name": workflow.name}


@app.get("/api/workflows")
async def list_workflows():
    """列出所有工作流"""
    return db.list_workflows()


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, "工作流不存在")
    return workflow.model_dump()


@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow: WorkflowDefinition):
    """更新工作流"""
    existing = db.get_workflow(workflow_id)
    if not existing:
        raise HTTPException(404, "工作流不存在")

    workflow.id = workflow_id
    workflow.updated_at = datetime.now()
    workflow.version = existing.version + 1
    db.save_workflow(workflow)
    return {"id": workflow.id, "version": workflow.version}


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    if not db.delete_workflow(workflow_id):
        raise HTTPException(404, "工作流不存在")
    return {"status": "deleted"}


# ==================== 工作流执行 ====================

@app.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: RunRequest = RunRequest()):
    """同步执行工作流"""
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, "工作流不存在")

    record = await executor.execute(workflow, request.inputs)
    db.save_execution(record)

    return record.model_dump()


@app.post("/api/workflows/{workflow_id}/run/stream")
async def run_workflow_stream(workflow_id: str, request: RunRequest = RunRequest()):
    """流式执行工作流（SSE）"""
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, "工作流不存在")

    async def event_generator():
        record = None
        async for event in executor.execute_stream(workflow, request.inputs):
            data = json.dumps(event, ensure_ascii=False, default=str)
            yield f"data: {data}\n\n"

            # 保存最终记录
            if event.get("type") == "workflow_complete":
                record = ExecutionRecord(
                    workflow_id=workflow.id,
                    workflow_version=workflow.version,
                    status=event.get("status", "failed"),
                    inputs=request.inputs,
                    outputs=event.get("outputs", {}),
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    duration_ms=event.get("duration_ms", 0),
                )
                db.save_execution(record)

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==================== 执行记录 ====================

@app.get("/api/executions")
async def list_executions(workflow_id: str = None):
    """列出执行记录"""
    return db.list_executions(workflow_id)


@app.get("/api/executions/{execution_id}")
async def get_execution(execution_id: str):
    """获取执行详情"""
    record = db.get_execution(execution_id)
    if not record:
        raise HTTPException(404, "执行记录不存在")
    return record.model_dump()


# ==================== 统计 ====================

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return db.get_stats()


# ==================== 模板 ====================

@app.get("/api/templates")
async def list_templates():
    """列出工作流模板"""
    return get_templates()


@app.post("/api/workflows/from-template/{template_name}")
async def create_from_template(template_name: str):
    """从模板创建工作流"""
    templates = {t["name"]: t for t in get_templates()}
    if template_name not in templates:
        raise HTTPException(404, f"模板 '{template_name}' 不存在")

    template = templates[template_name]
    workflow = WorkflowDefinition(**template["definition"])
    workflow.created_at = datetime.now()
    workflow.updated_at = datetime.now()
    db.save_workflow(workflow)

    return {"id": workflow.id, "name": workflow.name}


def get_templates() -> list[dict]:
    """内置工作流模板"""
    return [
        {
            "name": "simple_llm",
            "description": "简单的 LLM 调用流程",
            "definition": {
                "name": "简单 LLM 调用",
                "description": "接收输入 → 调用 LLM → 返回结果",
                "nodes": [
                    {"id": "start", "type": "start", "name": "开始", "position": {"x": 100, "y": 200}},
                    {"id": "llm", "type": "llm", "name": "LLM 处理", "position": {"x": 300, "y": 200},
                     "config": {"system_prompt": "你是一个有用的助手", "user_prompt": "{{inputs.query}}"}},
                    {"id": "end", "type": "end", "name": "结束", "position": {"x": 500, "y": 200}},
                ],
                "edges": [
                    {"source_node_id": "start", "target_node_id": "llm"},
                    {"source_node_id": "llm", "target_node_id": "end"},
                ],
            },
        },
        {
            "name": "conditional_branch",
            "description": "条件分支流程",
            "definition": {
                "name": "条件分支",
                "description": "根据条件选择不同的处理路径",
                "nodes": [
                    {"id": "start", "type": "start", "name": "开始", "position": {"x": 100, "y": 200}},
                    {"id": "condition", "type": "condition", "name": "判断", "position": {"x": 300, "y": 200},
                     "config": {"condition_type": "expression", "condition_expression": "len(inputs.get('text', '')) > 100"}},
                    {"id": "llm_long", "type": "llm", "name": "处理长文本", "position": {"x": 500, "y": 100},
                     "config": {"system_prompt": "请总结以下长文本", "user_prompt": "{{inputs.text}}"}},
                    {"id": "llm_short", "type": "llm", "name": "处理短文本", "position": {"x": 500, "y": 300},
                     "config": {"system_prompt": "请扩展以下短文本", "user_prompt": "{{inputs.text}}"}},
                    {"id": "end", "type": "end", "name": "结束", "position": {"x": 700, "y": 200}},
                ],
                "edges": [
                    {"source_node_id": "start", "target_node_id": "condition"},
                    {"source_node_id": "condition", "target_node_id": "llm_long", "type": "true"},
                    {"source_node_id": "condition", "target_node_id": "llm_short", "type": "false"},
                    {"source_node_id": "llm_long", "target_node_id": "end"},
                    {"source_node_id": "llm_short", "target_node_id": "end"},
                ],
            },
        },
        {
            "name": "parallel_tasks",
            "description": "并行任务执行",
            "definition": {
                "name": "并行任务",
                "description": "同时执行多个独立任务",
                "nodes": [
                    {"id": "start", "type": "start", "name": "开始", "position": {"x": 100, "y": 200}},
                    {"id": "task1", "type": "llm", "name": "任务1", "position": {"x": 300, "y": 100},
                     "config": {"system_prompt": "分析情感", "user_prompt": "{{inputs.text}}"}},
                    {"id": "task2", "type": "llm", "name": "任务2", "position": {"x": 300, "y": 200},
                     "config": {"system_prompt": "提取关键词", "user_prompt": "{{inputs.text}}"}},
                    {"id": "task3", "type": "llm", "name": "任务3", "position": {"x": 300, "y": 300},
                     "config": {"system_prompt": "生成摘要", "user_prompt": "{{inputs.text}}"}},
                    {"id": "end", "type": "end", "name": "结束", "position": {"x": 500, "y": 200}},
                ],
                "edges": [
                    {"source_node_id": "start", "target_node_id": "task1"},
                    {"source_node_id": "start", "target_node_id": "task2"},
                    {"source_node_id": "start", "target_node_id": "task3"},
                    {"source_node_id": "task1", "target_node_id": "end"},
                    {"source_node_id": "task2", "target_node_id": "end"},
                    {"source_node_id": "task3", "target_node_id": "end"},
                ],
            },
        },
    ]


# ==================== Web UI ====================

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Web 可视化编辑器"""
    return HTML_PAGE


def run_server(host: str = "0.0.0.0", port: int = 8001):
    """启动服务"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 AI 工作流编排引擎...")
    print("📎 访问 http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")


# ==================== 内嵌 HTML ====================

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 工作流编排引擎</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #0f0f0f; --surface: #1a1a1a; --border: #2a2a2a;
  --text: #e0e0e0; --text2: #888; --accent: #4a9eff;
  --green: #4caf50; --red: #f44336; --yellow: #ffc107;
  --purple: #9c27b0;
}
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; }

/* 侧边栏 */
.sidebar { width: 280px; background: var(--surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
.sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
.sidebar-header h2 { font-size: 16px; color: var(--accent); margin-bottom: 10px; }
.btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; transition: opacity 0.2s; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-success { background: var(--green); color: #fff; }
.btn:hover { opacity: 0.9; }
.btn-block { width: 100%; }
.workflow-list { flex: 1; overflow-y: auto; padding: 8px; }
.workflow-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px; font-size: 13px; }
.workflow-item:hover { background: var(--border); }
.workflow-item.active { background: var(--accent); color: #fff; }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text2); }

/* 主区域 */
.main { flex: 1; display: flex; flex-direction: column; }
.toolbar { padding: 12px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; }
.canvas-container { flex: 1; position: relative; overflow: hidden; }
canvas { width: 100%; height: 100%; }

/* 节点面板 */
.node-palette { position: absolute; top: 10px; left: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; width: 160px; }
.node-palette h3 { font-size: 13px; margin-bottom: 8px; color: var(--accent); }
.palette-item { padding: 6px 10px; margin: 4px 0; background: var(--border); border-radius: 4px; cursor: grab; font-size: 12px; text-align: center; }
.palette-item:hover { background: var(--accent); color: #fff; }

/* 属性面板 */
.properties-panel { position: absolute; top: 10px; right: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; width: 300px; max-height: 80vh; overflow-y: auto; display: none; }
.properties-panel.visible { display: block; }
.properties-panel h3 { font-size: 14px; margin-bottom: 12px; color: var(--accent); }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: var(--text2); margin-bottom: 4px; }
.form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-size: 13px; }
.form-group textarea { min-height: 80px; resize: vertical; }

/* 日志面板 */
.log-panel { position: absolute; bottom: 10px; left: 10px; right: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; max-height: 200px; overflow-y: auto; font-size: 12px; font-family: monospace; }
.log-entry { padding: 4px 0; border-bottom: 1px solid var(--border); }
.log-entry.success { color: var(--green); }
.log-entry.error { color: var(--red); }
.log-entry.info { color: var(--accent); }

/* 节点样式 */
.node { position: absolute; background: var(--surface); border: 2px solid var(--border); border-radius: 8px; padding: 10px; min-width: 120px; cursor: move; user-select: none; }
.node.selected { border-color: var(--accent); }
.node-header { font-size: 12px; font-weight: bold; margin-bottom: 4px; }
.node-type { font-size: 10px; color: var(--text2); }
.node-port { width: 10px; height: 10px; background: var(--border); border-radius: 50%; position: absolute; cursor: crosshair; }
.node-port.input { left: -5px; top: 50%; transform: translateY(-50%); }
.node-port.output { right: -5px; top: 50%; transform: translateY(-50%); }
.node-port:hover { background: var(--accent); }

/* 状态颜色 */
.node.running { border-color: var(--yellow); }
.node.success { border-color: var(--green); }
.node.failed { border-color: var(--red); }
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <h2>🔄 工作流编排引擎</h2>
    <button class="btn btn-primary btn-block" onclick="createWorkflow()">+ 新建工作流</button>
  </div>
  <div class="workflow-list" id="workflow-list"></div>
  <div class="sidebar-footer" id="stats">加载中...</div>
</div>

<div class="main">
  <div class="toolbar">
    <span id="workflow-name" style="font-weight:bold;">选择或创建工作流</span>
    <span style="flex:1"></span>
    <button class="btn btn-success" onclick="runWorkflow()" id="run-btn" disabled>▶ 运行</button>
    <button class="btn btn-primary" onclick="saveWorkflow()" id="save-btn" disabled>💾 保存</button>
  </div>
  <div class="canvas-container" id="canvas-container">
    <canvas id="canvas"></canvas>

    <div class="node-palette">
      <h3>节点类型</h3>
      <div class="palette-item" draggable="true" data-type="start">🟢 开始</div>
      <div class="palette-item" draggable="true" data-type="end">🔴 结束</div>
      <div class="palette-item" draggable="true" data-type="llm">🤖 LLM</div>
      <div class="palette-item" draggable="true" data-type="tool">🔧 工具</div>
      <div class="palette-item" draggable="true" data-type="condition">❓ 条件</div>
      <div class="palette-item" draggable="true" data-type="code">💻 代码</div>
      <div class="palette-item" draggable="true" data-type="transform">🔄 转换</div>
    </div>

    <div class="properties-panel" id="properties-panel">
      <h3>节点属性</h3>
      <div id="properties-content"></div>
      <button class="btn btn-primary btn-block" onclick="applyProperties()" style="margin-top:12px;">应用</button>
    </div>

    <div class="log-panel" id="log-panel"></div>
  </div>
</div>

<script>
const API = '';
let workflows = [];
let currentWorkflow = null;
let nodes = [];
let edges = [];
let selectedNode = null;
let draggingNode = null;
let dragOffset = { x: 0, y: 0 };
let connectingFrom = null;

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

// 节点颜色
const nodeColors = {
  start: '#4caf50',
  end: '#f44336',
  llm: '#4a9eff',
  tool: '#ff9800',
  condition: '#9c27b0',
  code: '#607d8b',
  transform: '#00bcd4',
};

// 初始化
async function init() {
  await loadWorkflows();
  await loadStats();
  resizeCanvas();
  setupEventListeners();
}

function resizeCanvas() {
  const container = document.getElementById('canvas-container');
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  draw();
}

function setupEventListeners() {
  window.addEventListener('resize', resizeCanvas);

  canvas.addEventListener('mousedown', onMouseDown);
  canvas.addEventListener('mousemove', onMouseMove);
  canvas.addEventListener('mouseup', onMouseUp);

  // 拖拽添加节点
  document.querySelectorAll('.palette-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      e.dataTransfer.setData('nodeType', item.dataset.type);
    });
  });

  canvas.addEventListener('dragover', e => e.preventDefault());
  canvas.addEventListener('drop', onDrop);
}

async function loadWorkflows() {
  const res = await fetch(API + '/api/workflows');
  workflows = await res.json();
  renderWorkflowList();
}

function renderWorkflowList() {
  const el = document.getElementById('workflow-list');
  el.innerHTML = workflows.map(w =>
    `<div class="workflow-item ${currentWorkflow?.id===w.id?'active':''}" onclick="selectWorkflow('${w.id}')">${w.name}</div>`
  ).join('');
}

async function selectWorkflow(id) {
  const res = await fetch(API + '/api/workflows/' + id);
  currentWorkflow = await res.json();
  nodes = currentWorkflow.nodes || [];
  edges = currentWorkflow.edges || [];
  document.getElementById('workflow-name').textContent = currentWorkflow.name;
  document.getElementById('run-btn').disabled = false;
  document.getElementById('save-btn').disabled = false;
  renderWorkflowList();
  draw();
}

async function createWorkflow() {
  const name = prompt('工作流名称:', '新工作流');
  if (!name) return;

  const workflow = {
    name: name,
    description: '',
    nodes: [
      { id: 'start', type: 'start', name: '开始', position: { x: 100, y: 200 } },
      { id: 'end', type: 'end', name: '结束', position: { x: 500, y: 200 } },
    ],
    edges: [],
  };

  const res = await fetch(API + '/api/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(workflow),
  });
  const data = await res.json();
  await loadWorkflows();
  await selectWorkflow(data.id);
}

async function saveWorkflow() {
  if (!currentWorkflow) return;

  currentWorkflow.nodes = nodes;
  currentWorkflow.edges = edges;

  await fetch(API + '/api/workflows/' + currentWorkflow.id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(currentWorkflow),
  });

  addLog('工作流已保存', 'success');
}

async function runWorkflow() {
  if (!currentWorkflow) return;

  addLog('开始执行工作流...', 'info');

  const res = await fetch(API + '/api/workflows/' + currentWorkflow.id + '/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: {} }),
  });
  const record = await res.json();

  // 更新节点状态
  for (const [nodeId, exec] of Object.entries(record.node_executions || {})) {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      node._status = exec.status;
    }
  }
  draw();

  if (record.status === 'success') {
    addLog(`工作流执行成功 (${record.duration_ms.toFixed(0)}ms)`, 'success');
  } else {
    addLog(`工作流执行失败: ${JSON.stringify(record.outputs)}`, 'error');
  }
}

// ==================== 画布绘制 ====================

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 绘制网格
  drawGrid();

  // 绘制边
  edges.forEach(edge => drawEdge(edge));

  // 绘制节点
  nodes.forEach(node => drawNode(node));
}

function drawGrid() {
  ctx.strokeStyle = '#1a1a1a';
  ctx.lineWidth = 1;
  const gridSize = 20;

  for (let x = 0; x < canvas.width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
}

function drawNode(node) {
  const x = node.position.x;
  const y = node.position.y;
  const w = 120;
  const h = 50;

  // 背景
  ctx.fillStyle = node === selectedNode ? '#2a2a3a' : '#1a1a2a';
  ctx.strokeStyle = nodeColors[node.type] || '#4a9eff';
  ctx.lineWidth = node === selectedNode ? 3 : 2;

  // 状态颜色覆盖
  if (node._status === 'running') ctx.strokeStyle = '#ffc107';
  if (node._status === 'success') ctx.strokeStyle = '#4caf50';
  if (node._status === 'failed') ctx.strokeStyle = '#f44336';

  ctx.beginPath();
  ctx.roundRect(x, y, w, h, 8);
  ctx.fill();
  ctx.stroke();

  // 标题
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 12px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(node.name, x + w/2, y + 20);

  // 类型
  ctx.fillStyle = '#888';
  ctx.font = '10px sans-serif';
  ctx.fillText(node.type, x + w/2, y + 38);

  // 端口
  ctx.fillStyle = '#4a9eff';
  ctx.beginPath();
  ctx.arc(x, y + h/2, 5, 0, Math.PI * 2);
  ctx.fill();

  ctx.beginPath();
  ctx.arc(x + w, y + h/2, 5, 0, Math.PI * 2);
  ctx.fill();
}

function drawEdge(edge) {
  const source = nodes.find(n => n.id === edge.source_node_id);
  const target = nodes.find(n => n.id === edge.target_node_id);
  if (!source || !target) return;

  const sx = source.position.x + 120;
  const sy = source.position.y + 25;
  const tx = target.position.x;
  const ty = target.position.y + 25;

  ctx.strokeStyle = edge.type === 'true' ? '#4caf50' : edge.type === 'false' ? '#f44336' : '#4a9eff';
  ctx.lineWidth = 2;
  ctx.setLineDash(edge.type === 'error' ? [5, 5] : []);

  ctx.beginPath();
  ctx.moveTo(sx, sy);
  ctx.bezierCurveTo(sx + 50, sy, tx - 50, ty, tx, ty);
  ctx.stroke();
  ctx.setLineDash([]);

  // 箭头
  const angle = Math.atan2(ty - sy, tx - sx);
  ctx.fillStyle = ctx.strokeStyle;
  ctx.beginPath();
  ctx.moveTo(tx, ty);
  ctx.lineTo(tx - 10 * Math.cos(angle - 0.3), ty - 10 * Math.sin(angle - 0.3));
  ctx.lineTo(tx - 10 * Math.cos(angle + 0.3), ty - 10 * Math.sin(angle + 0.3));
  ctx.fill();
}

// ==================== 交互 ====================

function onMouseDown(e) {
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  // 检查是否点击了节点
  selectedNode = null;
  for (const node of nodes) {
    if (x >= node.position.x && x <= node.position.x + 120 &&
        y >= node.position.y && y <= node.position.y + 50) {
      selectedNode = node;
      draggingNode = node;
      dragOffset = { x: x - node.position.x, y: y - node.position.y };
      break;
    }
  }

  draw();
  showProperties(selectedNode);
}

function onMouseMove(e) {
  if (!draggingNode) return;

  const rect = canvas.getBoundingClientRect();
  draggingNode.position.x = e.clientX - rect.left - dragOffset.x;
  draggingNode.position.y = e.clientY - rect.top - dragOffset.y;
  draw();
}

function onMouseUp(e) {
  draggingNode = null;
}

function onDrop(e) {
  e.preventDefault();
  const type = e.dataTransfer.getData('nodeType');
  if (!type) return;

  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  const node = {
    id: 'node_' + Date.now(),
    type: type,
    name: type.toUpperCase(),
    position: { x, y },
    config: {},
  };

  nodes.push(node);
  draw();
}

function showProperties(node) {
  const panel = document.getElementById('properties-panel');
  const content = document.getElementById('properties-content');

  if (!node) {
    panel.classList.remove('visible');
    return;
  }

  panel.classList.add('visible');

  let html = `
    <div class="form-group">
      <label>名称</label>
      <input id="prop-name" value="${node.name}">
    </div>
    <div class="form-group">
      <label>类型</label>
      <input value="${node.type}" disabled>
    </div>
  `;

  if (node.type === 'llm') {
    html += `
      <div class="form-group">
        <label>系统提示</label>
        <textarea id="prop-system-prompt">${node.config?.system_prompt || ''}</textarea>
      </div>
      <div class="form-group">
        <label>用户提示</label>
        <textarea id="prop-user-prompt">${node.config?.user_prompt || ''}</textarea>
      </div>
    `;
  }

  if (node.type === 'condition') {
    html += `
      <div class="form-group">
        <label>条件表达式</label>
        <input id="prop-condition" value="${node.config?.condition_expression || ''}">
      </div>
    `;
  }

  if (node.type === 'code') {
    html += `
      <div class="form-group">
        <label>代码</label>
        <textarea id="prop-code" style="min-height:120px">${node.config?.code || ''}</textarea>
      </div>
    `;
  }

  content.innerHTML = html;
}

function applyProperties() {
  if (!selectedNode) return;

  const name = document.getElementById('prop-name')?.value;
  if (name) selectedNode.name = name;

  if (selectedNode.type === 'llm') {
    selectedNode.config = selectedNode.config || {};
    selectedNode.config.system_prompt = document.getElementById('prop-system-prompt')?.value;
    selectedNode.config.user_prompt = document.getElementById('prop-user-prompt')?.value;
  }

  if (selectedNode.type === 'condition') {
    selectedNode.config = selectedNode.config || {};
    selectedNode.config.condition_expression = document.getElementById('prop-condition')?.value;
  }

  if (selectedNode.type === 'code') {
    selectedNode.config = selectedNode.config || {};
    selectedNode.config.code = document.getElementById('prop-code')?.value;
  }

  draw();
  addLog(`节点 "${selectedNode.name}" 属性已更新`, 'info');
}

function addLog(message, type = 'info') {
  const panel = document.getElementById('log-panel');
  const time = new Date().toLocaleTimeString();
  panel.innerHTML += `<div class="log-entry ${type}">[${time}] ${message}</div>`;
  panel.scrollTop = panel.scrollHeight;
}

async function loadStats() {
  const res = await fetch(API + '/api/stats');
  const s = await res.json();
  document.getElementById('stats').textContent = `工作流: ${s.workflows} | 执行: ${s.executions} | 成功率: ${s.success_rate}`;
}

init();
</script>
</body>
</html>"""
