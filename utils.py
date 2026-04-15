import re
import socket
import urllib.request
from pathlib import Path

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

import state

def log(msg: str, style: str = "dim white") -> None:
    state.console.log(f"[{style}]{msg}[/{style}]")

def clean_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*",          "", text, flags=re.DOTALL)
    text = re.sub(r"<\|.*?\|>",          "", text)
    text = re.sub(r"</?(?:raw|speak|cmd)>", "", text)
    return text.replace("*","").replace("#","").replace("_","").strip()

def is_port_open(host: str = "127.0.0.1", port: int = 11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False

def rich_download(url: str, dest: Path, label: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
        total = int(resp.getheader("Content-Length", 0))
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(), DownloadColumn(),
            TransferSpeedColumn(), TimeRemainingColumn(),
            console=state.console, transient=True,
        ) as prog:
            task = prog.add_task(f"[cyan]{label}[/cyan]", total=total or None)
            done = 0
            while True:
                chunk = resp.read(16384)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total > 0:
                    prog.update(task, completed=done)