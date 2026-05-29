"""工作流数据模型定义"""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


# ========== 节点类型定义 ==========

class NodeType(str, Enum):
    """节点类型"""
    START = "start"              # 开始节点
    END = "end"                  # 结束节点
    LLM = "llm"                  # LLM 调用
    TOOL = "tool"                # 工具调用
    CONDITION = "condition"      # 条件判断
    CODE = "code"                # 代码执行
    TRANSFORM = "transform"      # 数据转换


class NodeStatus(str, Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class EdgeType(str, Enum):
    """边类型"""
    NORMAL = "normal"            # 普通连接
    CONDITIONAL_TRUE = "true"    # 条件为真
    CONDITIONAL_FALSE = "false"  # 条件为假
    ERROR = "error"              # 错误分支


# ========== 节点定义 ==========

class Position(BaseModel):
    """节点在画布上的位置"""
    x: float
    y: float


class NodeConfig(BaseModel):
    """节点配置"""
    # LLM 节点
    model: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    response_format: str | None = None  # "json" | "text"

    # 工具节点
    tool_name: str | None = None
    tool_arguments: dict = {}

    # 条件节点
    condition_type: str = "expression"   # "expression" | "llm_judge"
    condition_expression: str | None = None
    condition_prompt: str | None = None

    # 代码节点
    code: str | None = None
    timeout: int = 30

    # 通用
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout_seconds: int = 60


class Node(BaseModel):
    """工作流节点"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: NodeType
    name: str
    description: str = ""
    position: Position
    config: NodeConfig = NodeConfig()


class Edge(BaseModel):
    """节点之间的连接"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_node_id: str
    source_port: str = "output"
    target_node_id: str
    target_port: str = "input"
    type: EdgeType = EdgeType.NORMAL
    label: str = ""


# ========== 工作流定义 ==========

class WorkflowDefinition(BaseModel):
    """工作流定义"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    version: int = 1
    nodes: list[Node]
    edges: list[Edge]

    # 全局变量
    variables: dict[str, Any] = {}

    # 触发方式
    trigger_type: str = "manual"  # "manual" | "api"

    # 全局配置
    max_execution_time: int = 300
    error_strategy: str = "fail_fast"  # "fail_fast" | "continue"

    # 元数据
    author: str = ""
    tags: list[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ========== 执行记录 ==========

class NodeExecution(BaseModel):
    """单个节点的执行记录"""
    node_id: str
    status: NodeStatus
    inputs: dict = {}
    outputs: dict = {}
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0
    tokens_used: int = 0
    retry_count: int = 0


class ExecutionRecord(BaseModel):
    """工作流执行记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    workflow_version: int
    status: NodeStatus = NodeStatus.PENDING
    inputs: dict = {}
    outputs: dict = {}

    # 节点执行记录
    node_executions: dict[str, NodeExecution] = {}

    # 时间线
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0

    # 统计
    total_tokens: int = 0
    nodes_succeeded: int = 0
    nodes_failed: int = 0
