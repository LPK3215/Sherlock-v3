import assert from "node:assert/strict";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";

const API_URL = process.env.E2E_API_URL || "http://api:5050";
const CLIENT_HOST = process.env.E2E_CLIENT_HOST || "user-app";
const CLIENT_PORT = Number(process.env.E2E_CLIENT_PORT || "3000");
const ACCESS_TOKEN = process.env.E2E_ACCESS_TOKEN || "";
const PLAYWRIGHT_MODULE =
  process.env.PLAYWRIGHT_MODULE || "/work/node_modules/playwright-core/index.js";
const VISION_MODEL =
  process.env.E2E_VISION_MODEL || "modelscope:Qwen/Qwen3-VL-8B-Thinking";
const STT_FIXTURE_PATH = process.env.E2E_STT_FIXTURE || "/fixtures/sherlock-stt-e2e.wav";
const ARTIFACT_DIR = process.env.E2E_ARTIFACT_DIR || "/artifacts";
const TIMEOUT_MS = Number(process.env.E2E_REALTIME_TIMEOUT_MS || "180000");

assert(ACCESS_TOKEN, "E2E_ACCESS_TOKEN is required");
assert(VISION_MODEL.includes(":"), "E2E_VISION_MODEL must use provider:model format");
assert(fs.existsSync(STT_FIXTURE_PATH), `STT fixture does not exist: ${STT_FIXTURE_PATH}`);

const playwright = await import(PLAYWRIGHT_MODULE);
const chromium = playwright.chromium || playwright.default?.chromium;
assert(chromium, `Chromium is not exported by ${PLAYWRIGHT_MODULE}`);
const authHeaders = { Authorization: `Bearer ${ACCESS_TOKEN}` };
const providerId = VISION_MODEL.slice(0, VISION_MODEL.indexOf(":"));
const modelId = VISION_MODEL.slice(VISION_MODEL.indexOf(":") + 1);
const agentSlug = `realtime-vision-e2e-${Date.now()}`;
const sttAudioBase64 = fs.readFileSync(STT_FIXTURE_PATH).toString("base64");

let browser;
let page;
let providerModels;
let providerChanged = false;
let agentCreated = false;
let proxy;

