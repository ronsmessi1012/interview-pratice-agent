# backend/actions.py
import re
import json
from typing import Dict, Any
from .session import InterviewSession
from .llm import ModelClient  # type: ignore

# Default hedge words (lowercased)
DEFAULT_HEDGE_WORDS = [
    "maybe", "might", "sort of", "i think", "perhaps", "probably", "could be", "not sure", "maybe"
]

def _count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))

def _contains_hedge(text: str, hedges):
    txt = text.lower()
    return any(h in txt for h in hedges)

def decide_followup_rule(session: InterviewSession,
                         latest_answer: str,
                         cfg: Dict[str, Any]) -> str:
    """
    Deterministic heuristic that returns a strength label:
    - "strong", "moderate", or "weak"
    Uses:
      - weak_answer_threshold_words (if less => weak)
      - hedge_words => weak
      - optionally other heuristics in cfg
    """
    # defaults
    threshold = cfg.get("weak_answer_threshold_words", 20)
    hedges = [h.lower() for h in cfg.get("hedge_words", DEFAULT_HEDGE_WORDS)]

    word_count = _count_words(latest_answer)
    if word_count < max(5, int(threshold * 0.4)):  # extremely short -> weak
        return "weak"

    if _contains_hedge(latest_answer, hedges):
        return "weak"

    # moderate vs strong: use threshold
    if word_count < threshold:
        return "moderate"

    # further heuristics: presence of STAR keywords could indicate stronger answer
    star_keywords = ["situation", "task", "action", "result", "STAR", "example", "when i"]
    if any(k in latest_answer.lower() for k in star_keywords):
        return "strong"

    return "strong"


def llm_decide_and_generate(session: InterviewSession,
                            latest_answer: str,
                            role_prompt_system: str,
                            model_client: ModelClient) -> Dict[str, Any]:
    """
    Use the LLM to return a JSON object with:
      {
        "action": "follow_up" | "next_question" | "end",
        "strength": "weak" | "moderate" | "strong",
        "follow_up_question": "If action==follow_up, the suggested follow-up question string"
      }
    This function asks the model to output a JSON object on one line. Fallback heuristics applied if parsing fails.
    """
    # Build the system prompt (context included)
    system_prompt = role_prompt_system.format(
        role=session.role,
        branch=session.branch,
        specialization=session.specialization,
        difficulty=session.difficulty,
        questions="\n".join(session.questions),
        answers="\n".join(session.answers),
        latest_answer=latest_answer
    )

    user_prompt = (
        "Decide whether the candidate's latest answer needs a follow-up or we should proceed to the next seed question.\n"
        "Output EXACTLY a JSON object on a single line with fields: action, strength, follow_up_question.\n"
        " - action: one of \"follow_up\", \"next_question\", \"end\".\n"
        " - strength: one of \"weak\", \"moderate\", \"strong\" (your estimation of the latest answer).\n"
        " - follow_up_question: a single concise question (only if action is follow_up). If action is not follow_up, provide empty string.\n"
        "Do not include any extra text or explanation—only the JSON.\n"
    )

    raw = model_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    # Attempt to parse JSON substring
    try:
        jstart = raw.find("{")
        jend = raw.rfind("}") + 1
        if jstart != -1 and jend != -1 and jend > jstart:
            jtxt = raw[jstart:jend]
            obj = json.loads(jtxt)
            # Validate fields
            action = obj.get("action")
            strength = obj.get("strength")
            follow_up_q = obj.get("follow_up_question", "")
            if action in ("follow_up", "next_question", "end") and strength in ("weak", "moderate", "strong"):
                return {
                    "action": action,
                    "strength": strength,
                    "follow_up_question": (follow_up_q or "").strip()
                }
    except Exception:
        pass

    # Fallback heuristic parsing if LLM response not parseable
    low = raw.lower()
    # Determine action by keywords
    if any(k in low for k in ["follow up", "follow-up", "clarify", "could you", "tell me more", "what do you mean"]):
        # try to extract a question-like line
        candidate_line = raw.strip().splitlines()[0]
        return {"action": "follow_up", "strength": "moderate", "follow_up_question": candidate_line.strip()}

    if any(k in low for k in ["next", "move on", "next question", "proceed"]):
        return {"action": "next_question", "strength": "strong", "follow_up_question": ""}

    # Default: conservative -> ask one follow-up (moderate)
    first_line = raw.strip().splitlines()[0] if raw.strip() else "Could you elaborate on that?"
    return {"action": "follow_up", "strength": "moderate", "follow_up_question": first_line.strip()}
