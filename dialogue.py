import time

from rich.panel import Panel
from rich.rule import Rule

from config import CLOSE_PHRASES, DIALOGUE_TIMEOUT
import state
from context import load_chat_history, save_chat_history, user_ctx
from audio import contains_phrase, listen_for_speech, speak, transcribe
from llm import run_llm

def handle_turn(user_text: str) -> bool:
    user_ctx.record_topics(user_text)
    state.console.print(Panel(
        f"[bold yellow]You >[/bold yellow]  {user_text}",
        border_style="yellow", padding=(0, 1),
    ))
    with state.console.status("[cyan]Thinking...[/cyan]", spinner="dots2"):
        t0 = time.perf_counter()
        raw_block, speak_text, should_close = run_llm(user_text)
        elapsed = time.perf_counter() - t0

    state.console.print(Panel(
        f"[bold cyan]LAVIE >[/bold cyan]  {speak_text}\n"
        f"[dim]({elapsed:.1f}s)[/dim]",
        border_style="cyan", padding=(0, 1),
    ))
    state.chat_history.append({"role": "user",      "content": user_text})
    state.chat_history.append({"role": "assistant", "content": speak_text})
    save_chat_history()
    speak(speak_text)
    return should_close

def _close_dialogue() -> None:
    user_ctx.save()
    save_chat_history()
    state.console.print(Rule("[dim]Dialogue closed — listening for wake phrase[/dim]", style="dim cyan"))

def run_dialogue(initial_command: str = "") -> None:
    user_ctx.start_session()
    state.chat_history.clear()
    load_chat_history()
    state.console.print(Rule("[bold cyan]◉  Dialogue Active[/bold cyan]", style="cyan"))
    speak("I'm listening.")

    if initial_command and len(initial_command) > 2:
        if handle_turn(initial_command):
            _close_dialogue()
            return

    last_speech = time.time()

    while True:
        elapsed_silence = time.time() - last_speech
        remaining       = DIALOGUE_TIMEOUT - elapsed_silence

        if remaining <= 0:
            speak("Closing — I'll be here when you need me.")
            break

        audio = listen_for_speech(speech_timeout=min(remaining, 3.0))
        if audio is None:
            continue

        state.console.print("[yellow]Transcribing…[/yellow]", end="\r")
        text = transcribe(audio, use_vad=True)

        if not text or len(text) < 2:
            state.console.print("[dim]… (nothing clear)[/dim]")
            continue

        if contains_phrase(text, CLOSE_PHRASES):
            speak("Goodbye! I'll be here when you need me.")
            break

        if handle_turn(text):
            break

        last_speech = time.time()

    _close_dialogue()