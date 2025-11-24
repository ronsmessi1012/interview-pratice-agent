# Backend Documentation

## Tech Stack
- **Framework**: FastAPI (Python)
- **Language**: Python 3.10+
- **LLM Integration**: Ollama (running Llama 3 locally)
- **Text-to-Speech (TTS)**: Murf.ai API (Direct HTTP calls)
- **Data Validation**: Pydantic
- **CORS**: FastAPI Middleware
- **Environment Management**: `python-dotenv`

## Backend Pipeline

1.  **Session Initialization (`/start`)**:
    - Receives user details (Name, Role, etc.).
    - Creates a new `InterviewSession` with a unique ID.
    - Selects initial "seed questions" based on the role.
    - Returns the first question and welcome message.

2.  **Answer Processing (`/answer`)**:
    - Receives user's spoken text.
    - **Intent Detection**: Checks if the user wants to end the interview ("Are you sure?").
    - **LLM Decision**: Uses Llama 3 to decide the next move:
        - `follow_up`: Ask a clarifying question (if answer is weak/vague).
        - `next_question`: Move to the next seed question (if answer is good).
        - `end`: Terminate the interview.
    - **Duration Check**: Enforces a minimum interview duration (10 mins) and question count (5) before allowing termination.
    - **Dynamic Generation**: If seed questions run out, the LLM generates new questions on the fly.

3.  **Text-to-Speech (`/api/tts`)**:
    - Receives text from the frontend.
    - Calls Murf.ai API (`https://api.murf.ai/v1/speech/generate`) to generate high-quality AI voice.
    - Returns the audio binary (MP3) to the frontend.
    - **Optimization**: Uses `requests.Session` for connection pooling to minimize latency.

4.  **Report Generation (`/end`)**:
    - Aggregates the entire transcript.
    - Uses Llama 3 to generate a structured JSON report including:
        - Scores (0-5) for Clarity, Structure, Technical Accuracy.
        - Strengths and Weaknesses.
        - Actionable Improvement Plan.
        - Practice Prompts and Resources.
