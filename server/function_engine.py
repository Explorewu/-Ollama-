from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class FunctionCategory(str, Enum):
    TIME = "time"
    UTILITY = "utility"


@dataclass
class FunctionParameter:
    name: str
    type: str
    description: str
    required: bool = False


@dataclass
class FunctionDefinition:
    name: str
    description: str
    category: FunctionCategory
    parameters: List[FunctionParameter]
    handler: Callable[..., Dict[str, Any]]
    require_confirmation: bool = False


class FunctionRegistry:
    def __init__(self):
        self._registry: Dict[str, FunctionDefinition] = {}
        self._history: List[Dict[str, Any]] = []

    def register(self, func: FunctionDefinition) -> None:
        self._registry[func.name] = func

    def get(self, name: str) -> Optional[FunctionDefinition]:
        return self._registry.get(name)

    def list_all(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        return [
            {
                "name": f.name,
                "description": f.description,
                "category": f.category.value,
                "parameters": [p.__dict__ for p in f.parameters],
                "require_confirmation": f.require_confirmation,
            }
            for f in self._registry.values()
        ]

    def execute(self, name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
        func = self.get(name)
        if not func:
            return {"success": False, "message": "function not found", "code": 404, "data": None}

        if func.require_confirmation and not require_confirmation:
            return {
                "success": False,
                "message": "confirmation required",
                "code": 403,
                "data": {"function": name, "description": func.description, "require_confirmation": True},
            }

        try:
            result = func.handler(**(arguments or {}))
            if not isinstance(result, dict):
                result = {"value": result}
            payload = {"success": True, "message": "ok", "code": 200, "data": result}
        except Exception as e:
            payload = {"success": False, "message": str(e), "code": 500, "data": None}

        self._history.append({
            "function": name,
            "arguments": arguments or {},
            "result": payload,
            "timestamp": datetime.now().isoformat(),
        })
        return payload

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]


class DateTimeFunctions:
    @staticmethod
    def get_current_time(format_type: str = "datetime") -> Dict[str, Any]:
        now = datetime.now()
        if format_type == "date":
            value = now.strftime("%Y-%m-%d")
        elif format_type == "time":
            value = now.strftime("%H:%M:%S")
        elif format_type == "timestamp":
            value = int(now.timestamp())
        else:
            value = now.strftime("%Y-%m-%d %H:%M:%S")
        return {"value": value}


class UtilityFunctions:
    @staticmethod
    def calculate(expression: str) -> Dict[str, Any]:
        import ast
        import operator
        
        if not expression or not isinstance(expression, str):
            return {"error": "invalid expression"}
        
        expression = expression.strip()
        if not expression:
            return {"error": "empty expression"}
        
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return {"error": "invalid characters in expression"}
        
        try:
            tree = ast.parse(expression, mode='eval')
            
            def safe_eval(node):
                if isinstance(node, ast.Constant):
                    if isinstance(node.value, (int, float)):
                        return node.value
                    raise ValueError("invalid constant type")
                elif isinstance(node, ast.BinOp):
                    left = safe_eval(node.left)
                    right = safe_eval(node.right)
                    if isinstance(node.op, ast.Add):
                        return left + right
                    elif isinstance(node.op, ast.Sub):
                        return left - right
                    elif isinstance(node.op, ast.Mult):
                        return left * right
                    elif isinstance(node.op, ast.Div):
                        if right == 0:
                            raise ValueError("division by zero")
                        return left / right
                    else:
                        raise ValueError("unsupported operator")
                elif isinstance(node, ast.UnaryOp):
                    operand = safe_eval(node.operand)
                    if isinstance(node.op, ast.USub):
                        return -operand
                    elif isinstance(node.op, ast.UAdd):
                        return operand
                    else:
                        raise ValueError("unsupported unary operator")
                elif isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                else:
                    raise ValueError(f"unsupported node type: {type(node).__name__}")
            
            result = safe_eval(tree)
            return {"result": result}
        except SyntaxError:
            return {"error": "invalid expression syntax"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"calculation error: {str(e)}"}


function_registry = FunctionRegistry()


def create_function_registry() -> FunctionRegistry:
    registry = FunctionRegistry()

    registry.register(FunctionDefinition(
        name="get_current_time",
        description="Get current time",
        category=FunctionCategory.TIME,
        parameters=[FunctionParameter("format_type", "string", "datetime|date|time|timestamp", required=False)],
        handler=DateTimeFunctions.get_current_time,
    ))

    registry.register(FunctionDefinition(
        name="calculate",
        description="Evaluate a math expression",
        category=FunctionCategory.UTILITY,
        parameters=[FunctionParameter("expression", "string", "Math expression", required=True)],
        handler=UtilityFunctions.calculate,
    ))

    return registry


function_registry = create_function_registry()


def list_functions(enabled_only: bool = True) -> List[Dict[str, Any]]:
    return function_registry.list_all(enabled_only)


def execute_function(name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
    return function_registry.execute(name, arguments, require_confirmation)


def get_execution_history(limit: int = 50) -> List[Dict[str, Any]]:
    return function_registry.get_execution_history(limit)

