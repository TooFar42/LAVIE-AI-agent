from collections import deque
from rich.console import Console

from config import HISTORY_MAXLEN

console      = Console()
chat_history = deque(maxlen=HISTORY_MAXLEN * 2)

whisper_model = None
kokoro_tts    = None
tts_mode      = None
engine_sapi   = None