# backend/followup.py
import re
from typing import Dict, Any
from .session import InterviewSession
from .llm import ModelClient  # type: ignore

HEDGE_WORDS = [
    "maybe", "might", "sort of", "i think", "perhaps", "probably", "maybe", "could be", "not sure"
]

def _count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))

def _contains_hedge(text: str, hedges=None) -> bool:
    text_l = text.lower()
    hedges = hedges or HEDGE_WORDS
    return any(h in text_l for h in hedges)

def decide_followup_rule(session: InterviewSession, latest_answer: str, cfg: Dict[str, Any]) -> bool:
    """
    Simple deterministic rule: return True if follow-up recommended.
    cfg should include keys:
      - weak_answer_threshold_words
      - hedge_words (list)
    """
    threshold = cfg.get("weak_answer_threshold_words", 20)
    if _count_words(latest_answer) < threshold:
        return True

    hedges = cfg.get("hedge_words", HEDGE_WORDS)
    if _contains_hedge(latest_answer, hedges):
        return True

    # optional: check for "no example" or "no details" patterns
    if re.search(r"\b(no example|not really|can't remember|don't remember)\b", latest_answer.lower()):
        return True

    return False

def llm_decide_and_generate(session: InterviewSession,
                            latest_answer: str,
                            role_prompt_system: str,
                            model_client: ModelClient) -> Dict[str, str]:
    """
    Ask the LLM (with the INTERVIEW_FOLLOWUP style prompt) to choose:
    - return {"action":"follow_up", "text":"..."} OR {"action":"next_question", "text":"..."}
    LLM output must be plain text (we will parse heuristically).
    """
    # Build the system prompt that includes context
    system_prompt = role_prompt_system.format(
        role=session.role,
        branch=session.branch,
        specialization=session.specialization,
        difficulty=session.difficulty,
        questions="\n".join(session.questions),
        answers="\n".join(session.answers),
        latest_answer=latest_answer
    )

    # Ask LLM to output a single JSON line with action + text
    user_prompt = (
        "Decide whether to ask a follow-up question or move to the next seed question. "
        "Output EXACTLY a JSON object on a single line with fields: action and text. "
        "action must be either \"follow_up\" or \"next_question\". "
        "text must be a single interview question (one sentence, concise). "
        "Do not include any additional commentary.\n\n"
    )

    raw = model_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    # Try to extract a JSON object from raw text
    import json
    try:
        # find first { ... } substring
        jstart = raw.find("{")
        jend = raw.rfind("}") + 1
        jtxt = raw[jstart:jend]
        obj = json.loads(jtxt)
        # ensure fields exist
        if obj.get("action") in ("follow_up", "next_question") and isinstance(obj.get("text"), str):
            return {"action": obj["action"], "text": obj["text"].strip()}
    except Exception:
        # fall through to heuristic parsing
        pass

    # Heuristic fallback: if the raw contains "follow" or "clarify" then treat as follow_up
    low = raw.lower()
    if "follow" in low or "clarify" in low or "more" in low or "could you" in low:
        # extract first sentence
        sentence = raw.strip().splitlines()[0]
        return {"action": "follow_up", "text": sentence.strip()}

    # default: treat raw as next question
    sentence = raw.strip().splitlines()[0]
    return {"action": "next_question", "text": sentence.strip()}
