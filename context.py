import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from config import CONTEXT_FILE, CHAT_HISTORY_FILE
import state

@dataclass
class UserContext:
    user_name:       Optional[str]       = None
    app_usage:       Dict[str, int]      = field(default_factory=dict)
    topic_frequency: Dict[str, int]      = field(default_factory=dict)
    notes:           List[str]           = field(default_factory=list)
    session_count:   int                 = 0
    last_session:    Optional[str]       = None

    def record_app_use(self, app: str) -> None:
        self.app_usage[app] = self.app_usage.get(app, 0) + 1
        self.save()

    def record_topics(self, text: str) -> None:
        stopwords = {
            "the","a","an","is","it","to","of","in","and","or",
            "that","this","was","for","are","with","have","from",
        }
        for word in re.findall(r"\b[a-z]{4,}\b", text.lower()):
            if word not in stopwords:
                self.topic_frequency[word] = self.topic_frequency.get(word, 0) + 1
        self.save()

    def add_note(self, note: str) -> None:
        note = note.strip()
        if note and note not in self.notes:
            self.notes.append(note)
            self.notes = self.notes[-50:]
            self.save()

    def start_session(self) -> None:
        self.session_count += 1
        self.last_session = datetime.now().isoformat(timespec="seconds")
        self.save()

    def to_prompt_summary(self) -> str:
        lines =[f"Session #{self.session_count}  |  {datetime.now().strftime('%A %d %b, %H:%M')}"]
        if self.user_name:
            lines.append(f"User: {self.user_name}")
        if self.app_usage:
            top = sorted(self.app_usage.items(), key=lambda x: -x[1])[:5]
            lines.append("Apps: " + ", ".join(f"{a}({n}×)" for a, n in top))
        if self.notes:
            lines.extend(f"• {n}" for n in self.notes[-8:])
        return "\n".join(lines)

    def save(self) -> None:
        try:
            with open(CONTEXT_FILE, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @classmethod
    def load(cls) -> "UserContext":
        if CONTEXT_FILE.is_file():
            try:
                with open(CONTEXT_FILE, encoding="utf-8") as fh:
                    data = json.load(fh)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

user_ctx = UserContext.load()

def load_chat_history() -> None:
    if CHAT_HISTORY_FILE.is_file():
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as fh:
                for entry in json.load(fh):
                    state.chat_history.append(entry)
        except Exception:
            pass

def save_chat_history() -> None:
    try:
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(list(state.chat_history), fh, indent=2, ensure_ascii=False)
    except Exception:
        pass