import requests
from abc import ABC, abstractmethod


# -----------------------------
# Base Interface
# -----------------------------
class ModelClient(ABC):

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        pass


# -----------------------------
# Dummy Model Client
# -----------------------------
class DummyModelClient(ModelClient):

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return f"(dummy) System: {system_prompt[:30]} | User: {user_prompt[:30]}..."


# -----------------------------
# Ollama Model Client
# -----------------------------
class OllamaClient(ModelClient):
    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = "http://localhost:11434/api/generate"

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        return data.get("response", "")
    
# llm.py (add this at the bottom)
def llm_generate(prompt: str) -> str:
    client = OllamaClient(model="llama3.1:8b")
    return client.generate(system_prompt="", user_prompt=prompt)

