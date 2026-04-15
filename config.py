import os
import sys
from pathlib import Path
from typing import List

WAKE_PHRASES: List[str] =[
    "wake up lavie", "hey lavie", "okay lavie", "hi lavie",
    "lavie wake up", "come on lavie",
    "lavie", "la vie", "la vee", "lavi", "la vi",
    "hey lavi", "hey la vie", "hey la vee",
]

CLOSE_PHRASES: List[str] =[
    "goodbye lavie", "bye lavie", "stop listening", "close dialogue",
    "end conversation", "that's all lavie", "thanks lavie",
    "thank you lavie", "go to sleep", "sleep lavie", "lavie sleep",
]

SAMPLE_RATE        = 16_000
SILENCE_THRESHOLD  = 150
SILENCE_DURATION   = 1.0
DIALOGUE_TIMEOUT   = 10.0
MAX_RECORD_SEC     = 30

# 👇 LOWERED TO PREVENT CONTEXT POISONING! 👇
HISTORY_MAXLEN  = 3  
MAX_NEW_TOKENS  = 300
TTS_VOICE       = "af_bella"
TTS_SPEED       = 1.15
ASR_MODEL_SIZE  = "small.en"

OLLAMA_HOST    = "http://localhost:11434"
OLLAMA_MODEL   = "qwen3.5:2b"
OLLAMA_TIMEOUT = 45

CONTEXT_DIR       = Path.home() / ".lavie"
CONTEXT_FILE      = CONTEXT_DIR / "context.json"
CHAT_HISTORY_FILE = CONTEXT_DIR / "chat_history.json"
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__))))

OLLAMA_INSTALLER_URL_WIN = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_INSTALL_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "Programs" / "Ollama"
)