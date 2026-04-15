import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import List, Optional, Tuple

from rich.panel import Panel
from rich.progress import BarColumn, Progress
from rich.rule import Rule

from config import (
    MAX_NEW_TOKENS, OLLAMA_HOST, OLLAMA_INSTALL_DIR, OLLAMA_INSTALLER_URL_WIN, 
    OLLAMA_MODEL, OLLAMA_TIMEOUT
)
import state
from context import user_ctx
from commands import execute_single_command, web_search
from utils import clean_text, is_port_open, log, rich_download

def build_system_prompt() -> str:
    recent = list(state.chat_history)[-6:]
    history_lines = "\n".join(
        f"{'User' if e['role']=='user' else 'LAVIE'}: {e['content'].replace(chr(10),' ')}"
        for e in recent
    ) or "None"

    return f"""You are LAVIE, a fast local voice assistant. You run entirely on-device.

USER CONTEXT
{user_ctx.to_prompt_summary()}

RECENT TURNS
{history_lines}

══════════ RESPONSE FORMAT — MANDATORY ══════════
You must output commands on their own lines, followed by a <speak> block.

Available Commands:
open: app_name
close: app_name
website: url
search: query
type: text
key: ctrl+c
volume: 50
screenshot
close_dialogue

<speak>
Short sentence to say out loud.
</speak>

══════════ EXAMPLES ══════════
User: Open edge
open: msedge
<speak>Opening Microsoft Edge for you.</speak>

User: What is the news about AI?
search: latest AI news
<speak>Let me look up the latest news on AI.</speak>

User: Open Opera GX
open: opera
<speak>I'm on it.</speak>

══════════ STRICT RULES ══════════
1. DISABLE ALL REASONING. Do NOT use <think> tags or internal monologue. Answer instantly.
2. If asked to search, YOU MUST OUTPUT THE `search: query` COMMAND. NEVER apologize without running the command first.
3. Keep <speak> under 20 words.
"""

def parse_llm_response(text: str) -> Tuple[str, str, List[str]]:
    # 0. Completely eradicate thinking blocks before parsing anything!
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE) 
    
    commands =[]
    
    # 1. Extract explicit <cmd> tags if they exist
    for match in re.findall(r"<cmd>\s*(.*?)\s*</cmd>", text, re.DOTALL | re.IGNORECASE):
        commands.append(match.strip())
            
    # 2. Extract implicit commands line by line
    for line in text.split("\n"):
        line = line.strip()
        match = re.match(r"^(open|close|website|search|type|key|volume|learn):\s*(.+)$", line, re.IGNORECASE)
        if match:
            val = match.group(2).split("<")[0].strip()
            cmd_str = f"{match.group(1).lower()}: {val}"
            if not any(cmd_str.lower() == c.lower() for c in commands):
                commands.append(cmd_str)
                
        if line.lower() in ["screenshot", "close_dialogue"]:
            if not any(line.lower() == c.lower() for c in commands):
                commands.append(line.lower())

    # 3. Extract the spoken text block
    speak_m = re.search(r"<speak>\s*(.*?)\s*</speak>", text, re.DOTALL | re.IGNORECASE)
    if speak_m:
        speak_text = speak_m.group(1)
    else:
        # Fallback: remove all known command lines and <raw> blocks, speak the rest
        raw_m = re.search(r"<raw>\s*(.*?)\s*</raw>", text, re.DOTALL | re.IGNORECASE)
        speak_text = text.replace(raw_m.group(0), "") if raw_m else text
        
        clean_lines =[]
        for line in speak_text.split("\n"):
            line = line.strip()
            if re.match(r"^(open|close|website|search|type|key|volume|learn):", line, re.IGNORECASE):
                continue
            if line.lower() in ["screenshot", "close_dialogue"]:
                continue
            clean_lines.append(line)
        speak_text = " ".join(clean_lines)

    speak_text = clean_text(speak_text)
    
    if not speak_text.strip() and commands:
        speak_text = "I'm on it."

    return text, speak_text.strip(), commands

