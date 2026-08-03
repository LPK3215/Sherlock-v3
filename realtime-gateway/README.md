# Sherlock Cascade Bot Server

This server supports only the Cascade pipeline:

`microphone -> STT -> VLM -> TTS -> speaker`

Camera and screen frames can be requested by the VLM through Pipecat tools.

## Start locally

Requirements: Python 3.11+ and `uv`.

```powershell
Copy-Item config.example.env .env
# Configure the selected CASCADE_* providers in .env
uv sync
.\run.ps1
```

The SmallWebRTC server listens on `http://localhost:7860`. The launcher rejects
any `AI_MODE` other than `cascade`.

The verified default uses local Whisper on CPU (`int8`) for STT and local Piper
(`zh_CN-huayan-medium`) for Chinese TTS. Only the OpenAI-compatible VLM needs an
API key; configure its `CASCADE_VLM_OPENAI_*` values in `.env`.
