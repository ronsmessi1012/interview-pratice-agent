import gradio as gr
import requests
import os
from gtts import gTTS
import tempfile
import time
import threading

# -------------------------
# Backend API URL
# -------------------------
BACKEND_URL = "http://127.0.0.1:8000"

# Keep track of session
SESSION_ID = None
TRANSCRIPT = []

# -------------------------
# TTS Playback helper
# -------------------------
def play_tts(text):
    """Generate temporary TTS file and play it."""
    tts = gTTS(text=text, lang="en")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(temp_file.name)
    os.system(f"afplay {temp_file.name}")  # macOS
    time.sleep(0.5)
    temp_file.close()
    os.unlink(temp_file.name)

# -------------------------
# Start Interview
# -------------------------
def start_interview(role, branch, specialization, difficulty):
    global SESSION_ID, TRANSCRIPT
    TRANSCRIPT = []
    payload = {
        "role": role,
        "branch": branch,
        "specialization": specialization,
        "difficulty": difficulty
    }
    resp = requests.post(f"{BACKEND_URL}/start", json=payload).json()
    SESSION_ID = resp["session_id"]
    next_q = resp["next_question"]
    TRANSCRIPT.append({"question": next_q, "answer": ""})
    threading.Thread(target=play_tts, args=(next_q,)).start()
    return f"Session started. First question:\n{next_q}", TRANSCRIPT

# -------------------------
# Submit Answer
# -------------------------
def answer_question(audio_data):
    global SESSION_ID, TRANSCRIPT
    if not SESSION_ID:
        return "Start an interview first.", TRANSCRIPT

    import speech_recognition as sr
    import soundfile as sf
    import tempfile

    # Convert NumPy audio to WAV
    if isinstance(audio_data, tuple):
        sr_val, audio_array = audio_data
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            sf.write(tmp.name, audio_array, sr_val)
            audio_file_path = tmp.name
    else:
        audio_file_path = audio_data

    r = sr.Recognizer()
    with sr.AudioFile(audio_file_path) as source:
        audio = r.record(source)
        try:
            user_text = r.recognize_google(audio)
        except (sr.UnknownValueError, sr.RequestError):
            user_text = ""

    if isinstance(audio_data, tuple):
        os.unlink(audio_file_path)

    if not user_text:
        return "Could not understand audio. Try again.", TRANSCRIPT

    payload = {"session_id": SESSION_ID, "answer": user_text}
    resp = requests.post(f"{BACKEND_URL}/answer", json=payload).json()

    TRANSCRIPT[-1]["answer"] = user_text

    if resp["action"] in ("next_question", "follow_up"):
        next_q = resp["text"]
        TRANSCRIPT.append({"question": next_q, "answer": ""})
        threading.Thread(target=play_tts, args=(next_q,)).start()
        return f"Interviewer: {next_q}", TRANSCRIPT

    elif resp["action"] == "end":
        threading.Thread(target=play_tts, args=("Interview completed.",)).start()
        return "Interview completed. You can request feedback.", TRANSCRIPT

    else:
        return "Unexpected response from backend.", TRANSCRIPT

# -------------------------
# END INTERVIEW (NEW)
# -------------------------
# in app.py — updated end_interview
def end_interview():
    global SESSION_ID, TRANSCRIPT
    if not SESSION_ID:
        return "No active interview to end.", TRANSCRIPT, ""

    try:
        resp = requests.post(
            f"{BACKEND_URL}/end",
            json={"session_id": SESSION_ID}
        ).json()

        summary_text = resp.get("summary", "Interview ended.")
        summary_html = ""
    except Exception as e:
        summary_text = f"Interview ended early. (Backend error: {str(e)})"
        summary_html = ""

    SESSION_ID = None

    threading.Thread(target=play_tts, args=(summary_text,)).start()

    return summary_text, TRANSCRIPT, summary_html


# -------------------------
# Gradio UI
# -------------------------
# -------------------------
# Gradio UI
# -------------------------
with gr.Blocks() as demo:
    gr.Markdown("## Interview Practice Agent (Voice)")

    with gr.Row():
        with gr.Column():
            role_input = gr.Textbox(label="Role", value=" ")
            branch_input = gr.Textbox(label="Branch", value=" ")
            specialization_input = gr.Textbox(label="Specialization", value=" ")
            difficulty_input = gr.Dropdown(
                ["easy", "medium", "hard"], 
                value="medium", 
                label="Difficulty"
            )
            start_btn = gr.Button("Start Interview")

        with gr.Column():
            output_box = gr.Textbox(
                label="Interviewer / Status",
                interactive=False,
                lines=3
            )
            transcript_box = gr.JSON(label="Transcript")

    start_btn.click(
        start_interview,
        inputs=[role_input, branch_input, specialization_input, difficulty_input],
        outputs=[output_box, transcript_box]
    )

    mic_input = gr.Microphone(label="Your Answer (Speak)")
    submit_btn = gr.Button("Submit Answer")

    # NEW: HTML report box + END button
    html_box = gr.HTML(label="Interview Report")
    end_btn = gr.Button("End Interview")

    submit_btn.click(
        answer_question,
        inputs=mic_input,
        outputs=[output_box, transcript_box]
    )

    end_btn.click(
        end_interview,
        inputs=[],
        outputs=[output_box, transcript_box, html_box]
    )

demo.launch()
