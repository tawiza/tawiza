"""Utility tools for the unified agent."""

import ast
import operator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry

# Safe operators for calculation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_evaluate(node):
    """Safely evaluate a math expression AST node.

    Args:
        node: AST node to evaluate

    Returns:
        Result of evaluation

    Raises:
        ValueError: If expression contains unsafe operations
    """
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsafe operator: {op_type.__name__}")
        left = safe_evaluate(node.left)
        right = safe_evaluate(node.right)
        return SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsafe operator: {op_type.__name__}")
        operand = safe_evaluate(node.operand)
        return SAFE_OPERATORS[op_type](operand)
    else:
        raise ValueError(f"Unsafe expression: {ast.dump(node)}")


async def get_datetime(timezone: str = "UTC") -> dict[str, Any]:
    """Get current datetime in specified timezone.

    Args:
        timezone: Timezone name (default: "UTC")

    Returns:
        Dict with success, datetime, timezone, and optional error
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        return {
            "success": True,
            "datetime": now.isoformat(),
            "timezone": timezone,
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S %Z")
        }
    except Exception as e:
        logger.error(f"Error getting datetime for timezone {timezone}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def calculate(expression: str) -> dict[str, Any]:
    """Safely evaluate a mathematical expression.

    Args:
        expression: Mathematical expression to evaluate

    Returns:
        Dict with success, result, and optional error
    """
    try:
        # Parse the expression
        tree = ast.parse(expression, mode='eval')

        # Evaluate safely using AST
        result = safe_evaluate(tree.body)

        logger.debug(f"Calculated: {expression} = {result}")

        return {
            "success": True,
            "expression": expression,
            "result": result
        }
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        logger.error(f"Error calculating expression '{expression}': {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error calculating expression '{expression}': {e}")
        return {
            "success": False,
            "error": f"Invalid expression: {str(e)}"
        }


def register_utility_tools(registry: ToolRegistry) -> None:
    """Register utility tools with the registry.

    Args:
        registry: ToolRegistry instance to register tools with
    """
    # Manually add tools since registry.register is a decorator
    registry._tools["utility.datetime"] = Tool(
        name="utility.datetime",
        func=get_datetime,
        category=ToolCategory.UTILITY,
        description="Get current date and time in specified timezone"
    )

    registry._tools["utility.calculate"] = Tool(
        name="utility.calculate",
        func=calculate,
        category=ToolCategory.UTILITY,
        description="Safely evaluate a mathematical expression"
    )

    logger.debug("Registered 2 utility tools")
