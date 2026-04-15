import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import keyboard

from context import user_ctx
from utils import log

def web_search(query: str) -> str:
    """Scrapes DuckDuckGo Lite to get actual search snippets (works for news!)"""
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode('utf-8')
            
        # Extract the text snippets from the HTML results
        snippets = re.findall(r'<td class="result-snippet">(.+?)</td>', html, re.DOTALL)
        if snippets:
            # Clean out the HTML tags and join the top 3 results
            clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:3]]
            return " | ".join(clean_snippets)
            
        return "NO_RESULTS"
    except Exception as exc:
        return "NO_RESULTS"

def _launch_app(app: str) -> None:
    user_ctx.record_app_use(app)
    try:
        if sys.platform == "win32":
            os.system(f'start "" "{app}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", app])
        else:
            subprocess.Popen([app])
        log(f"Opened: {app}", "green")
    except Exception as exc:
        log(f"open '{app}' failed: {exc}", "yellow")

def _kill_app(app: str) -> None:
    try:
        if sys.platform == "win32":
            os.system(f'taskkill /IM "{app}.exe" /F 2>nul')
        else:
            os.system(f"pkill -f '{app}' 2>/dev/null")
        log(f"Closed: {app}", "green")
    except Exception as exc:
        log(f"close '{app}' failed: {exc}", "yellow")

def _open_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open_new_tab(url)
    log(f"Opened URL: {url}", "green")

def _type_text(text: str) -> None:
    try:
        keyboard.write(text, delay=0.03)
    except Exception as exc:
        log(f"type failed: {exc}", "yellow")

def _press_key(combo: str) -> None:
    try:
        keyboard.press_and_release(combo)
    except Exception as exc:
        log(f"key '{combo}' failed: {exc}", "yellow")

def _set_volume(level_str: str) -> None:
    try:
        level = int(level_str)
        if sys.platform == "win32":
            if shutil.which("nircmd"):
                os.system(f"nircmd setsysvolume {int(level * 655.35)}")
            else:
                ps = (
                    f"$vol = [math]::Round({level}/100 * 65535);"
                    f"(New-Object -ComObject WScript.Shell)."
                    f"SendKeys([char]173)"
                )
                os.system(
                    f'powershell -c "[Audio]::Volume={level/100}" 2>nul'
                )
        elif sys.platform == "darwin":
            os.system(f"osascript -e 'set volume output volume {level}'")
        else:
            os.system(f"amixer sset Master {level}%")
    except Exception as exc:
        log(f"volume failed: {exc}", "yellow")

def _take_screenshot() -> None:
    try:
        import datetime as dt
        fname = Path.home() / "Desktop" / f"lavie_screenshot_{dt.datetime.now().strftime('%H%M%S')}.png"
        if sys.platform == "win32":
            subprocess.Popen(["powershell", "-c",
                 f"Add-Type -AssemblyName System.Windows.Forms;"
                 f"[System.Windows.Forms.Screen]::PrimaryScreen |"
                 f"% {{ $bmp = New-Object System.Drawing.Bitmap($_.Bounds.Width,$_.Bounds.Height);"
                 f"$g=[System.Drawing.Graphics]::FromImage($bmp);"
                 f"$g.CopyFromScreen(0,0,0,0,$bmp.Size);"
                 f"$bmp.Save('{fname}') }}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        elif sys.platform == "darwin":
            os.system(f"screencapture '{fname}'")
        else:
            os.system(f"scrot '{fname}'")
        log(f"Screenshot → {fname}", "green")
    except Exception as exc:
        log(f"screenshot failed: {exc}", "yellow")

def execute_single_command(cmd: str) -> None:
    cmd = cmd.strip()
    if   cmd.startswith(("open:", "open_app:", "launch:")):
        _launch_app(cmd.split(":", 1)[1].strip())
    elif cmd.startswith(("close:", "close_app:", "kill:")):
        _kill_app(cmd.split(":", 1)[1].strip())
    elif cmd.startswith(("website:", "open_website:", "url:")):
        _open_url(cmd.split(":", 1)[1].strip())
    elif cmd.startswith("type:"):
        _type_text(cmd.split(":", 1)[1].strip())
    elif cmd.startswith("key:"):
        _press_key(cmd.split(":", 1)[1].strip())
    elif cmd.startswith("volume:"):
        _set_volume(cmd.split(":", 1)[1].strip())
    elif cmd == "screenshot":
        _take_screenshot()
    elif cmd.startswith("learn:"):
        note = cmd.split(":", 1)[1].strip()
        user_ctx.add_note(note)
        log(f"Learned: {note}", "green")
    elif cmd == "close_dialogue":
        pass
    else:
        log(f"Unknown command: {cmd}", "red")