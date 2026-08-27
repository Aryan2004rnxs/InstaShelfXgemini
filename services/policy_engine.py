import logging
from typing import Dict, Any, Tuple
from pydantic import BaseModel

logger = logging.getLogger("InstaShelf.services.policy_engine")

class PolicyDecision(BaseModel):
    action: str
    risk_level: str  # SAFE, LOW, MEDIUM, HIGH, CRITICAL
    allowed: bool
    requires_approval: bool
    reason: str

# Policy Classification Matrix
RISK_MATRIX = {
    "SAVE_SHELF": ("SAFE", True, False),
    "GENERATE_KNOWLEDGE_MAP": ("SAFE", True, False),
    "GENERATE_STUDY_MATERIAL": ("SAFE", True, False),
    "NOTIFY_USER": ("SAFE", True, False),
    "ARCHIVE_DUPLICATE": ("LOW", True, False),
    "REORDER_CURRICULUM": ("LOW", True, False),
    "CREATE_MISSION": ("LOW", True, False),
    "UPDATE_MISSION_HEALTH": ("LOW", True, False),
    "RESTRUCTURE_MISSION": ("MEDIUM", True, False), # Auto + undo
    "DELETE_ITEM": ("HIGH", False, True),           # Approval required
    "EXTERNAL_BROADCAST": ("HIGH", False, True),    # Approval required
    "EXECUTE_SYSTEM_CMD": ("CRITICAL", False, False) # Blocked
}

def evaluate_action_policy(action_name: str, tool_inputs: Dict[str, Any], user_policy_overrides: Dict[str, str] = None) -> PolicyDecision:
    """
    Evaluates proposed agent action against deterministic Risk & Safety Policy Engine.
    Models never receive unrestricted access; policy dictates authorization.
    """
    action_key = action_name.upper()
    
    if action_key in RISK_MATRIX:
        risk, allowed, req_approval = RISK_MATRIX[action_key]
    else:
        # Default policy for unknown tools
        risk, allowed, req_approval = "MEDIUM", True, False

    # Check user policy overrides
    if user_policy_overrides and action_key in user_policy_overrides:
        override = user_policy_overrides[action_key]
        if override == "ALWAYS_ALLOW":
            allowed, req_approval = True, False
        elif override == "ALWAYS_REQUIRE_APPROVAL":
            allowed, req_approval = False, True
        elif override == "ALWAYS_BLOCK":
            allowed, req_approval = False, False

    reason = f"Action '{action_name}' classified as {risk} risk. Allowed: {allowed}, Approval Required: {req_approval}."
    logger.info(f"[PolicyEngine] {reason}")

    return PolicyDecision(
        action=action_name,
        risk_level=risk,
        allowed=allowed,
        requires_approval=req_approval,
        reason=reason
    )
