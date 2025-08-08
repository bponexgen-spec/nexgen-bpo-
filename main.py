import os
import json
import tempfile
import uuid
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import openai
import requests

app = FastAPI(title="Nexgen BPO - Voice Agent (Global White-label)")

# CORS (adjust allow_origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Load configuration from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_DEFAULT = os.getenv("ELEVENLABS_VOICE", "Bella")
SYNTHFLOW_API_URL = os.getenv("SYNTHFLOW_API_URL", "")  # optional future integration
SYNTHFLOW_API_KEY = os.getenv("SYNTHFLOW_API_KEY", "")

# Initialize OpenAI if key provided
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

SUBMISSIONS_FILE = "submissions.json"
os.makedirs("static", exist_ok=True)

# Ensure submissions file exists
if not os.path.exists(SUBMISSIONS_FILE):
    with open(SUBMISSIONS_FILE, "w") as f:
        json.dump([], f)

class Contact(BaseModel):
    name: str
    email: str
    plan: Optional[str] = None
    message: Optional[str] = None

def _load_voice_map() -> Dict[str, str]:
    """Load voice mapping from environment variables starting with VOICE_."""
    voices = {}
    for k, v in os.environ.items():
        if k.startswith("VOICE_") and v:
            lang = k.split("_", 1)[1]
            voices[lang] = v
    return voices

VOICE_MAP = _load_voice_map()

def choose_voice_for_language(lang: str) -> str:
    if not lang:
        return ELEVENLABS_VOICE_DEFAULT
    if lang in VOICE_MAP:
        return VOICE_MAP[lang]
    if '-' in lang:
        prefix = lang.split('-')[0]
        if prefix in VOICE_MAP:
            return VOICE_MAP[prefix]
    return ELEVENLABS_VOICE_DEFAULT

# -------------------- Provider wrapper functions --------------------
def run_asr_local(file_path: str, language: str = "en") -> str:
    if not OPENAI_API_KEY:
        return "[ASR not configured - set OPENAI_API_KEY]"
    try:
        with open(file_path, "rb") as audio_file:
            resp = openai.Audio.transcribe("whisper-1", audio_file, language=language)
            return resp.get("text", "")
    except Exception as e:
        return f"[ASR error: {str(e)}]"

def run_llm_local(transcript: str, language: str = "en") -> str:
    if not OPENAI_API_KEY:
        return "[LLM not configured - set OPENAI_API_KEY]"
    try:
        system_msg = {
            "role": "system",
            "content": ("You are a helpful voice assistant for Nexgen BPO. "
                        f"Always reply in the same language as the user. If the user language is '{language}', "
                        "respond in that language. Keep responses concise and professional.")
        }
        user_msg = {"role": "user", "content": f"User said (transcript): {transcript}"}
        chat = openai.ChatCompletion.create(model=OPENAI_MODEL, messages=[system_msg, user_msg], max_tokens=500)
        return chat["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM error: {str(e)}]"

def run_tts_elevenlabs(text: str, voice: str, out_path: str) -> bool:
    if not ELEVENLABS_API_KEY:
        return False
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"text": text, "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}}
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            return False
    except Exception:
        return False

@app.post("/voice-agent")
async def voice_agent(audio: UploadFile = File(...), language: Optional[str] = Form("en")):
    suffix = os.path.splitext(audio.filename)[1] or ".wav"
    tmp_name = f"/tmp/{uuid.uuid4().hex}{suffix}"
    with open(tmp_name, "wb") as tmpf:
        tmpf.write(await audio.read())

    lang = (language or "en").lower()

    transcript = run_asr_local(tmp_name, language=lang)

    if transcript and not transcript.startswith("[ASR error") and not transcript.startswith("[ASR not configured"):
        llm_response = run_llm_local(transcript, language=lang)
    else:
        llm_response = "[LLM unavailable due to ASR error or missing config]"

    chosen_voice = choose_voice_for_language(lang)
    out_filename = f"generated_{uuid.uuid4().hex}.mp3"
    out_path = os.path.join("static", out_filename)
    tts_ok = run_tts_elevenlabs(llm_response, chosen_voice, out_path)
    tts_url = f"/static/{out_filename}" if tts_ok else None

    try:
        os.remove(tmp_name)
    except:
        pass

    return JSONResponse({"transcript": transcript, "response_text": llm_response, "tts_audio_url": tts_url})

@app.post("/contact")
async def contact_submit(name: str = Form(...), email: str = Form(...), plan: str = Form(None), message: str = Form(None)):
    entry = {"name": name, "email": email, "plan": plan, "message": message}
    try:
        with open(SUBMISSIONS_FILE, "r+") as f:
            data = json.load(f)
            data.append(entry)
            f.seek(0)
            json.dump(data, f, indent=2)
        return JSONResponse({"status": "ok", "detail": "Submission received"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
