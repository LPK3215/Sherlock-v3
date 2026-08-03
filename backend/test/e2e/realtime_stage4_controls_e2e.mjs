import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";

const API_URL = process.env.E2E_API_URL || "http://api:5050";
const CLIENT_HOST = process.env.E2E_CLIENT_HOST || "realtime-client";
const CLIENT_PORT = Number(process.env.E2E_CLIENT_PORT || "3000");
const ACCESS_TOKEN = process.env.E2E_ACCESS_TOKEN || "";
const PLAYWRIGHT_MODULE =
  process.env.PLAYWRIGHT_MODULE || "/work/node_modules/playwright-core/index.js";
const CHAT_MODEL =
  process.env.E2E_CHAT_MODEL || "siliconflow-cn:Qwen/Qwen3-VL-8B-Instruct";
const STT_FIXTURE_PATH = process.env.E2E_STT_FIXTURE || "/fixtures/sherlock-stt-e2e.wav";
const TIMEOUT_MS = Number(process.env.E2E_REALTIME_TIMEOUT_MS || "180000");
const LOCAL_STOP_LIMIT_MS = 500;
const EFFECT_RESPONSE_DELAY_MS = 8000;

assert(ACCESS_TOKEN, "E2E_ACCESS_TOKEN is required");
assert(CHAT_MODEL.includes(":"), "E2E_CHAT_MODEL must use provider:model format");
assert(fs.existsSync(STT_FIXTURE_PATH), `STT fixture does not exist: ${STT_FIXTURE_PATH}`);

const playwright = await import(PLAYWRIGHT_MODULE);
const chromium = playwright.chromium || playwright.default?.chromium;
assert(chromium, `Chromium is not exported by ${PLAYWRIGHT_MODULE}`);

const authHeaders = { Authorization: `Bearer ${ACCESS_TOKEN}` };
const providerId = CHAT_MODEL.slice(0, CHAT_MODEL.indexOf(":"));
const modelId = CHAT_MODEL.slice(CHAT_MODEL.indexOf(":") + 1);
const suffix = Date.now().toString(36);
const agentSlug = `realtime-stage4-e2e-${suffix}`;
const mcpSlug = `realtime-stage4-effect-${suffix}`;
const sideEffectMarker = `STAGE4_SIDE_EFFECT_${suffix}`;
const sttAudioBase64 = fs.readFileSync(STT_FIXTURE_PATH).toString("base64");

let agentCreated = false;
let browser;
let effectServer;
let mcpCreated = false;
let page;
let providerChanged = false;
let providerModels;
let proxy;
const effects = [];

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
    if (models.some((model) => model.spec === CHAT_MODEL) === expected) return;
    await delay(1000);
  }
  throw new Error(`Model cache did not become ${expected ? "ready" : "restored"}`);
}

async function createMcpServer() {
  const mcpServerCode = [
    "import json",
    "from urllib.request import Request, urlopen",
    "from mcp.server.fastmcp import FastMCP",
    "server = FastMCP('stage4-side-effect')",
    "@server.tool()",
    "def stage4_side_effect(marker: str) -> str:",
    "    request = Request(",
    "        'http://realtime-stage4-e2e:3001/effect',",
    "        data=json.dumps({'marker': marker}).encode('utf-8'),",
    "        headers={'Content-Type': 'application/json'},",
    "        method='POST',",
    "    )",
    "    with urlopen(request, timeout=30) as response:",
    "        return response.read().decode('utf-8')",
    "server.run(transport='stdio')",
  ].join("\n");

  await api("/api/system/mcp-servers", {
    method: "POST",
    body: JSON.stringify({
      slug: mcpSlug,
      name: `Stage 4 side effect ${suffix}`,
      transport: "stdio",
      command: "python",
      args: ["-c", mcpServerCode],
      description: "Temporary stage 4 cancellation E2E server",
    }),
  });
  mcpCreated = true;

  const testResult = await api(`/api/system/mcp-servers/${mcpSlug}/test`, {
    method: "POST",
  });
  assert.equal(testResult.tool_count, 1);
}

