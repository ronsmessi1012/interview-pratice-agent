# scoring.py
from typing import Dict, Any
from .llm import llm_generate  # or DummyModelClient

def score_answer(answer: str, question: str, role: str) -> Dict[str, Any]:
    """
    Compute scores for an answer considering the specific question.
    Returns a dict of numerical scores and optionally qualitative labels.
    """

    # Step 1 — Build a prompt for LLM scoring
    prompt = f"""
You are an expert interview evaluator for role: {role}.
Evaluate the candidate's answer with respect to the specific question.

QUESTION: {question}
ANSWER: {answer}

Score the answer on a scale 0-10 for:
- Accuracy
- Relevance
- Clarity
- Depth of reasoning

Return STRICT JSON ONLY:
{{
    "accuracy": int,
    "relevance": int,
    "clarity": int,
    "depth": int
}}
"""

    # Step 2 — Call LLM
    raw = llm_generate(prompt)

    # Step 3 — Parse safely
    import json
    try:
        scores = json.loads(raw)
        # convert all values to float to avoid type issues later
        scores = {k: float(v) for k, v in scores.items()}
    except Exception:
        # fallback dummy scoring
        scores = {
            "accuracy": 5.0,
            "relevance": 5.0,
            "clarity": 5.0,
            "depth": 5.0
        }

    return scores
