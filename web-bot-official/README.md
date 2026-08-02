# Sherlock Cascade Voice/Video Bot

This project is configured for the **Cascade (级联)** pipeline only:

`Whisper STT -> OpenAI-compatible VLM -> Piper Chinese TTS`

It supports microphone conversation, camera input, desktop screen sharing,
transcripts, and event logs through Pipecat SmallWebRTC and Voice UI Kit.

## Requirements

- Node.js 18+
- Python 3.11+
- `uv`
- An API key and base URL for the selected VLM provider

STT and Chinese TTS are local with the current configuration, so they do not require
separate API keys.

## Run locally

Start the Cascade server:

```powershell
cd server
uv sync
.\run.ps1
```

In another PowerShell window, start the client:

```powershell
cd client
npm install
npm run dev
```

Open `http://localhost:3000` and click **Connect**. The server listens on port
`7860`; the client listens on port `3000`.

Configuration is stored in `server/.env`. `AI_MODE` must be `cascade`; the
server rejects `realtime` and unknown modes instead of silently trying another
API.
