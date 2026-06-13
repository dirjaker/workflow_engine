"""
Workflow Engine Web Dashboard
==============================
FastAPI 服务，提供工作流管理的暗色主题仪表盘
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from database import WorkflowDatabase
from dag_executor import DAGExecutor
from node_executors import create_default_executors
from models import WorkflowDefinition, NodeType

app = FastAPI(title="Workflow Engine Dashboard", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 初始化
db = WorkflowDatabase("data/dashboard.db")
executors = create_default_executors()
executor = DAGExecutor(executors)


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []


class RunRequest(BaseModel):
    inputs: Dict[str, Any] = {}


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/stats")
async def stats():
    """获取系统统计"""
    workflows = db.list_workflows()
    return {
        "workflows": len(workflows),
        "node_types": [t.value for t in NodeType],
    }


@app.get("/api/workflows")
async def list_workflows():
    """列出所有工作流"""
    return db.list_workflows()


@app.post("/api/workflows")
async def create_workflow(req: WorkflowCreateRequest):
    """创建简单工作流"""
    wf = WorkflowDefinition(
        name=req.name,
        description=req.description,
        nodes=[],
        edges=[],
    )
    wf.created_at = datetime.now()
    wf.updated_at = datetime.now()
    db.save_workflow(wf)
    return {"id": wf.id, "name": wf.name}


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "工作流不存在")
    return wf.model_dump() if hasattr(wf, "model_dump") else wf


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    db.delete_workflow(workflow_id)
    return {"status": "ok"}


@app.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: RunRequest = RunRequest()):
    """执行工作流"""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "工作流不存在")
    result = executor.execute(wf, inputs=req.inputs)
    if isinstance(result, dict):
        return result
    return {"result": str(result)}


@app.get("/api/templates")
async def list_templates():
    """获取模板列表"""
    try:
        from templates import get_templates
        return get_templates()
    except ImportError:
        return {"templates": [
            {"name": "simple_llm", "description": "简单 LLM 调用流程"},
            {"name": "conditional_branch", "description": "条件分支流程"},
            {"name": "parallel_tasks", "description": "并行任务执行"},
        ]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
