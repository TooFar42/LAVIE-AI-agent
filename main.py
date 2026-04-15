import sys
import time
from typing import List

import keyboard
import numpy as np
import sounddevice as sd
from rich.align import Align
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from config import ASR_MODEL_SIZE, OLLAMA_MODEL, SAMPLE_RATE, TTS_VOICE, WAKE_PHRASES
import state
from context import save_chat_history, user_ctx
from audio import contains_phrase, listen_for_speech, load_models, strip_wake_phrase, transcribe
from dialogue import run_dialogue
from llm import bootstrap_ollama
from utils import log

def print_banner() -> None:
    state.console.clear()
    try:
        import onnxruntime as ort
        dev = (
            "[bold green]GPU[/bold green] (CUDA)"
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else "CPU"
        )
    except Exception:
        dev = "CPU"

    grid = Table.grid(expand=True)
    grid.add_column(justify="center")
    grid.add_row("")
    grid.add_row(Panel(
        Align.center(Text.from_markup(
            "[bold cyan]L A V I E[/bold cyan]  [dim]v2[/dim]\n"
            "[dim]Local AI Voice Interactive Engine[/dim]"
        ), vertical="middle"),
        border_style="cyan", padding=(1, 6),
    ))

    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim cyan", justify="right")
    info.add_column(style="white")
    info.add_row("Device",         f"[bold]{dev}[/bold]")
    info.add_row("LLM",            f"[bold]{OLLAMA_MODEL}[/bold]  [dim]via Ollama[/dim]")
    info.add_row("ASR",            f"Whisper [bold]{ASR_MODEL_SIZE}[/bold]")
    info.add_row("TTS",            f"Kokoro  voice=[bold]{TTS_VOICE}[/bold]")
    info.add_row("Sessions",       f"[bold]{user_ctx.session_count}[/bold]  [dim](context from ~/.lavie/)[/dim]")
    info.add_row("Wake phrase",    '[bold yellow]"Hey LAVIE"[/bold yellow]  or  [bold yellow]Ctrl+Space[/bold yellow]')
    info.add_row("Close dialogue", '"Goodbye LAVIE"  or  10 s silence')
    info.add_row("Quit",           "[bold red]Ctrl+C[/bold red]")

    grid.add_row(Align.center(info))
    grid.add_row("")
    state.console.print(grid)
    state.console.print(Rule(style="dim cyan"))

def run_assistant() -> None:
    state.console.print(Rule("[bold cyan]Listening for wake phrase[/bold cyan]", style="cyan"))
    state.console.print(
        '[dim]Say [bold yellow]"Hey LAVIE"[/bold yellow] to start a dialogue, '
        'or hold [bold yellow]Ctrl+Space[/bold yellow].  '
        '[bold red]Ctrl+C[/bold red] to quit.[/dim]\n'
    )

    while True:
        try:
            if keyboard.is_pressed("ctrl+space"):
                state.console.print("[bold green]● Recording (release to stop)[/bold green]", end="\r")
                frames: List[np.ndarray] =[]
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as st:
                    while keyboard.is_pressed("ctrl+space"):
                        d, _ = st.read(1024)
                        frames.append(d)
                if len(frames) < 5:
                    continue
                state.console.print("[yellow]Transcribing...[/yellow]                                  ", end="\r")
                audio = np.concatenate(frames)
                text  = transcribe(audio, use_vad=False)
                if text and len(text) > 2:
                    run_dialogue(text)
                continue

            audio = listen_for_speech(speech_timeout=4.0)
            if audio is None:
                time.sleep(0.01)
                continue

            snippet = transcribe(audio, use_vad=False)
            if not snippet:
                continue

            log(f"Heard: {snippet!r}", "dim white")

            if not contains_phrase(snippet, WAKE_PHRASES):
                continue

            command = strip_wake_phrase(snippet)
            run_dialogue(command)

        except KeyboardInterrupt:
            state.console.print("\n[bold red]Goodbye![/bold red]")
            user_ctx.save()
            save_chat_history()
            sys.exit(0)
        except Exception as exc:
            state.console.print(f"[red]Loop error: {exc}[/red]")
            time.sleep(0.5)

if __name__ == "__main__":
    print_banner()
    bootstrap_ollama()
    load_models()
    run_assistant()
