# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import os

# Load .env from the backend directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Internal modules
from llm import OllamaClient, DummyModelClient
from session import create_session, get_session
from roles_loader import load_role, pick_seed_question
from actions import decide_followup_rule, llm_decide_and_generate
from feedback import generate_feedback
#from feedback import generate_feedback
from summary import generate_session_summary
from tts import generate_speech
from fastapi.responses import Response

from datetime import datetime, timedelta

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------
# Constants for interview flow
# ---------------------------------------------
MAX_FOLLOWUPS_PER_Q = 3
MIN_NEXT_QUESTIONS_TO_END = 5
MIN_INTERVIEW_DURATION = timedelta(minutes=10)  # Minimum total interview time before allowing termination


# ---------------------------------------------
# Model Client
# ---------------------------------------------
model_client = OllamaClient(model="llama3.1:8b")
# model_client = DummyModelClient()

# ---------------------------------------------
# Request Models
# ---------------------------------------------
class StartRequest(BaseModel):
    name: str
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

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "en-US-naomi"


# ---------------------------------------------
# Load Prompt Templates
# ---------------------------------------------
with open("prompts/interviewer_followup.txt", "r", encoding="utf-8") as f:
    INTERVIEW_FOLLOWUP = f.read()

with open("prompts/interviewer_first_question.txt", "r", encoding="utf-8") as f:
    INTERVIEW_FIRST = f.read()


# ---------------------------------------------
# Constants for interview flow
# ---------------------------------------------
MAX_FOLLOWUPS_PER_Q = 3
MIN_NEXT_QUESTIONS_TO_END = 5


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

    # Load role
    try:
        role_data = load_role(req.role)
    except Exception:
        role_data = None

    # Pick first seed question
    seed_q = pick_seed_question(
        role_data,
        branch=req.branch,
        difficulty=req.difficulty
    ) if role_data else None

    # Fallback: LLM generates initial question
    if not seed_q:
        system_prompt_filled = INTERVIEW_FIRST.format(
            role=req.role,
            branch=req.branch or "",
            specialization=req.specialization or "",
            difficulty=req.difficulty,
            name=req.name
        )
        seed_q = model_client.generate(system_prompt=system_prompt_filled, user_prompt="").strip()

    # Build initial seed list
    seed_list = [seed_q]
    if role_data:
        attempts = 0
        while len(seed_list) < 3 and attempts < 10:
            q = pick_seed_question(
                role_data,
                branch=req.branch,
                difficulty=req.difficulty
            )
            if q not in seed_list:
                seed_list.append(q)
            attempts += 1

    # Create session
    session_id = create_session(
        name=req.name,
        role=req.role,
        branch=req.branch or "",
        specialization=req.specialization or "",
        difficulty=req.difficulty,
        seed_questions=seed_list
    )
    session = get_session(session_id)

    # Initialize interview with first question
    current = session.get_current_seed()
    if current:
        session.questions.append(current)
        
    # Prepend welcome message
    welcome_msg = f"Hi {req.name}! I'm Novexa, your AI interviewer today. I'm looking forward to getting to know you. Let's start with... "
    full_response = f"{welcome_msg}{current}" if current else welcome_msg

    return {"session_id": session_id, "next_question": full_response}