def _call_ollama(messages: List[dict]) -> str:
    payload = json.dumps({
        "model":   OLLAMA_MODEL,
        "messages": messages,
        "stream":  True,
        "think":   False,
        "options": {
            "num_predict":    MAX_NEW_TOKENS,
            "temperature":    0.25,
            "repeat_penalty": 1.1,
            "top_k":          20,
            "top_p":          0.8,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parts: List[str] =[]
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    tok   = chunk.get("message", {}).get("content", "")
                    if tok:
                        parts.append(tok)
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    pass
    except urllib.error.URLError as exc:
        return f"<speak>Ollama error: {exc.reason}</speak>"
    except Exception as exc:
        return f"<speak>Error: {exc}</speak>"

    return "".join(parts) or "<speak>No response received.</speak>"

def run_llm(user_text: str) -> Tuple[str, str, bool]:
    sys_msg  = {"role": "system", "content": build_system_prompt()}
    messages = [sys_msg] + list(state.chat_history) +[{"role": "user", "content": user_text}]

    raw_response                 = _call_ollama(messages)
    raw_block, speak_text, cmds  = parse_llm_response(raw_response)

    search_queries: List[str] = []
    other_commands: List[str] =[]
    close_issued               = False

    for cmd in cmds:
        cmd = cmd.strip()
        if   cmd == "close_dialogue":      close_issued = True
        elif cmd.startswith("search:"):    search_queries.append(cmd.split(":", 1)[1].strip())
        else:                              other_commands.append(cmd)

    for cmd in other_commands:
        execute_single_command(cmd)

    if search_queries and not close_issued:
        results =[]
        for q in search_queries:
            user_ctx.record_topics(q)
            
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
            try:
                webbrowser.get("firefox").open_new_tab(search_url)
                log(f"Opened Firefox search tab for: {q}", "green")
            except webbrowser.Error:
                webbrowser.open_new_tab(search_url)
                log(f"Opened default browser search tab for: {q}", "green")

            result = web_search(q)
            
            if result == "NO_RESULTS" or "No instant answer" in result:
                log(f"Background Search '{q}' → No text found, relying on browser tab.", "dim yellow")
                # Force the AI to say the specific line if no text was scraped
                results.append(f"'{q}': No text summary available. IMPORTANT INSTRUCTION: You MUST say exactly \"Here's the page for you.\" and nothing else.")
            else:
                log(f"Background Search '{q}' → {result[:60]}…", "dim cyan")
                results.append(f"'{q}': {result}")

        messages.append({"role": "assistant", "content": raw_response})
        messages.append({
            "role": "user",
            "content": (
                "Search results:\n" + "\n".join(results)
                + "\n\nIf the results contain text, summarize them briefly. If the results instruct you to say \"Here's the page for you.\", then you MUST say exactly that phrase and nothing else."
            ),
        })
        raw_response2               = _call_ollama(messages)
        raw_block, speak_text, cmds2 = parse_llm_response(raw_response2)
        
        for cmd in cmds2:
            cmd = cmd.strip()
            if   cmd == "close_dialogue": close_issued = True
            elif not cmd.startswith("search:"): execute_single_command(cmd)

    return raw_block, speak_text, close_issued

def _find_ollama_exe() -> Optional[Path]:
    found = shutil.which("ollama")
    if found:
        return Path(found)
    candidates: List[Path] = []
    if sys.platform == "win32":
        candidates =[
            OLLAMA_INSTALL_DIR / "ollama.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path("C:/Program Files/Ollama/ollama.exe"),
        ]
    elif sys.platform == "darwin":
        candidates =[Path("/usr/local/bin/ollama"), Path("/opt/homebrew/bin/ollama")]
    else:
        candidates =[Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
    for p in candidates:
        if p.is_file():
            return p
    return None

def _install_ollama() -> Path:
    if sys.platform == "win32":
        state.console.print(Panel("[bold yellow]Ollama not found — downloading installer...[/bold yellow]",
                            border_style="yellow"))
        tmp = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
        try:
            rich_download(OLLAMA_INSTALLER_URL_WIN, tmp, "OllamaSetup.exe")
            subprocess.run([str(tmp), "/S", f"/D={OLLAMA_INSTALL_DIR}"], check=True)
            log("Ollama installed.", "green")
        finally:
            tmp.unlink(missing_ok=True)
    else:
        state.console.print(Panel("[bold yellow]Ollama not found — running install script...[/bold yellow]",
                            border_style="yellow"))
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    exe = _find_ollama_exe()
    if not exe:
        state.console.print("[bold red]Ollama not found after install.[/bold red]")
        sys.exit(1)
    return exe

def _start_ollama_server(exe: Path) -> None:
    if is_port_open():
        log("Ollama server already running.", "green")
        return
    log("Starting Ollama server...", "yellow")
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe), "serve"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw,
    )
    with state.console.status("[cyan]Waiting for Ollama...[/cyan]", spinner="dots"):
        for _ in range(40):
            if is_port_open():
                log("Ollama server ready.", "green")
                return
            time.sleep(0.5)
    state.console.print("[bold red]Ollama did not start in time.[/bold red]")
    sys.exit(1)

def _pull_model(exe: Path) -> None:
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        if any(m["name"] == OLLAMA_MODEL or m["name"] == f"{OLLAMA_MODEL}:latest" for m in data.get("models",[])):
            log(f"Model '{OLLAMA_MODEL}' available.", "green")
            return
    except Exception:
        pass

    state.console.print(Panel(f"[bold yellow]Pulling model: {OLLAMA_MODEL}[/bold yellow]",
                        border_style="yellow"))

    proc = subprocess.Popen([str(exe), "pull", OLLAMA_MODEL],
        stdout    = subprocess.PIPE,
        stderr    = subprocess.STDOUT,
        text      = True,
        encoding  = "utf-8",
        errors    = "replace",
    )

    with Progress(
        "[progress.description]{task.description}", BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=state.console, transient=True,
    ) as prog:
        task = prog.add_task("[cyan]Downloading...[/cyan]", total=100)
        for line in proc.stdout:
            try:
                obj    = json.loads(line.strip())
                tot    = obj.get("total",     0)
                done   = obj.get("completed", 0)
                status = obj.get("status",    "")[:48]
                if tot > 0:
                    prog.update(task, completed=done / tot * 100,
                                description=f"[cyan]{status}[/cyan]")
                elif status:
                    prog.update(task, description=f"[cyan]{status}[/cyan]")
            except (json.JSONDecodeError, ZeroDivisionError):
                pass

    proc.wait()
    if proc.returncode != 0:
        state.console.print("[bold red]Model pull failed.[/bold red]")
        sys.exit(1)
    log(f"Model '{OLLAMA_MODEL}' ready.", "green")

def bootstrap_ollama() -> None:
    state.console.print(Rule("[bold cyan]Initializing Ollama[/bold cyan]", style="cyan"))
    exe = _find_ollama_exe() or _install_ollama()
    _start_ollama_server(exe)
    _pull_model(exe)
    state.console.print(Rule(style="dim cyan"))