async function createAgent() {
  const me = await api("/api/auth/me");
  assert(me.uid, "Current user response is missing uid");

  const response = await api("/api/agent", {
    method: "POST",
    body: JSON.stringify({
      name: `Realtime Stage 4 E2E ${suffix.slice(-6)}`,
      slug: agentSlug,
      backend_id: "ChatbotAgent",
      description: "Stage 4 interruption controls browser E2E temporary agent",
      config_json: {
        context: {
          model: CHAT_MODEL,
          system_prompt: [
            "Follow this deterministic stage 4 test protocol exactly.",
            "For STAGE4_LONG_BARGE, immediately write 160 numbered sentences of at least twelve words each and do not stop early.",
            "For STAGE4_ASK_APPROVAL, call ask_user_question exactly once with questions=[{\"question_id\":\"voice_approval\",\"question\":\"Approve the stage 4 voice release?\",\"options\":[{\"label\":\"Approve\",\"value\":\"approve\"},{\"label\":\"Reject\",\"value\":\"reject\"}],\"multi_select\":false,\"allow_other\":true}].",
            "After ask_user_question returns any spoken answer, answer exactly VOICE APPROVAL RESUME OK 418.",
            `For STAGE4_RUN_SIDE_EFFECT, call stage4_side_effect exactly once with marker=${sideEffectMarker}, then answer exactly SIDE EFFECT FINISHED 592.`,
            "For a standalone user message meaning You are right, answer exactly VOICE FOLLOWUP OK 731.",
            "Do not call any tool except when these rules explicitly require it.",
          ].join(" "),
          tools: ["ask_user_question"],
          knowledges: [],
          mcps: [mcpSlug],
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
      is_subagent: false,
    }),
  });
  assert.equal(response.agent?.slug, agentSlug);
  agentCreated = true;
}

async function startEffectServer() {
  const server = http.createServer((request, response) => {
    if (request.method !== "POST" || request.url !== "/effect") {
      response.writeHead(404).end();
      return;
    }

    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      const payload = JSON.parse(body);
      effects.push({ marker: payload.marker, receivedAt: Date.now() });
      setTimeout(() => {
        if (response.destroyed) return;
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify({ marker: payload.marker, accepted: true }));
      }, EFFECT_RESPONSE_DELAY_MS);
    });
    response.on("error", () => undefined);
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(3001, "0.0.0.0", resolve);
  });
  return server;
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

async function installSession(context) {
  await context.addInitScript(
    ({ accessToken, audioBase64, selectedAgent }) => {
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

      const bytes = Uint8Array.from(atob(audioBase64), (char) => char.charCodeAt(0));
      const audioBuffer = audioContext.decodeAudioData(bytes.buffer.slice(0));
      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 360;
      const draw = () => {
        const drawing = canvas.getContext("2d");
        drawing.fillStyle = "black";
        drawing.fillRect(0, 0, canvas.width, canvas.height);
      };
      draw();
      const timer = setInterval(draw, 100);
      const videoTrack = canvas.captureStream(10).getVideoTracks()[0];
      const fixtures = {
        audioBuffer,
        audioContext,
        audioDestination,
        canvas,
        lastFixtureEnded: Promise.resolve(),
        peerConnections,
        silence,
        timer,
        videoTrack,
      };
      window.__stage4E2E = fixtures;

      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: async (constraints) => {
          const stream = new MediaStream();
          if (constraints?.audio) {
            stream.addTrack(audioDestination.stream.getAudioTracks()[0].clone());
          }
          if (constraints?.video) stream.addTrack(videoTrack.clone());
          return stream;
        },
      });

      window.__startVoiceFixture = async () => {
        await audioContext.resume();
        const source = audioContext.createBufferSource();
        source.buffer = await audioBuffer;
        source.connect(audioDestination);
        const ended = new Promise((resolve) => {
          source.onended = resolve;
        });
        fixtures.lastFixtureEnded = ended;
        const startedAt = performance.now();
        source.start();
        return startedAt;
      };

      window.__awaitVoiceFixture = () => fixtures.lastFixtureEnded;
      window.__inboundAudioBytes = async () => {
        let inboundBytes = 0;
        const connection = peerConnections.at(-1);
        if (!connection) return inboundBytes;
        for (const receiver of connection.getReceivers()) {
          if (receiver.track?.kind !== "audio") continue;
          const stats = await receiver.getStats();
          for (const report of stats.values()) {
            if (report.type === "inbound-rtp" && report.kind === "audio") {
              inboundBytes += Number(report.bytesReceived || 0);
            }
          }
        }
        return inboundBytes;
      };
    },
    { accessToken: ACCESS_TOKEN, audioBase64: sttAudioBase64, selectedAgent: agentSlug },
  );
}