# ---------------------------------------------
# /answer — Process Answer
# ---------------------------------------------
@app.post("/answer")
def process_answer(req: AnswerRequest):

    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session_id")

    if session.completed:
        return {
            "session_id": session.id,
            "action": "end",
            "text": "Interview already completed. Request /feedback or /end for summary."
        }

    # Save answer
    session.answers.append(req.answer)

    # Load role follow-up rules
    try:
        role_data = load_role(session.role)
        rules_cfg = role_data.get("follow_up_rules", {})
    except Exception:
        rules_cfg = {}

    max_followups = rules_cfg.get("max_followups", MAX_FOLLOWUPS_PER_Q)

    # Determine if follow-up is needed
    det_strength = decide_followup_rule(session, req.answer, rules_cfg)

    # Check for explicit confirmation to end
    if session.questions:
        last_q = session.questions[-1].lower()
        ans_lower = req.answer.lower()
        if "are you sure" in last_q and any(w in ans_lower for w in ["yes", "yeah", "sure", "correct", "right"]):
            return {
                "session_id": session.id,
                "action": "end",
                "text": "Thank you for your time. Ending the interview now."
            }

    # Consult hybrid LLM engine
    decision = llm_decide_and_generate(
        session=session,
        latest_answer=req.answer,
        role_prompt_system=INTERVIEW_FOLLOWUP,
        model_client=model_client
    )

    action = decision.get("action")
    follow_up_q = decision.get("follow_up_question", "")

    # Normalize outputs
    if action not in ("follow_up", "next_question", "end"):
        action = "follow_up" if det_strength in ("weak", "moderate") else "next_question"

    if action == "end":
        return {
            "session_id": session.id,
            "action": "end",
            "text": "Thank you for your time. Ending the interview now."
        }

    # -------------------------
    # FOLLOW-UP LOGIC
    # -------------------------
    if action == "follow_up":
        if session.current_followup_count >= max_followups:

            # Max follow-ups reached → go to next question
            session.current_followup_count = 0
            session.advance_seed()
            session.next_question_count += 1

            if session.completed and session.next_question_count >= MIN_NEXT_QUESTIONS_TO_END:
                return {
                    "session_id": session.id,
                    "action": "end",
                    "text": "Interview completed. Request /feedback or /end for summary."
                }

            next_seed = session.get_current_seed()

            # Rephrase next question
            system_prompt_filled = INTERVIEW_FIRST.format(
                role=session.role,
                branch=session.branch,
                specialization=session.specialization,
                difficulty=session.difficulty,
                name=session.name
            )
            user_prompt = f"Rephrase the following interview question concisely:\n{next_seed}"
            rephrased = model_client.generate(
                system_prompt=system_prompt_filled,
                user_prompt=user_prompt
            ).strip()

            session.questions.append(rephrased)
            return {
                "session_id": session.id,
                "action": "next_question",
                "text": rephrased
            }

        # Serve follow-up question
        session.current_followup_count += 1
        session.questions.append(follow_up_q)
        return {
            "session_id": session.id,
            "action": "follow_up",
            "text": follow_up_q
        }

    # -------------------------
    # NEXT QUESTION LOGIC
    # -------------------------
    session.current_followup_count = 0
    session.advance_seed()
    session.next_question_count += 1

    # Check if we should end based on question count AND duration
    should_end_count = session.completed and session.next_question_count >= MIN_NEXT_QUESTIONS_TO_END
    
    # Check duration
    elapsed = datetime.utcnow() - session.start_time
    duration_met = elapsed >= MIN_INTERVIEW_DURATION

    if should_end_count and duration_met:
        return {
            "session_id": session.id,
            "action": "end",
            "text": "Interview completed. Request /feedback or /end for summary."
        }

    # If we ran out of seeds but need to keep going (duration not met), generate dynamic question
    if session.completed and not duration_met:
        system_prompt_filled = INTERVIEW_FIRST.format(
            role=session.role,
            branch=session.branch,
            specialization=session.specialization,
            difficulty=session.difficulty,
            name=session.name
        )
        user_prompt = "Generate a new, unique interview question for this role. Do not repeat previous questions."
        new_q = model_client.generate(
            system_prompt=system_prompt_filled,
            user_prompt=user_prompt
        ).strip()
        
        session.questions.append(new_q)
        return {
            "session_id": session.id,
            "action": "next_question",
            "text": new_q
        }

    next_seed = session.get_current_seed()

    # Rephrase next question
    system_prompt_filled = INTERVIEW_FIRST.format(
        role=session.role,
        branch=session.branch,
        specialization=session.specialization,
        difficulty=session.difficulty,
        name=session.name
    )
    user_prompt = f"Rephrase the following interview question concisely:\n{next_seed}"
    rephrased = model_client.generate(
        system_prompt=system_prompt_filled,
        user_prompt=user_prompt
    ).strip()

    session.questions.append(rephrased)

    return {
        "session_id": session.id,
        "action": "next_question",
        "text": rephrased
    }


# ---------------------------------------------
# /feedback — Evaluate specific Q/A
# ---------------------------------------------
@app.post("/feedback")
def feedback_endpoint(payload: FeedbackRequest):
    return generate_feedback(
        answer=payload.answer,
        question=payload.question,
        role=payload.role
    )


# ---------------------------------------------
# /end — Generate Full Session Summary (Unstructured)
# ---------------------------------------------
# ---------------------------------------------
# /end — Generate Full Session Summary
# ---------------------------------------------
class EndRequest(BaseModel):
    session_id: str

@app.post("/end")
def end_interview(req: EndRequest):
    session_id = req.session_id
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session_id")

    if not session.answers:
        return {"message": "No answers recorded yet."}

    session.completed = True
    summary = generate_session_summary(session)

    return {"session_id": session_id, "summary": summary}


# ---------------------------------------------
# /api/tts — Generate Speech using Murf AI
# ---------------------------------------------
@app.post("/api/tts")
def tts_endpoint(req: TTSRequest):
    try:
        audio_content = generate_speech(req.text, req.voice_id)
        return Response(content=audio_content, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
