import time
import sys
from typing import List, Optional, Tuple
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import (
    ASR_MODEL_SIZE, BASE_DIR, MAX_RECORD_SEC, SAMPLE_RATE, 
    SILENCE_DURATION, SILENCE_THRESHOLD, TTS_SPEED, TTS_VOICE, WAKE_PHRASES
)
import state
from utils import log, rich_download

def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

def transcribe(audio: np.ndarray, use_vad: bool = True) -> str:
    audio_f32 = audio.astype(np.float32).flatten() / 32768.0
    segments, _ = state.whisper_model.transcribe(
        audio_f32,
        language          = "en",
        vad_filter        = use_vad,
        condition_on_previous_text = False,
    )
    return " ".join(s.text for s in segments).strip()

def listen_for_speech(speech_timeout: float = 4.0) -> Optional[np.ndarray]:
    frames: List[np.ndarray] =[]
    speech_started  = False
    silence_start: Optional[float] = None
    t0 = time.time()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
        while True:
            data, _ = stream.read(1024)
            energy   = rms(data)

            if not speech_started:
                if energy >= SILENCE_THRESHOLD:
                    speech_started = True
                    frames.append(data)
                elif time.time() - t0 > speech_timeout:
                    return None
            else:
                frames.append(data)
                if energy < SILENCE_THRESHOLD:
                    silence_start = silence_start or time.time()
                    if time.time() - silence_start >= SILENCE_DURATION:
                        break
                else:
                    silence_start = None
                if time.time() - t0 > speech_timeout + MAX_RECORD_SEC:
                    break

    return np.concatenate(frames) if frames else None

def contains_phrase(text: str, phrases: List[str]) -> bool:
    low = text.lower()
    return any(p in low for p in phrases)

def strip_wake_phrase(text: str) -> str:
    low = text.lower()
    for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
        idx = low.find(phrase)
        if idx != -1:
            return text[idx + len(phrase):].lstrip(",.!? ")
    return text

def speak(text: str) -> None:
    if not text or not text.strip():
        return
    if state.tts_mode == "kokoro":
        try:
            samples, sr = state.kokoro_tts.create(text, voice=TTS_VOICE, speed=TTS_SPEED, lang="en-us")
            sd.play(samples, sr)
            sd.wait()
        except Exception as exc:
            log(f"Kokoro error: {exc}", "red")
    elif state.tts_mode == "sapi5" and state.engine_sapi:
        try:
            state.engine_sapi.say(text)
            state.engine_sapi.runAndWait()
        except Exception as exc:
            log(f"SAPI5 error: {exc}", "red")

def _setup_kokoro() -> Tuple[Optional[Path], Optional[Path]]:
    model_file  = BASE_DIR / "kokoro-v1.0.onnx"
    voices_file = BASE_DIR / "voices-v1.0.bin"
    base_url    = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
    for fpath, url in[
        (model_file,  f"{base_url}/kokoro-v1.0.onnx"),
        (voices_file, f"{base_url}/voices-v1.0.bin"),
    ]:
        if not fpath.is_file():
            try:
                rich_download(url, fpath, fpath.name)
            except Exception as exc:
                log(f"Download failed: {exc}", "red")
                return None, None
    return model_file, voices_file

def load_models() -> None:
    with state.console.status("[cyan]Loading ASR (Whisper)...[/cyan]", spinner="dots"):
        from faster_whisper import WhisperModel
        try:
            state.whisper_model = WhisperModel(ASR_MODEL_SIZE, device="cuda", compute_type="float16")
            log(f"Whisper {ASR_MODEL_SIZE} → GPU", "green")
        except Exception:
            state.whisper_model = WhisperModel(ASR_MODEL_SIZE, device="cpu", compute_type="int8")
            log(f"Whisper {ASR_MODEL_SIZE} → CPU", "green")

    model_file, voices_file = _setup_kokoro()
    with state.console.status("[cyan]Loading TTS (Kokoro)...[/cyan]", spinner="dots"):
        if model_file and model_file.is_file():
            try:
                from kokoro_onnx import Kokoro
                state.kokoro_tts = Kokoro(str(model_file), str(voices_file))
                state.tts_mode   = "kokoro"
                log("Kokoro TTS ready.", "green")
            except Exception as exc:
                log(f"Kokoro failed ({exc}), trying fallback.", "yellow")

        if state.tts_mode != "kokoro":
            try:
                import pyttsx3
                state.engine_sapi = pyttsx3.init()
                state.tts_mode    = "sapi5"
                log("Fallback TTS (pyttsx3) ready.", "yellow")
            except Exception:
                state.console.print("[red]No TTS backend available.[/red]")
                sys.exit(1)