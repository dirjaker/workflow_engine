"""DAG 执行引擎 — 核心调度器"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import AsyncIterator

from models import (
    WorkflowDefinition, ExecutionRecord, NodeExecution,
    NodeType, NodeStatus, EdgeType, Node
)

logger = logging.getLogger(__name__)


class ExecutionContext:
    """执行上下文 — 管理工作流执行过程中的状态"""

    def __init__(
        self,
        workflow: WorkflowDefinition,
        record: ExecutionRecord,
        variables: dict,
    ):
        self.workflow = workflow
        self.record = record
        self.variables = variables
        self._node_outputs: dict[str, dict] = {}
        self.should_stop = False
        self.execution_order = []

    def set_node_output(self, node_id: str, output: dict):
        """设置节点输出"""
        self._node_outputs[node_id] = output

    def get_node_output(self, node_id: str) -> dict | None:
        """获取节点输出"""
        return self._node_outputs.get(node_id)

    def set_variable(self, key: str, value: Any):
        """设置变量"""
        self.variables[key] = value

    def get_outputs(self) -> dict:
        """获取最终输出（结束节点的输入）"""
        end_nodes = [n for n in self.workflow.nodes if n.type == NodeType.END]
        outputs = {}
        for end_node in end_nodes:
            for edge in self.workflow.edges:
                if edge.target_node_id == end_node.id:
                    source_output = self.get_node_output(edge.source_node_id)
                    if source_output:
                        outputs.update(source_output)
        return outputs

    def interpolate(self, text: str) -> str:
        """变量插值"""
        import re
        pattern = r"\{\{(.+?)\}\}"

        def replacer(match):
            ref = match.group(1).strip()
            parts = ref.split(".")

            if parts[0] == "inputs":
                return str(self.variables.get(parts[1], ""))
            elif parts[0] == "variables":
                return str(self.variables.get(parts[1], ""))
            elif len(parts) >= 2:
                # node_id.output.field
                node_output = self.get_node_output(parts[0])
                if node_output:
                    if len(parts) == 2:
                        return str(node_output)
                    else:
                        current = node_output
                        for part in parts[1:]:
                            if isinstance(current, dict):
                                current = current.get(part, "")
                            else:
                                return str(current)
                        return str(current)

            return match.group(0)  # 无法解析时保持原样

        return re.sub(pattern, replacer, text)


class NodeExecutor:
    """节点执行器基类"""

    async def execute(
        self,
        node: Node,
        inputs: dict,
        context: ExecutionContext,
    ) -> dict:
        raise NotImplementedError


class DAGExecutor:
    """
    DAG 执行引擎

    核心职责：
    1. 拓扑排序：确定节点执行顺序
    2. 并行调度：无依赖的节点并行执行
    3. 状态管理：跟踪每个节点的执行状态
    4. 变量传递：上游输出 → 下游输入
    5. 错误处理：重试、降级
    """

    def __init__(self, node_executors: dict[NodeType, NodeExecutor]):
        self.executors = node_executors

    async def execute(
        self,
        workflow: WorkflowDefinition,
        inputs: dict = None,
    ) -> ExecutionRecord:
        """执行工作流"""
        # 创建执行记录
        record = ExecutionRecord(
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            inputs=inputs or {},
            started_at=datetime.now(),
        )

        # 构建执行上下文
        context = ExecutionContext(
            workflow=workflow,
            record=record,
            variables={**workflow.variables, **(inputs or {})},
        )

        try:
            # 1. 验证
            errors = self._validate_workflow(workflow)
            if errors:
                raise ValueError(f"工作流验证失败: {errors}")

            # 2. 构建依赖图
            graph = self._build_graph(workflow)

            # 3. 拓扑排序
            execution_order = self._topological_sort(graph, workflow)
            context.execution_order = execution_order

            # 4. 按层级执行
            record.status = NodeStatus.RUNNING

            for layer in execution_order:
                # 同一层的节点可以并行执行
                tasks = []
                node_ids = []
                for node_id in layer:
                    node = next((n for n in workflow.nodes if n.id == node_id), None)
                    if node:
                        tasks.append(self._execute_node(node, context))
                        node_ids.append(node_id)

                # 并行执行
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                for node_id, result in zip(node_ids, results):
                    if isinstance(result, Exception):
                        # 节点执行失败
                        exec_record = record.node_executions.get(node_id)
                        if exec_record:
                            exec_record.status = NodeStatus.FAILED
                            exec_record.error = str(result)
                        record.nodes_failed += 1

                        if workflow.error_strategy == "fail_fast":
                            raise result
                    else:
                        record.nodes_succeeded += 1

                # 检查是否需要停止
                if context.should_stop:
                    break

            # 5. 收集输出
            record.status = NodeStatus.SUCCESS if record.nodes_failed == 0 else NodeStatus.FAILED
            record.outputs = context.get_outputs()

        except Exception as e:
            record.status = NodeStatus.FAILED
            record.outputs = {"error": str(e)}
            logger.error(f"工作流执行失败: {e}")

        finally:
            record.completed_at = datetime.now()
            record.duration_ms = (record.completed_at - record.started_at).total_seconds() * 1000

        return record

    async def execute_stream(
        self,
        workflow: WorkflowDefinition,
        inputs: dict = None,
    ) -> AsyncIterator[dict]:
        """流式执行工作流 — 返回每个节点的状态更新"""
        record = ExecutionRecord(
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            inputs=inputs or {},
            started_at=datetime.now(),
        )

        context = ExecutionContext(
            workflow=workflow,
            record=record,
            variables={**workflow.variables, **(inputs or {})},
        )

        try:
            errors = self._validate_workflow(workflow)
            if errors:
                raise ValueError(f"工作流验证失败: {errors}")

            graph = self._build_graph(workflow)
            execution_order = self._topological_sort(graph, workflow)
            context.execution_order = execution_order

            record.status = NodeStatus.RUNNING
            yield {"type": "workflow_start", "workflow_id": workflow.id}

            for layer_idx, layer in enumerate(execution_order):
                yield {"type": "layer_start", "layer": layer_idx, "nodes": layer}

                tasks = []
                node_ids = []
                for node_id in layer:
                    node = next((n for n in workflow.nodes if n.id == node_id), None)
                    if node:
                        tasks.append(self._execute_node(node, context))
                        node_ids.append(node_id)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for node_id, result in zip(node_ids, results):
                    if isinstance(result, Exception):
                        yield {
                            "type": "node_complete",
                            "node_id": node_id,
                            "status": "failed",
                            "error": str(result),
                        }
                        record.nodes_failed += 1
                        if workflow.error_strategy == "fail_fast":
                            raise result
                    else:
                        yield {
                            "type": "node_complete",
                            "node_id": node_id,
                            "status": "success",
                            "outputs": result,
                        }
                        record.nodes_succeeded += 1

                yield {"type": "layer_complete", "layer": layer_idx}

            record.status = NodeStatus.SUCCESS if record.nodes_failed == 0 else NodeStatus.FAILED
            record.outputs = context.get_outputs()

        except Exception as e:
            record.status = NodeStatus.FAILED
            record.outputs = {"error": str(e)}
            yield {"type": "error", "error": str(e)}

        finally:
            record.completed_at = datetime.now()
            record.duration_ms = (record.completed_at - record.started_at).total_seconds() * 1000
            yield {
                "type": "workflow_complete",
                "status": record.status.value,
                "duration_ms": record.duration_ms,
                "outputs": record.outputs,
            }

    def _validate_workflow(self, workflow: WorkflowDefinition) -> list[str]:
        """验证工作流"""
        errors = []

        # 检查是否有开始和结束节点
        node_types = {n.type for n in workflow.nodes}
        if NodeType.START not in node_types:
            errors.append("缺少开始节点")
        if NodeType.END not in node_types:
            errors.append("缺少结束节点")

        # 检查是否有环
        if self._has_cycle(workflow):
            errors.append("工作流存在循环依赖")

        return errors

    def _has_cycle(self, workflow: WorkflowDefinition) -> bool:
        """检测是否有环（DFS）"""
        graph = defaultdict(list)
        for edge in workflow.edges:
            graph[edge.source_node_id].append(edge.target_node_id)

        visited = set()
        rec_stack = set()

        def dfs(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbor in graph[node_id]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        return any(dfs(n.id) for n in workflow.nodes if n.id not in visited)

    def _build_graph(self, workflow: WorkflowDefinition) -> dict[str, list[str]]:
        """构建邻接表"""
        graph = defaultdict(list)
        for edge in workflow.edges:
            graph[edge.source_node_id].append(edge.target_node_id)
        return graph

    def _topological_sort(
        self,
        graph: dict[str, list[str]],
        workflow: WorkflowDefinition,
    ) -> list[list[str]]:
        """拓扑排序 → 返回按层级分组的执行顺序"""
        # 计算入度
        in_degree = defaultdict(int)
        all_nodes = {n.id for n in workflow.nodes}
        for node_id in all_nodes:
            in_degree[node_id] = 0
        for edges_from in graph.values():
            for target in edges_from:
                in_degree[target] += 1

        # BFS 分层
        layers = []
        queue = deque([node_id for node_id, deg in in_degree.items() if deg == 0])

        while queue:
            layer = []
            for _ in range(len(queue)):
                node_id = queue.popleft()
                layer.append(node_id)
                for neighbor in graph[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            if layer:
                layers.append(layer)

        return layers

    async def _execute_node(self, node: Node, context: ExecutionContext):
        """执行单个节点"""
        executor = self.executors.get(node.type)
        if not executor:
            raise ValueError(f"未找到节点类型 {node.type} 的执行器")

        # 记录开始
        execution = NodeExecution(
            node_id=node.id,
            status=NodeStatus.RUNNING,
            started_at=datetime.now(),
        )
        context.record.node_executions[node.id] = execution

        try:
            # 解析输入变量
            inputs = self._resolve_inputs(node, context)

            # 带重试的执行
            for attempt in range(node.config.retry_count + 1):
                try:
                    result = await asyncio.wait_for(
                        executor.execute(node, inputs, context),
                        timeout=node.config.timeout_seconds,
                    )
                    execution.retry_count = attempt
                    break
                except asyncio.TimeoutError:
                    if attempt < node.config.retry_count:
                        await asyncio.sleep(node.config.retry_delay * (attempt + 1))
                        continue
                    raise
                except Exception as e:
                    if attempt < node.config.retry_count:
                        await asyncio.sleep(node.config.retry_delay * (attempt + 1))
                        continue
                    raise

            # 记录成功
            execution.status = NodeStatus.SUCCESS
            execution.outputs = result
            execution.completed_at = datetime.now()
            execution.duration_ms = (
                execution.completed_at - execution.started_at
            ).total_seconds() * 1000

            # 将输出写入上下文
            context.set_node_output(node.id, result)

            return result

        except Exception as e:
            execution.status = NodeStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()
            execution.duration_ms = (
                execution.completed_at - execution.started_at
            ).total_seconds() * 1000
            raise

    def _resolve_inputs(self, node: Node, context: ExecutionContext) -> dict:
        """解析节点输入变量"""
        inputs = {}

        # 从连接的边获取输入
        for edge in context.workflow.edges:
            if edge.target_node_id == node.id:
                source_output = context.get_node_output(edge.source_node_id)
                if source_output:
                    inputs[edge.target_port] = source_output.get(edge.source_port, source_output)

        # 从配置中解析变量引用
        for key, value in node.config.model_dump().items():
            if isinstance(value, str) and "{{" in value:
                inputs[key] = context.interpolate(value)
            else:
                inputs[key] = value

        return inputs
