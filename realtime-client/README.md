# Sherlock Cascade Client

Next.js client for the Pipecat Cascade bot, including microphone, camera,
screen sharing, transcripts, and event logs.

## Start locally

Start the server on port `7860`, then run:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000` and click **Connect**. The development proxy in
`next.config.ts` forwards SmallWebRTC signaling to the local server.

Screen sharing is available on desktop browsers only.