async function connectCall() {
  await page.locator('button[data-tooltip="开始通话"]').click();
  await page.waitForFunction(
    () => document.querySelector(".state-label")?.textContent === "AI 已接通",
    undefined,
    { timeout: TIMEOUT_MS },
  );
}

async function sendText(text) {
  const input = page.locator('input[placeholder="发送消息…"]');
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

async function waitForBotIdle() {
  await page.waitForFunction(
    () => !document.querySelector(".assistant-activity"),
    undefined,
    { timeout: TIMEOUT_MS },
  );
}

async function runStartedCount() {
  return page.locator('.event-agent-row[data-event-type="run.started"]').count();
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

async function waitForRunStatus(runId, expected) {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    const payload = await api(`/api/agent/runs/${runId}`);
    const status = payload.run?.status;
    if (status === expected) return payload.run;
    if (["completed", "failed", "cancelled", "interrupted"].includes(status)) {
      throw new Error(`Run ${runId} ended as ${status}, expected ${expected}`);
    }
    await delay(250);
  }
  throw new Error(`Run ${runId} did not reach ${expected}`);
}

async function startVoiceFixture() {
  return page.evaluate(() => window.__startVoiceFixture());
}

async function waitForVoiceFixture() {
  await page.evaluate(() => window.__awaitVoiceFixture());
}

async function waitForBotVolume(expected, timeout = TIMEOUT_MS) {
  await page.waitForFunction(
    (volume) => document.querySelector("audio")?.volume === volume,
    expected,
    { polling: 10, timeout },
  );
}

async function waitForEffects(expected) {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (effects.length >= expected) return;
    await delay(50);
  }
  throw new Error(`Side effect count did not reach ${expected}`);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

try {
  effectServer = await startEffectServer();

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

  await createMcpServer();
  await createAgent();
  proxy = await startLoopbackProxy();

  browser = await chromium.launch({
    headless: true,
    args: [
      "--autoplay-policy=no-user-gesture-required",
      "--disable-dev-shm-usage",
      "--no-sandbox",
    ],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await installSession(context);
  page = await context.newPage();
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  assert.equal(await page.evaluate(() => window.isSecureContext), true);
  await page.getByRole("button", { name: "进入通话" }).click();
  await connectCall();
  await waitForBotVolume(1);

  const audioBefore = await page.evaluate(() => window.__inboundAudioBytes());
  const bargeStartedBefore = await runStartedCount();
  await sendText("STAGE4_LONG_BARGE");
  const interruptedRunId = await waitForRunStarted(bargeStartedBefore);
  await waitForRunStatus(interruptedRunId, "running");
  await page.waitForFunction(
    (minimum) => window.__inboundAudioBytes().then((bytes) => bytes > minimum + 1500),
    audioBefore,
    { timeout: TIMEOUT_MS },
  );
  await waitForRunStatus(interruptedRunId, "running");

  const followupStartedBefore = await runStartedCount();
  const voiceStartedAt = await startVoiceFixture();
  await waitForBotVolume(0, LOCAL_STOP_LIMIT_MS);
  const localStopDelay = await page.evaluate(
    (startedAt) => performance.now() - startedAt,
    voiceStartedAt,
  );
  assert(
    localStopDelay <= LOCAL_STOP_LIMIT_MS,
    `Local bot audio stopped after ${localStopDelay.toFixed(1)}ms`,
  );
  await waitForVoiceFixture();
  const followupRunId = await waitForRunStarted(followupStartedBefore);
  await waitForRunStatus(interruptedRunId, "cancelled");
  await waitForRunStatus(followupRunId, "completed");
  await waitForAssistant("VOICE FOLLOWUP OK 731");
  await waitForBotVolume(1);
  console.log(
    JSON.stringify({
      check: "voice-barge-in-stop-and-cancel",
      local_stop_ms: Math.round(localStopDelay),
      status: "passed",
    }),
  );

  await waitForBotIdle();
  const approvalStartedBefore = await runStartedCount();
  await sendText("STAGE4_ASK_APPROVAL");
  const approvalRunId = await waitForRunStarted(approvalStartedBefore);
  await page
    .getByText("Approve the stage 4 voice release?", { exact: true })
    .waitFor({ timeout: TIMEOUT_MS });
  const interruptedRun = await waitForRunStatus(approvalRunId, "interrupted");
  const approvalResumeStartedBefore = await runStartedCount();
  await startVoiceFixture();
  await waitForVoiceFixture();
  const approvalResumeRunId = await waitForRunStarted(approvalResumeStartedBefore);
  const approvalResumeRun = await waitForRunStatus(approvalResumeRunId, "completed");
  await waitForAssistant("VOICE APPROVAL RESUME OK 418");
  assert.equal(approvalResumeRun.run_type, "resume");
  assert.equal(approvalResumeRun.created_by_run_id, approvalRunId);
  assert.equal(
    approvalResumeRun.conversation_thread_id,
    interruptedRun.conversation_thread_id,
  );
  console.log(JSON.stringify({ check: "voice-approval-resume", status: "passed" }));

  await waitForBotIdle();
  assert.equal(effects.length, 0);
  const effectStartedBefore = await runStartedCount();
  await sendText("STAGE4_RUN_SIDE_EFFECT");
  const effectRunId = await waitForRunStarted(effectStartedBefore);
  await waitForEffects(1);
  assert.equal(effects[0].marker, sideEffectMarker);
  await waitForRunStatus(effectRunId, "running");

  const postEffectStartedBefore = await runStartedCount();
  await startVoiceFixture();
  await waitForVoiceFixture();
  const postEffectRunId = await waitForRunStarted(postEffectStartedBefore);
  await waitForRunStatus(effectRunId, "cancelled");
  await waitForRunStatus(postEffectRunId, "completed");
  const settleUntil = effects[0].receivedAt + EFFECT_RESPONSE_DELAY_MS + 2000;
  await delay(Math.max(0, settleUntil - Date.now()));
  assert.equal(effects.length, 1, "Cancelled side-effect tool executed more than once");
  console.log(
    JSON.stringify({ check: "side-effect-cancel-no-duplicate", status: "passed" }),
  );
} finally {
  await browser?.close().catch(() => undefined);
  await new Promise((resolve) => proxy?.close(resolve) || resolve());
  if (agentCreated) {
    await api(`/api/agent/${agentSlug}`, { method: "DELETE" }).catch(() => undefined);
  }
  if (mcpCreated) {
    await api(`/api/system/mcp-servers/${mcpSlug}`, { method: "DELETE" }).catch(
      () => undefined,
    );
  }
  if (providerChanged && providerModels) {
    await updateProviderModels(providerModels).catch(() => undefined);
    await waitForModel(false).catch(() => undefined);
  }
  if (effectServer) {
    await new Promise((resolve) => {
      effectServer.close(resolve);
      effectServer.closeAllConnections?.();
    });
  }
}
