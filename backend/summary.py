# backend/summary.py
from typing import Dict, Any, List
from .scoring import score_answer
from .llm import llm_generate
import json

def generate_session_summary(session) -> Dict[str, Any]:
    """
    Generate a full session summary:
    - Average numeric scores
    - Q/A transcript
    - Recommended practice prompts (via LLM)
    """

    transcript: List[Dict[str, Any]] = []
    scores_list: List[Dict[str, Any]] = []

    # Step 1 — Score each answered question
    for q, a in zip(session.questions, session.answers):
        score = score_answer(a, q, session.role)
        scores_list.append(score)
        transcript.append({"question": q, "answer": a, "score": score})

    # Step 2 — Compute average numeric scores safely
    avg_scores: Dict[str, float] = {}
    if scores_list:
        keys = scores_list[0].keys()
        for k in keys:
            numeric_values = []
            for s in scores_list:
                try:
                    numeric_values.append(float(s[k]))
                except (ValueError, TypeError):
                    continue  # skip non-numeric entries
            if numeric_values:
                avg_scores[k] = round(sum(numeric_values) / len(numeric_values), 2)
            else:
                avg_scores[k] = None

    # Step 3 — Build LLM prompt for practice items
    practice_prompt = f"""
You are an expert interview coach.
Given the following average scores and Q/A transcript:

Average Scores: {avg_scores}
Transcript: {transcript}

Provide:
1. Three practice prompts similar to the questions answered
2. Links to resources or exercises to improve
Return STRICT JSON with keys:
{{"practice_prompts": [str], "resource_links": [str]}}
"""

    # Step 4 — Call LLM and parse JSON safely
    raw_response = llm_generate(practice_prompt)
    try:
        practice: Dict[str, Any] = json.loads(raw_response)
    except json.JSONDecodeError:
        # fallback in case LLM returns invalid JSON
        practice = {"practice_prompts": [], "resource_links": []}

    # Step 5 — Return final session summary
    return {
        "avg_scores": avg_scores,
        "transcript": transcript,
        "practice": practice,
        "total_questions": len(session.questions),
        "completed": getattr(session, "completed", False)
    }
