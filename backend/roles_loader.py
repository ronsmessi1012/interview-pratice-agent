import json
import os
import random
from typing import Optional, Dict, Any

ROLES_DIR = os.path.join(os.path.dirname(__file__), "roles")

def load_role(role_name: str) -> Dict[str, Any]:
    """
    Load role JSON file by role name (case-insensitive).
    Eg: load_role('engineer'), load_role('sales')
    """
    filename = f"{role_name.lower()}.json"
    path = os.path.join(ROLES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Role file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_seed_question(role_data: Dict[str, Any],
                       branch: Optional[str],
                       difficulty: str) -> str:
    """
    Select a seed question based on role_data, branch (optional), and difficulty.
    - If branch provided and exists, prefer branch-specific technical questions.
    - Else, use behavioral pool or role-level technical pool.
    """
    difficulty = difficulty.lower()
    # Try branch-specific technical
    branches = role_data.get("branches")
    if branch and branches and branch.lower() in branches:
        branch_data = branches[branch.lower()]
        tech = branch_data.get("technical", {})
        bucket = tech.get(difficulty, [])
        if bucket:
            return random.choice(bucket)

        # fallback: behavioral
        behavioral = branch_data.get("behavioral", [])
        if behavioral:
            return random.choice(behavioral)

    # If no branch or no branch question, try role-level technical (for sales/retail)
    tech = role_data.get("technical", {})
    if tech:
        bucket = tech.get(difficulty, [])
        if bucket:
            return random.choice(bucket)

    # Fallback to role-level behavioral
    behavioral = role_data.get("behavioral") or []
    if behavioral:
        return random.choice(behavioral)

    # Last resort: a generic prompt
    return "Tell me about your background and why you're interested in this role."
