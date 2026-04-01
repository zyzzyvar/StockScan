from datetime import date
from abc import ABC, abstractmethod
import pandas as pd


def apply_operator(value, operator: str, rule_value: dict) -> bool:
    """Evaluate a single value against a rule condition."""
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False

    op = operator
    if op == "gt":
        return v > float(rule_value.get("v", 0))
    elif op == "gte":
        return v >= float(rule_value.get("v", 0))
    elif op == "lt":
        return v < float(rule_value.get("v", 0))
    elif op == "lte":
        return v <= float(rule_value.get("v", 0))
    elif op == "eq":
        return v == float(rule_value.get("v", 0))
    elif op == "between":
        return float(rule_value["min"]) <= v <= float(rule_value["max"])
    return False


class BaseEvaluator(ABC):
    """Abstract base for rule evaluators."""

    @abstractmethod
    def evaluate(
        self,
        rules: list,
        trade_date: date,
        stock_universe: list[str],
        stockdb_conn,
    ) -> dict[str, dict[int, bool]]:
        """
        Returns: {ts_code: {rule_id: bool}}
        """
        ...
