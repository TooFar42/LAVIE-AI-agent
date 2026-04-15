# LAVIE - Local AI Voice Interactive Engine

LAVIE is a fast, completely local, voice-activated system agent designed to enhance the desktop computer experience. Instead of acting as a simple chatbot, LAVIE bridges the gap between natural conversation and physical computer control, allowing users to interact with their system securely and hands-free.

Because LAVIE runs entirely on-device, it guarantees absolute privacy, lightning-fast response times, and zero reliance on cloud subscriptions.

## 🧠 Core Architecture
LAVIE is built on a highly optimized, fully local AI stack:
* **LLM Engine**: Runs `qwen3.5:2b` via **Ollama** for incredibly fast, on-device reasoning and command generation.
* **ASR (Speech-to-Text)**: Uses **Faster-Whisper** (`small.en`) running directly in RAM (no temporary files) for instant transcription, paired with precise Voice Activity Detection (VAD).
* **TTS (Text-to-Speech)**: Powered by **Kokoro-ONNX** for high-quality, human-like voice synthesis, with an automatic fallback to Windows SAPI5.

## ✨ Key Features

### 🎙️ Seamless Voice Interaction
* **Passive Wake-Word**: Constantly listens for wake phrases like *"Hey LAVIE"* without recording to disk.
* **Push-to-Talk Hotkey**: Hold `Ctrl+Space` for instant activation without needing a wake word.
* **Smart Dialogue State**: Keeps the conversation open naturally and automatically goes back to sleep after 10 seconds of silence or when dismissed (e.g., *"Goodbye LAVIE"*).

### 💻 Deep System Control
LAVIE interprets natural language and translates it into direct system actions:
* **App Management**: Open and close software (`"Open Microsoft Edge"`, `"Close Chrome"`).
* **Keyboard & Typing**: Simulate keystrokes (`"Press Ctrl+C"`) or type entire sentences.
* **System Utilities**: Adjust master system volume natively and take instant desktop screenshots.
* **Web Browsing**: Open specific URLs directly in the default browser.

### 🌐 Smart Web Searching
* **Real-time Scraping**: If asked for news or facts, LAVIE silently scrapes DuckDuckGo Lite to read the latest headlines and summaries out loud.
* **Visual Context**: Whenever a search is performed, LAVIE automatically opens a browser tab with the search results so the user can follow along visually while she speaks.

### 🗂️ Persistent User Context
LAVIE maintains a local memory file (`~/.lavie/context.json`) to provide a personalized experience:
* Tracks which applications you use most frequently.
* Learns your name and specific preferences (e.g., *"Learn that I prefer dark mode"*).
* Remembers topics you frequently discuss to contextualize future conversations.
* Maintains a rolling chat history so multi-turn conversations flow naturally.

## ⚙️ How It Works (Under the Hood)
LAVIE uses a highly strict XML-based prompting system. To prevent the LLM from "speaking code" out loud, the system strictly parses responses into two distinct blocks:
1. `<raw>`: Invisible to the user. Contains direct system commands (e.g., `open: msedge`, `volume: 50`).
2. `<speak>`: The natural language response that is piped directly into the Text-to-Speech engine.

Additionally, a custom parser brutally strips away `<think>` tags and internal monologues, ensuring the tiny 2-Billion parameter LLM executes tasks instantly without getting distracted by its own reasoning processes. 

## 📦 Requirements & Dependencies
* Python 3.12+
* **Ollama** (Automatically bootstraps and installs via the script if missing)
* **Libraries**: `numpy`, `sounddevice`, `faster-whisper`, `kokoro-onnx`, `keyboard`, `rich`
* **Hardware**: Tested on CUDA-enabled GPUs for optimal Whisper/Kokoro performance, but fully capable of running on standard CPUs via quantized ONNX/Int8 fallback.
