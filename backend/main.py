# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# internal modules
from .llm import OllamaClient, DummyModelClient
from .session import create_session, get_session
from .roles_loader import load_role, pick_seed_question
from .actions import decide_followup_rule, llm_decide_and_generate
from .feedback import generate_feedback
from .summary import generate_session_summary

app = FastAPI()

# ---------------------------------------------
# Model Client (replace with DummyModelClient for offline testing)
# ---------------------------------------------
model_client = OllamaClient(model="llama3.1:8b")
# model_client = DummyModelClient()

# ---------------------------------------------
# Request Models
# ---------------------------------------------
class StartRequest(BaseModel):
    role: str
    branch: Optional[str] = None
    specialization: Optional[str] = None
    difficulty: str = "medium"

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

class FeedbackRequest(BaseModel):
    question: str
    answer: str
    role: str


# ---------------------------------------------
# Load Prompt Templates
# ---------------------------------------------
with open("prompts/interviewer_followup.txt", "r", encoding="utf-8") as f:
    INTERVIEW_FOLLOWUP = f.read()

with open("prompts/interviewer_first_question.txt", "r", encoding="utf-8") as f:
    INTERVIEW_FIRST = f.read()


# ---------------------------------------------
# Health Check
# ---------------------------------------------
@app.get("/status")
def status():
    return {"status": "ok"}


# ---------------------------------------------
# /start — Begin Interview
# ---------------------------------------------
@app.post("/start")
def start_interview(req: StartRequest):
    # attempt to load role
    try:
        role_data = load_role(req.role)
    except Exception:
        role_data = None

    # choose first seed question
    seed_q = None
    if role_data:
        seed_q = pick_seed_question(role_data, branch=req.branch, difficulty=req.difficulty)

    if not seed_q:
        # fallback: LLM generates initial question
        system_prompt_filled = INTERVIEW_FIRST.format(
            role=req.role,
            branch=req.branch or "",
            specialization=req.specialization or "",
            difficulty=req.difficulty
        )
        seed_q = model_client.generate(system_prompt=system_prompt_filled, user_prompt="")

    # build initial seed list
    seed_list = [seed_q]

    if role_data:
        # add up to 2 additional unique seeds
        attempts = 0
        while len(seed_list) < 3 and attempts < 10:
            q = pick_seed_question(role_data, branch=req.branch, difficulty=req.difficulty)
            if q not in seed_list:
                seed_list.append(q)
            attempts += 1

    # create session
    session_id = create_session(
        role=req.role,
        branch=req.branch or "",
        specialization=req.specialization or "",
        difficulty=req.difficulty,
        seed_questions=seed_list
    )
    session = get_session(session_id)

    # initialize interview with first question
    current = session.get_current_seed()
    if current:
        session.questions.append(current)

    return {"session_id": session_id, "next_question": current}


# ---------------------------------------------
# /answer — Process Answer (Follow-ups & Next Question)
# ---------------------------------------------
# ---------------------------------------------
# /answer — Process Answer (Follow-ups & Next Question)
# ---------------------------------------------
@app.post("/answer")
def process_answer(req: AnswerRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session_id")

    if session.completed:
        return {"session_id": session.id, "action": "end", "text": "Interview already completed. Request /feedback for summary."}

    # save answer
    session.answers.append(req.answer)

    # load role follow-up rules
    try:
        role_data = load_role(session.role)
        rules_cfg = role_data.get("follow_up_rules", {})
    except Exception:
        rules_cfg = {}

    # deterministic check
    det_strength = decide_followup_rule(session, req.answer, rules_cfg)
    max_followups = rules_cfg.get("max_followups", 2)

    # if strong -> skip follow-ups entirely
    if det_strength == "strong":
        session.current_followup_count = 0
        session.advance_seed()

        if session.completed:
            return {"session_id": session.id, "action": "end", "text": "Interview completed. Request /feedback for summary."}

        next_seed = session.get_current_seed()

        # Rephrase next question via LLM
        system_prompt_filled = INTERVIEW_FIRST.format(
            role=session.role,
            branch=session.branch,
            specialization=session.specialization,
            difficulty=session.difficulty
        )
        user_prompt = f"Rephrase the following interview question concisely:\n{next_seed}"
        rephrased = model_client.generate(system_prompt=system_prompt_filled, user_prompt=user_prompt).strip()

        session.questions.append(rephrased)
        return {"session_id": session.id, "action": "next_question", "text": rephrased}

    # Otherwise → consult LLM hybrid engine
    decision = llm_decide_and_generate(
        session=session,
        latest_answer=req.answer,
        role_prompt_system=INTERVIEW_FOLLOWUP,
        model_client=model_client
    )

    action = decision.get("action")
    strength = decision.get("strength", det_strength)
    follow_up_q = decision.get("follow_up_question", "")

    # Normalize LLM outputs
    if action not in ("follow_up", "next_question", "end"):
        action = "follow_up" if strength in ("weak", "moderate") else "next_question"

    # END case
    if action == "end":
        session.completed = True
        return {"session_id": session.id, "action": "end", "text": "Interview completed. Request /feedback for summary."}

    # FOLLOW-UP case
    if action == "follow_up":
        if session.current_followup_count >= max_followups:
            # force next seed
            session.current_followup_count = 0
            session.advance_seed()

            if session.completed:
                return {"session_id": session.id, "action": "end", "text": "Interview completed. Request /feedback for summary."}

            next_seed = session.get_current_seed()

            # rephrase
            system_prompt_filled = INTERVIEW_FIRST.format(
                role=session.role,
                branch=session.branch,
                specialization=session.specialization,
                difficulty=session.difficulty
            )
            user_prompt = f"Rephrase the following interview question concisely:\n{next_seed}"
            rephrased = model_client.generate(system_prompt=system_prompt_filled, user_prompt=user_prompt).strip()

            session.questions.append(rephrased)
            return {"session_id": session.id, "action": "next_question", "text": rephrased}

        # Serve follow-up
        session.current_followup_count += 1
        session.questions.append(follow_up_q)
        return {"session_id": session.id, "action": "follow_up", "text": follow_up_q}

    # NEXT QUESTION case
    session.current_followup_count = 0
    session.advance_seed()

    if session.completed:
        return {"session_id": session.id, "action": "end", "text": "Interview completed. Request /feedback for summary."}

    next_seed = session.get_current_seed()

    system_prompt_filled = INTERVIEW_FIRST.format(
        role=session.role,
        branch=session.branch,
        specialization=session.specialization,
        difficulty=session.difficulty
    )
    user_prompt = f"Rephrase the following interview question concisely:\n{next_seed}"
    rephrased = model_client.generate(system_prompt=system_prompt_filled, user_prompt=user_prompt).strip()

    session.questions.append(rephrased)
    return {"session_id": session.id, "action": "next_question", "text": rephrased}


# ---------------------------------------------
# /feedback — Evaluate Answer (Hour 11)
# ---------------------------------------------
@app.post("/feedback")
def feedback_endpoint(payload: FeedbackRequest):
    result = generate_feedback(
        answer=payload.answer,
        question=payload.question,
        role=payload.role
    )
    return result

@app.post("/end")
def end_interview(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session_id")

    if not session.answers:
        return {"message": "No answers recorded yet."}

    session.completed = True
    summary = generate_session_summary(session)

    return {"session_id": session_id, "summary": summary}