async function api(pathname, options = {}) {
  const response = await fetch(`${API_URL}${pathname}`, {
    ...options,
    headers: {
      ...authHeaders,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`${options.method || "GET"} ${pathname} failed (${response.status})`);
  }
  return payload;
}

async function updateProviderModels(enabledModels) {
  await api(`/api/system/model-providers/${providerId}`, {
    method: "PUT",
    body: JSON.stringify({ enabled_models: enabledModels }),
  });
}

async function waitForModel(expected) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const payload = await api("/api/system/model-providers/models/v2?model_type=chat");
    const models = payload.data?.[providerId]?.models || [];
    if (models.some((model) => model.spec === VISION_MODEL) === expected) return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Model cache did not become ${expected ? "ready" : "restored"}`);
}

async function createAgent() {
  const me = await api("/api/auth/me");
  assert(me.uid, "Current user response is missing uid");

  const response = await api("/api/agent", {
    method: "POST",
    body: JSON.stringify({
      name: `Realtime Vision E2E ${agentSlug.slice(-8)}`,
      slug: agentSlug,
      backend_id: "ChatbotAgent",
      description: "Docker realtime browser E2E temporary agent",
      config_json: {
        context: {
          model: VISION_MODEL,
          system_prompt: [
            "You are a deterministic realtime end-to-end test assistant.",
            "For a camera request, call capture_live_camera and answer only with the uppercase words and digits visible in the image.",
            "For a shared-screen request, call capture_live_screen and answer only with the uppercase words and digits visible in the image.",
            "For a text/TTS check, answer exactly TEXT TTS OK 308.",
            "When the user says 'You are right.', answer exactly STT AUDIO OK 614.",
            "For an interruption check, answer exactly INTERRUPT OK 527.",
            "Do not call tools unless the request needs a camera image or a shared-screen image.",
          ].join(" "),
          tools: [],
          knowledges: [],
          mcps: [],
          skills: [],
          subagents: [],
          model_retry_times: 0,
        },
      },
      share_config: {
        access_level: "user",
        department_ids: [],
        user_uids: [me.uid],
      },
    }),
  });
  assert.equal(response.agent?.slug, agentSlug);
}

async function startLoopbackProxy() {
  const server = net.createServer((client) => {
    const upstream = net.connect({ host: CLIENT_HOST, port: CLIENT_PORT });
    client.on("error", () => upstream.destroy());
    upstream.on("error", () => client.destroy());
    client.pipe(upstream).pipe(client);
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(3000, "127.0.0.1", resolve);
  });
  return server;
}

async function installMediaFixtures(context) {
  await context.addInitScript(
    ({ accessToken, selectedAgent, audioBase64 }) => {
      localStorage.setItem("user_token", accessToken);
      localStorage.setItem("realtime_agent_slug", selectedAgent);

      const peerConnections = [];
      const NativePeerConnection = window.RTCPeerConnection;
      window.RTCPeerConnection = new Proxy(NativePeerConnection, {
        construct(target, args) {
          const connection = Reflect.construct(target, args);
          peerConnections.push(connection);
          return connection;
        },
      });

      const audioContext = new AudioContext({ sampleRate: 48000 });
      const audioDestination = audioContext.createMediaStreamDestination();
      const silence = audioContext.createConstantSource();
      silence.offset.value = 0;
      silence.connect(audioDestination);
      silence.start();

      const makeCanvas = (background, label, footer) => {
        const canvas = document.createElement("canvas");
        canvas.width = 1280;
        canvas.height = 720;
        const draw = () => {
          const drawing = canvas.getContext("2d");
          drawing.fillStyle = background;
          drawing.fillRect(0, 0, canvas.width, canvas.height);
          drawing.fillStyle = "white";
          drawing.font = "bold 92px sans-serif";
          drawing.textAlign = "center";
          drawing.fillText(label, 640, 340);
          drawing.font = "bold 56px sans-serif";
          drawing.fillText(footer, 640, 440);
        };
        draw();
        const timer = setInterval(draw, 100);
        return { canvas, timer, track: canvas.captureStream(10).getVideoTracks()[0] };
      };

      const camera = makeCanvas("#b91c1c", "CAMERA RED 742", "229");
      const screen = makeCanvas("#15803d", "SCREEN GREEN 915", "431");
      const fixtures = { audioContext, audioDestination, camera, peerConnections, screen, silence };
      window.__realtimeE2E = fixtures;

      const mediaStream = (constraints, videoTrack, cloneVideo = true) => {
        const stream = new MediaStream();
        if (constraints?.audio) stream.addTrack(audioDestination.stream.getAudioTracks()[0].clone());
        if (constraints?.video) stream.addTrack(cloneVideo ? videoTrack.clone() : videoTrack);
        return stream;
      };

      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: async (constraints) => mediaStream(constraints, camera.track),
      });
      Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
        configurable: true,
        value: async (constraints = { video: true }) => mediaStream(constraints, screen.track, false),
      });

      window.__playSttFixture = async () => {
        await audioContext.resume();
        const bytes = Uint8Array.from(atob(audioBase64), (char) => char.charCodeAt(0));
        const decoded = await audioContext.decodeAudioData(bytes.buffer.slice(0));
        const source = audioContext.createBufferSource();
        source.buffer = decoded;
        source.connect(audioDestination);
        source.start();
        await new Promise((resolve) => {
          source.onended = resolve;
        });
      };

      window.__inboundAudioBytes = async () => {
        let bytes = 0;
        const connection = peerConnections.at(-1);
        if (!connection) return bytes;
        {
          for (const receiver of connection.getReceivers()) {
            if (receiver.track?.kind !== "audio") continue;
            const stats = await receiver.getStats();
            for (const report of stats.values()) {
              if (report.type === "inbound-rtp" && report.kind === "audio") {
                bytes += Number(report.bytesReceived || 0);
              }
            }
          }
        }
        return bytes;
      };

      window.__outboundVideoStats = async () => {
        const result = [];
        const connection = peerConnections.at(-1);
        if (!connection) return result;
        {
          let videoIndex = 0;
          for (const sender of connection.getSenders()) {
            if (sender.track?.kind !== "video") continue;
            const stats = await sender.getStats();
            for (const report of stats.values()) {
              if (report.type === "outbound-rtp" && report.kind === "video") {
                result.push({
                  videoIndex,
                  trackId: sender.track.id,
                  screenTrackId: screen.track.id,
                  bytesSent: Number(report.bytesSent || 0),
                  framesEncoded: Number(report.framesEncoded || 0),
                });
              }
            }
            videoIndex += 1;
          }
        }
        return result;
      };

      const summarizeSdp = (description) => {
        if (!description?.sdp) return [];
        return description.sdp.split(/\r\nm=/).map((section, index) => {
          const lines = `${index === 0 ? "" : "m="}${section}`.split(/\r\n/);
          return lines.filter(
            (line, lineIndex) =>
              lineIndex === 0 ||
              /^a=(mid:|extmap:|sendrecv$|sendonly$|recvonly$|inactive$|msid:|ssrc:)/.test(line),
          );
        });
      };

      window.__peerConnectionDiagnostics = async () => {
        const result = [];
        for (const connection of peerConnections) {
          const transceivers = [];
          for (const [index, transceiver] of connection.getTransceivers().entries()) {
            const stats = await transceiver.sender.getStats();
            const outbound = [...stats.values()]
              .filter((report) => report.type === "outbound-rtp")
              .map((report) => ({
                bytesSent: Number(report.bytesSent || 0),
                framesEncoded: Number(report.framesEncoded || 0),
                kind: report.kind,
                ssrc: report.ssrc,
              }));
            transceivers.push({
              index,
              mid: transceiver.mid,
              direction: transceiver.direction,
              currentDirection: transceiver.currentDirection,
              senderTrackId: transceiver.sender.track?.id,
              senderTrackState: transceiver.sender.track?.readyState,
              outbound,
            });
          }
          result.push({
            connectionState: connection.connectionState,
            signalingState: connection.signalingState,
            transceivers,
            localSdp: summarizeSdp(connection.localDescription),
            remoteSdp: summarizeSdp(connection.remoteDescription),
          });
        }
        return result;
      };
    },
    { accessToken: ACCESS_TOKEN, selectedAgent: agentSlug, audioBase64: sttAudioBase64 },
  );
}

async function sendText(text) {
  const input = page.locator('input[placeholder="发送消息"]');
  await input.fill(text);
  await input.press("Enter");
}

async function waitForAssistant(expected) {
  await page.waitForFunction(
    (value) =>
      [...document.querySelectorAll(".message:not(.message-user) p")].some((node) =>
        node.textContent?.includes(value),
      ),
    expected,
    { timeout: TIMEOUT_MS },
  );
}

async function waitForRunStarted(afterCount) {
  await page.waitForFunction(
    (count) =>
      document.querySelectorAll('.event-agent-row[data-event-type="run.started"]').length > count,
    afterCount,
    { timeout: TIMEOUT_MS },
  );
  const runId = await page
    .locator('.event-agent-row[data-event-type="run.started"]')
    .last()
    .getAttribute("data-run-id");
  assert(runId, "run.started event is missing data-run-id");
  return runId;
}

async function runStartedCount() {
  return page.locator('.event-agent-row[data-event-type="run.started"]').count();
}

async function waitForRunStatus(runId, expected) {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    const payload = await api(`/api/agent/runs/${runId}`);
    const status = payload.run?.status;
    if (status === expected) return;
    if (["completed", "failed", "cancelled", "interrupted"].includes(status)) {
      throw new Error(`Run ${runId} ended as ${status}, expected ${expected}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Run ${runId} did not reach ${expected}`);
}

try {
  const provider = await api(`/api/system/model-providers/${providerId}`);
  providerModels = provider.data?.enabled_models || [];
  if (!providerModels.some((model) => model.id === modelId)) {
    await updateProviderModels([
      ...providerModels,
      { id: modelId, type: "chat", display_name: modelId },
    ]);
    providerChanged = true;
  }
  await waitForModel(true);
  console.log(JSON.stringify({ milestone: "model-ready" }));

  await createAgent();
  agentCreated = true;
  console.log(JSON.stringify({ milestone: "fixture-ready" }));

  proxy = await startLoopbackProxy();
  browser = await chromium.launch({
    headless: true,
    args: [
      "--autoplay-policy=no-user-gesture-required",
      "--disable-dev-shm-usage",
      "--no-sandbox",
    ],
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await installMediaFixtures(context);
  page = await context.newPage();
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  assert.equal(await page.evaluate(() => window.isSecureContext), true);
  await page.getByRole("button", { name: "进入通话" }).click();
  await page.locator("button.start-call-action").click();
  await page.waitForFunction(
    () => document.querySelector(".connection-badge")?.textContent?.includes("AI 已接通"),
    undefined,
    { timeout: 60000 },
  );
  await page.waitForFunction(
    () =>
      window.__outboundVideoStats().then((stats) =>
        stats.some(
          (item) =>
            item.videoIndex === 0 &&
            item.bytesSent > 10000 &&
            item.framesEncoded > 10,
        ),
      ),
    undefined,
    { timeout: 30000 },
  );
  console.log(
    JSON.stringify({
      milestone: "screen-sender-ready",
      diagnostics: await page.evaluate(() => window.__peerConnectionDiagnostics()),
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 3000));
  await page.waitForFunction(
    () =>
      window.__outboundVideoStats().then((stats) =>
        stats.some(
          (item) =>
            item.videoIndex === 0 &&
            item.bytesSent > 10000 &&
            item.framesEncoded > 10,
        ),
      ),
    undefined,
    { timeout: 30000 },
  );
  console.log(JSON.stringify({ milestone: "webrtc-ready" }));

  await sendText("调用摄像头工具读取画面中央的英文和数字，只回答看到的内容。");
  await waitForAssistant("CAMERA RED 742");
  console.log(JSON.stringify({ check: "camera", status: "passed" }));

  await page.locator('button[data-tooltip="共享屏幕"]').click();
  await page.locator('button[data-tooltip="停止共享"]').waitFor({ timeout: 30000 });
  await page.waitForFunction(
    () =>
      window.__outboundVideoStats().then((stats) =>
        stats.some(
          (item) =>
            item.videoIndex === 1 &&
            item.trackId === item.screenTrackId,
        ),
      ),
    undefined,
    { timeout: 30000 },
  );
  console.log(
    JSON.stringify({
      milestone: "screen-sharing-ready",
      diagnostics: await page.evaluate(() => window.__peerConnectionDiagnostics()),
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 3000));
  await page.waitForFunction(
    () =>
      window.__outboundVideoStats().then((stats) =>
        stats.some(
          (item) =>
            item.videoIndex === 1 &&
            item.trackId === item.screenTrackId,
        ),
      ),
    undefined,
    { timeout: 30000 },
  );
  await sendText("调用共享屏幕工具读取画面中央的英文和数字，只回答看到的内容。");
  await waitForAssistant("SCREEN GREEN 915");
  await page.waitForFunction(
    () =>
      window.__outboundVideoStats().then((stats) =>
        stats.some(
          (item) =>
            item.videoIndex === 1 &&
            item.trackId === item.screenTrackId &&
            item.bytesSent > 10000 &&
            item.framesEncoded > 10,
        ),
      ),
    undefined,
    { timeout: 30000 },
  );
  console.log(JSON.stringify({ check: "screen", status: "passed" }));

  const audioBefore = await page.evaluate(() => window.__inboundAudioBytes());
  await sendText("这是文字和语音合成检查。只回答 TEXT TTS OK 308。");
  await waitForAssistant("TEXT TTS OK 308");
  await page.waitForFunction(
    (minimum) => window.__inboundAudioBytes().then((bytes) => bytes > minimum + 1000),
    audioBefore,
    { timeout: 60000 },
  );
  console.log(JSON.stringify({ check: "text-tts", status: "passed" }));

  await page.evaluate(() => window.__playSttFixture());
  await waitForAssistant("STT AUDIO OK 614");
  console.log(JSON.stringify({ check: "stt", status: "passed" }));

  await page.waitForFunction(() => !document.querySelector(".assistant-activity"), undefined, {
    timeout: TIMEOUT_MS,
  });
  const startedBefore = await runStartedCount();
  await sendText("再次调用摄像头工具，并详细说明画面中的所有内容。");
  const interruptedRunId = await waitForRunStarted(startedBefore);
  await sendText("中断上一条请求。只回答 INTERRUPT OK 527。");
  await waitForAssistant("INTERRUPT OK 527");
  await waitForRunStatus(interruptedRunId, "cancelled");
  console.log(JSON.stringify({ check: "barge-in", status: "passed" }));

  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  await page.getByTitle("事件日志").click();
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, "realtime-browser-e2e.png"),
    fullPage: true,
  });
  console.log(JSON.stringify({ status: "passed" }));
} catch (error) {
  if (page) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    await page
      .screenshot({ path: path.join(ARTIFACT_DIR, "realtime-browser-e2e-failed.png"), fullPage: true })
      .catch(() => undefined);
  }
  throw error;
} finally {
  await browser?.close().catch(() => undefined);
  await new Promise((resolve) => proxy?.close(resolve) || resolve());
  if (agentCreated) {
    await api(`/api/agent/${agentSlug}`, { method: "DELETE" }).catch(() => undefined);
  }
  if (providerChanged && providerModels) {
    await updateProviderModels(providerModels).catch(() => undefined);
    await waitForModel(false).catch(() => undefined);
  }
}
