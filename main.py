import os
import re
import wave
import numpy as np
import keyboard
import sounddevice as sd
import torch
import urllib.request
from nemo.collections.asr.models import ASRModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# --- 1. DEVICE SETUP ---
if torch.cuda.is_available():
    DEVICE = "cuda"
    DTYPE = torch.float16
    print(f"--- NVIDIA GPU DETECTED ---")
else:
    DEVICE = "cpu"
    DTYPE = torch.float32
    print("--- System initialized on: CPU ---")


# --- 2. KOKORO ASSET DOWNLOADER (ONNX SPECIFIC) ---
def setup_kokoro():
    print("Checking Kokoro ONNX files...")
    model_file = "kokoro-v1.0.onnx"
    voices_file = "voices-v1.0.bin"

    model_url = f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{model_file}"
    voices_url = f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{voices_file}"

    try:
        if not os.path.exists(model_file):
            print(f"Downloading {model_file} (this may take a moment)...")
            urllib.request.urlretrieve(model_url, model_file)

        if not os.path.exists(voices_file):
            print(f"Downloading {voices_file}...")
            urllib.request.urlretrieve(voices_url, voices_file)

        print("[✅] Kokoro ONNX assets ready.")
        return model_file, voices_file
    except Exception as e:
        print(f"[❌] Download Failed: {e}")
        local_onnx = [f for f in os.listdir('.') if f.endswith('.onnx')]
        local_bin = [f for f in os.listdir('.') if f.endswith('.bin')]
        if local_onnx and local_bin:
            print(f"[!] Using local file: {local_onnx[0]} and {local_bin[0]}")
            return local_onnx[0], local_bin[0]
        return None, None


model_file, voices_file = setup_kokoro()

# --- 3. MODEL INITIALIZATION ---
print(f"Loading Ears (ASR) to {DEVICE}...")
stt_model = ASRModel.from_pretrained("nvidia/stt_en_conformer_ctc_small").to(DEVICE)
if DEVICE == "cuda": stt_model.half()

print(f"Loading Brain (LLM) to {DEVICE}...")
model_id = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
llm_model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=DTYPE,
    device_map="auto" if DEVICE == "cuda" else None,
).to(DEVICE)

print("Loading Voice Engine...")
try:
    from kokoro_onnx import Kokoro

    if not model_file or not os.path.exists(model_file):
        raise FileNotFoundError("Model file missing after download attempt.")

    tts = Kokoro(model_file, voices_file)
    tts_mode = "kokoro"
    print(">> Kokoro Voice Ready.")
except Exception as e:
    import pyttsx3

    print(f"\n[!] Kokoro failed: {e}")
    engine = pyttsx3.init()
    tts_mode = "sapi5"
    print(">> Falling back to Windows SAPI5.")


# --- 4. ENGINE FUNCTIONS ---
def speak(text):
    if not text: return
    clean_text = re.sub(r'<\|.*?\|>', '', text).strip()
    clean_text = clean_text.replace('*', '').replace('#', '')

    if tts_mode == "kokoro":
        try:
            samples, sample_rate = tts.create(clean_text, voice="af_bella", speed=1.1, lang="en-us")
            sd.play(samples, sample_rate)
            sd.wait()
        except Exception as e:
            print(f"Audio Playback Error: {e}")
    else:
        engine.say(clean_text)
        engine.runAndWait()


# --- 5. MAIN LOOP ---
def run_assistant():
    print(f"\n=== ASSISTANT ACTIVE ON {DEVICE.upper()} ===")
    print("Hold [Ctrl + Space] to speak. Press[Ctrl + C] to stop script.")

    while True:
        try:
            if keyboard.is_pressed('ctrl+space'):
                print("\n[Listening...]")
                fs = 16000
                recording = []

                with sd.InputStream(samplerate=fs, channels=1, dtype='int16') as stream:
                    while keyboard.is_pressed('ctrl+space'):
                        data, _ = stream.read(1024)
                        recording.append(data)

                if len(recording) < 10: continue

                print("[Processing...]")
                audio_data = np.concatenate(recording, axis=0)
                temp_file = "input.wav"
                with wave.open(temp_file, "wb") as wf:
                    wf.setnchannels(1);
                    wf.setsampwidth(2);
                    wf.setframerate(fs)
                    wf.writeframes(audio_data.tobytes())

                res = stt_model.transcribe([temp_file], verbose=False)

                if isinstance(res, tuple):
                    transcription = res[0][0] if len(res[0]) > 0 else ""
                else:
                    transcription = res[0] if isinstance(res, list) else str(res)

                if not transcription or len(transcription.strip()) < 2:
                    print("... (no speech detected)")
                    continue

                print(f"You: {transcription}")

                messages = [
                    {"role": "system",
                     "content": "You are a concise, helpful assistant. Avoid markdown and special characters."},
                    {"role": "user", "content": transcription}
                ]
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

                inputs = tokenizer([prompt], return_tensors="pt").to(DEVICE)
                outputs = llm_model.generate(**inputs, max_new_tokens=60, pad_token_id=tokenizer.eos_token_id)
                response = tokenizer.decode(outputs[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True)

                print(f"AI: {response}")
                speak(response)

        except Exception as e:
            print(f"Loop error: {e}")


if __name__ == "__main__":
    run_assistant()
