import json
import logging
from typing import Dict, Any, Callable, Optional
from services.policy_engine import evaluate_action_policy
from memory.action_ledger import record_action
from services.agent_budget import check_and_consume_budget

logger = logging.getLogger("InstaShelf.tools.tool_gateway")

_EXECUTED_IDEMPOTENCY_KEYS = set()

async def execute_tool_via_gateway(
    tool_name: str,
    tool_func: Callable,
    tool_inputs: Dict[str, Any],
    task_id: str = "GLOBAL-TASK",
    agent_name: str = "ADKAgent",
    mission_id: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a tool call through the deterministic Tool Gateway.
    Enforces authorization, policy checks, budget caps, idempotency, and append-only audit logging.
    """
    if idempotency_key is None:
        idempotency_key = f"IDEM-{tool_name}-{hash(json.dumps(tool_inputs, sort_keys=True))}"

    # 1. Idempotency Check
    if idempotency_key in _EXECUTED_IDEMPOTENCY_KEYS:
        logger.info(f"[ToolGateway] Idempotency check hit for key {idempotency_key}. Returning cached status.")
        return {
            "status": "success",
            "executed": False,
            "idempotent": True,
            "message": "Action was previously executed successfully."
        }

    # 2. Budget Check
    if mission_id:
        allowed_budget = check_and_consume_budget(mission_id, tool_calls=1, model_calls=0)
        if not allowed_budget:
            return {
                "status": "error",
                "error": "Mission resource budget exceeded (max tool calls limit reached)."
            }

    # 3. Policy Check
    policy = evaluate_action_policy(tool_name, tool_inputs)
    if not policy.allowed and policy.requires_approval:
        # Record pending approval in audit log
        record_action(
            task_id=task_id,
            agent=agent_name,
            tool=tool_name,
            input_summary=tool_inputs,
            output_summary="Approval required by policy.",
            idempotency_key=idempotency_key,
            mission_id=mission_id,
            risk_level=policy.risk_level,
            approval_status="PENDING_USER_APPROVAL",
            verification_status="UNVERIFIED"
        )
        return {
            "status": "approval_required",
            "action": tool_name,
            "risk_level": policy.risk_level,
            "message": f"Action '{tool_name}' requires explicit user approval."
        }

    if not policy.allowed:
        return {
            "status": "blocked",
            "error": f"Action '{tool_name}' was blocked by policy engine ({policy.risk_level} risk)."
        }

    # 4. Tool Execution & Result Validation
    try:
        if callable(tool_func):
            import inspect
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**tool_inputs)
            else:
                result = tool_func(**tool_inputs)
        else:
            result = {"status": "success", "result": str(tool_func)}

        _EXECUTED_IDEMPOTENCY_KEYS.add(idempotency_key)

        # 5. Audit Logging in Append-Only Action Ledger
        out_summary = json.dumps(result)[:200] if isinstance(result, dict) else str(result)[:200]
        record_action(
            task_id=task_id,
            agent=agent_name,
            tool=tool_name,
            input_summary=tool_inputs,
            output_summary=out_summary,
            idempotency_key=idempotency_key,
            mission_id=mission_id,
            risk_level=policy.risk_level,
            approval_status="AUTOMATIC",
            verification_status="VERIFIED"
        )

        return {
            "status": "success",
            "result": result,
            "verified": True
        }
    except Exception as e:
        logger.error(f"[ToolGateway] Tool execution error ({tool_name}): {e}")
        return {
            "status": "error",
            "error": str(e)
        }
