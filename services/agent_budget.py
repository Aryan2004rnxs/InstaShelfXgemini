import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("InstaShelf.services.agent_budget")

class MissionBudget(BaseModel):
    max_tool_calls: int = Field(default=40, description="Max tool calls allowed per mission run")
    max_model_calls: int = Field(default=20, description="Max Gemini API LLM calls per mission run")
    max_daily_actions: int = Field(default=10, description="Max autonomous background actions per day")
    tool_calls_used: int = 0
    model_calls_used: int = 0
    daily_actions_used: int = 0

_MISSION_BUDGETS: Dict[str, MissionBudget] = {}

def get_mission_budget(mission_id: str) -> MissionBudget:
    if mission_id not in _MISSION_BUDGETS:
        _MISSION_BUDGETS[mission_id] = MissionBudget()
    return _MISSION_BUDGETS[mission_id]

def check_and_consume_budget(mission_id: str, tool_calls: int = 0, model_calls: int = 0, daily_actions: int = 0) -> bool:
    budget = get_mission_budget(mission_id)
    if budget.tool_calls_used + tool_calls > budget.max_tool_calls:
        logger.warning(f"Mission {mission_id} exceeded max_tool_calls budget ({budget.max_tool_calls})")
        return False
    if budget.model_calls_used + model_calls > budget.max_model_calls:
        logger.warning(f"Mission {mission_id} exceeded max_model_calls budget ({budget.max_model_calls})")
        return False
    if budget.daily_actions_used + daily_actions > budget.max_daily_actions:
        logger.warning(f"Mission {mission_id} exceeded max_daily_actions budget ({budget.max_daily_actions})")
        return False

    budget.tool_calls_used += tool_calls
    budget.model_calls_used += model_calls
    budget.daily_actions_used += daily_actions
    return True

def get_budget_status_summary(mission_id: str) -> Dict[str, Any]:
    budget = get_mission_budget(mission_id)
    return {
        "mission_id": mission_id,
        "tool_calls": f"{budget.tool_calls_used} / {budget.max_tool_calls}",
        "model_calls": f"{budget.model_calls_used} / {budget.max_model_calls}",
        "daily_actions": f"{budget.daily_actions_used} / {budget.max_daily_actions}",
        "budget_remaining": budget.tool_calls_used < budget.max_tool_calls and budget.model_calls_used < budget.max_model_calls
    }
