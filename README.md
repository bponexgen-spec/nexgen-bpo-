# Nexgen BPO — Global White-label Voice Agent (Render-ready)

This package is a **global, multilingual, white-label** voice agent pilot built with FastAPI.
It's provider-agnostic through wrapper functions so you can swap ASR/LLM/TTS providers later (e.g., Synthflow).
This is ready to deploy to Render or any Python-hosting service.

## What's included
- `main.py` — FastAPI app with provider wrappers (ASR, LLM, TTS).
- `static/` — frontend (index.html, style.css, script.js).
- `requirements.txt`, `Procfile`, `.env.example`, `README.md`.

## How it works (high level)
1. Frontend records audio and posts to `/voice-agent` with `language` (ISO code, e.g., en, nl, fr).
2. Server runs ASR -> LLM -> TTS using wrappers:
   - ASR: OpenAI Whisper by default (OpenAI key required).
   - LLM: OpenAI Chat by default (model configurable via OPENAI_MODEL).
   - TTS: ElevenLabs by default (voice per-language configurable via VOICE_<lang> env vars).
3. The response includes `transcript`, `response_text`, and a `tts_audio_url` to play the generated audio.

## Deployment (Render)
1. Create a Web Service (Python) on Render.
2. Upload this repo as a zip (or push to a Git repo and connect Render).
3. Set environment variables (use `.env.example` as reference):
   - `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `VOICE_en`, `VOICE_nl`, etc.
4. Start command is taken from Procfile: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## White-label notes
- Customize branding via environment variables or by editing `static/index.html` (logo, brand name).
- To create a per-client deployment, copy the repo, set client-specific env vars (voice, brand), and deploy a separate instance.
- For Synthflow integration, set `SYNTHFLOW_API_URL` and `SYNTHFLOW_API_KEY` and implement the provider call inside the respective wrapper functions in `main.py`.

## Testing locally
- Create a virtualenv, install `pip install -r requirements.txt`.
- Copy `.env.example` to `.env` and fill in API keys and voices.
- Run `uvicorn main:app --reload --port 8000` and open `http://localhost:8000`