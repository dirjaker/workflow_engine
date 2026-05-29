"""节点执行器 — 各类节点的具体执行逻辑"""

import json
import re
import logging
from datetime import datetime

from models import Node, NodeType, NodeStatus
from dag_executor import NodeExecutor, ExecutionContext

logger = logging.getLogger(__name__)


class StartNodeExecutor(NodeExecutor):
    """开始节点执行器"""

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        logger.info(f"工作流开始: {context.workflow.name}")
        return {"status": "started", "inputs": context.variables}


class EndNodeExecutor(NodeExecutor):
    """结束节点执行器"""

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        logger.info(f"工作流结束: {context.workflow.name}")
        context.should_stop = True
        return {"status": "completed", "outputs": inputs}


class LLMNodeExecutor(NodeExecutor):
    """
    LLM 节点执行器

    功能：
    - 调用大模型生成文本
    - 支持结构化输出（JSON）
    """

    def __init__(self, model_client=None):
        self.model = model_client

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        config = node.config

        # 如果没有模型客户端，返回模拟结果
        if not self.model:
            logger.warning("未配置模型客户端，返回模拟结果")
            return {
                "content": f"[模拟] LLM 节点 '{node.name}' 执行完成",
                "model": "mock",
                "tokens_used": 0,
            }

        # 构建消息
        messages = []
        if config.system_prompt:
            system_prompt = context.interpolate(config.system_prompt)
            messages.append({"role": "system", "content": system_prompt})

        user_prompt = context.interpolate(config.user_prompt or "")
        messages.append({"role": "user", "content": user_prompt})

        # 调用模型
        response = await self.model.chat(
            messages=messages,
            model=config.model or "deepseek-chat",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        content = response.get("content", "")

        # 如果需要 JSON 输出
        if config.response_format == "json":
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                # 尝试提取 JSON 块
                json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if json_match:
                    content = json.loads(json_match.group(1))
                else:
                    content = {"raw": content, "parse_error": "无法解析为 JSON"}

        # 记录 token 使用
        tokens = response.get("usage", {}).get("total_tokens", 0)
        context.record.total_tokens += tokens
        exec_record = context.record.node_executions.get(node.id)
        if exec_record:
            exec_record.tokens_used = tokens

        return {"content": content, "model": response.get("model", "")}


class ToolNodeExecutor(NodeExecutor):
    """工具调用节点执行器"""

    def __init__(self, tool_registry=None):
        self.tools = tool_registry

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        config = node.config
        tool_name = config.tool_name

        if not tool_name:
            raise ValueError("工具节点未配置 tool_name")

        # 变量插值到参数中
        resolved_args = {}
        for key, value in config.tool_arguments.items():
            if isinstance(value, str) and "{{" in value:
                resolved_args[key] = context.interpolate(value)
            else:
                resolved_args[key] = value

        # 如果没有工具注册表，返回模拟结果
        if not self.tools:
            logger.warning("未配置工具注册表，返回模拟结果")
            return {
                "success": True,
                "data": f"[模拟] 工具 '{tool_name}' 执行完成",
                "arguments": resolved_args,
            }

        # 执行工具
        result = await self.tools.execute(tool_name, resolved_args)

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }


class ConditionNodeExecutor(NodeExecutor):
    """
    条件节点执行器

    支持两种条件类型：
    1. expression: Python 表达式
    2. llm_judge: 用 LLM 判断
    """

    def __init__(self, model_client=None):
        self.model = model_client

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        config = node.config
        condition_type = config.condition_type

        if condition_type == "expression":
            result = self._eval_expression(config.condition_expression, inputs, context)
        elif condition_type == "llm_judge":
            result = await self._eval_llm(config.condition_prompt, inputs, context)
        else:
            raise ValueError(f"不支持的条件类型: {condition_type}")

        # 设置条件结果变量
        context.set_variable(f"{node.id}_result", result)

        return {"condition_result": result}

    def _eval_expression(self, expression: str, inputs: dict, context: ExecutionContext) -> bool:
        """安全地评估 Python 表达式"""
        if not expression:
            return True

        # 插值变量
        expression = context.interpolate(expression)

        # 限制可用的内置函数（安全沙箱）
        safe_builtins = {
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "type": type,
            "isinstance": isinstance, "hasattr": hasattr,
        }
        try:
            return bool(eval(expression, {"__builtins__": safe_builtins}, inputs))
        except Exception as e:
            raise ValueError(f"条件表达式评估失败: {expression} → {e}")

    async def _eval_llm(self, prompt_template: str, inputs: dict, context: ExecutionContext) -> bool:
        """用 LLM 判断条件"""
        if not self.model:
            logger.warning("未配置模型客户端，条件默认返回 True")
            return True

        prompt = context.interpolate(prompt_template or "")
        response = await self.model.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = response.get("content", "").strip().lower()
        return answer in ("yes", "true", "是", "对", "1")


class CodeNodeExecutor(NodeExecutor):
    """
    代码节点执行器

    在沙箱中执行 Python 代码
    """

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        code = node.config.code

        if not code:
            raise ValueError("代码节点未配置代码")

        # 插值变量
        code = context.interpolate(code)

        # 构建执行环境
        exec_globals = {
            "inputs": inputs,
            "outputs": {},
            "json": json,
            "re": re,
            "datetime": datetime,
        }

        # 安全的内置函数
        safe_builtins = {
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip, "map": map,
            "filter": filter, "sorted": sorted, "reversed": reversed,
            "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
            "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        }
        exec_globals["__builtins__"] = safe_builtins

        try:
            exec(code, exec_globals)
            return exec_globals.get("outputs", {})
        except Exception as e:
            raise ValueError(f"代码执行失败: {e}")


class TransformNodeExecutor(NodeExecutor):
    """
    数据转换节点执行器

    支持简单的数据转换操作
    """

    async def execute(self, node: Node, inputs: dict, context: ExecutionContext) -> dict:
        config = node.config
        code = config.code

        if not code:
            # 默认透传输入
            return inputs

        # 插值变量
        code = context.interpolate(code)

        # 构建执行环境
        exec_globals = {
            "inputs": inputs,
            "outputs": {},
            "json": json,
            "re": re,
        }
        exec_globals["__builtins__"] = {
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict,
            "isinstance": isinstance,
        }

        try:
            exec(code, exec_globals)
            return exec_globals.get("outputs", inputs)
        except Exception as e:
            raise ValueError(f"数据转换失败: {e}")


def create_default_executors(model_client=None, tool_registry=None) -> dict[NodeType, NodeExecutor]:
    """创建默认的节点执行器集合"""
    return {
        NodeType.START: StartNodeExecutor(),
        NodeType.END: EndNodeExecutor(),
        NodeType.LLM: LLMNodeExecutor(model_client),
        NodeType.TOOL: ToolNodeExecutor(tool_registry),
        NodeType.CONDITION: ConditionNodeExecutor(model_client),
        NodeType.CODE: CodeNodeExecutor(),
        NodeType.TRANSFORM: TransformNodeExecutor(),
    }
