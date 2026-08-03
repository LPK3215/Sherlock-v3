import assert from "node:assert/strict";
import net from "node:net";

const API_URL = process.env.E2E_API_URL || "http://api:5050";
const CLIENT_HOST = process.env.E2E_CLIENT_HOST || "user-app";
const CLIENT_PORT = Number(process.env.E2E_CLIENT_PORT || "3000");
const ACCESS_TOKEN = process.env.E2E_ACCESS_TOKEN || "";
const PLAYWRIGHT_MODULE =
  process.env.PLAYWRIGHT_MODULE || "/work/node_modules/playwright-core/index.js";
const CHAT_MODEL =
  process.env.E2E_CHAT_MODEL || "siliconflow-cn:Qwen/Qwen3-VL-8B-Instruct";
const TIMEOUT_MS = Number(process.env.E2E_REALTIME_TIMEOUT_MS || "180000");

assert(ACCESS_TOKEN, "E2E_ACCESS_TOKEN is required");
assert(CHAT_MODEL.includes(":"), "E2E_CHAT_MODEL must use provider:model format");

const playwright = await import(PLAYWRIGHT_MODULE);
const chromium = playwright.chromium || playwright.default?.chromium;
assert(chromium, `Chromium is not exported by ${PLAYWRIGHT_MODULE}`);

const authHeaders = { Authorization: `Bearer ${ACCESS_TOKEN}` };
const providerId = CHAT_MODEL.slice(0, CHAT_MODEL.indexOf(":"));
const modelId = CHAT_MODEL.slice(CHAT_MODEL.indexOf(":") + 1);
const agentSlug = `realtime-approval-e2e-${Date.now()}`;

let agentCreated = false;
let browser;
let page;
let providerChanged = false;
let providerModels;
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
    if (models.some((model) => model.spec === CHAT_MODEL) === expected) return;
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
      name: `Realtime Approval E2E ${agentSlug.slice(-8)}`,
      slug: agentSlug,
      backend_id: "ChatbotAgent",
      description: "Stage 4 approval and resume browser E2E temporary agent",
      config_json: {
        context: {
          model: CHAT_MODEL,
          system_prompt: [
            "You are a deterministic approval end-to-end test assistant.",
            "When asked for the release channel, call ask_user_question exactly once.",
            'Use questions=[{"question_id":"approval_choice","question":"Which release channel?","options":[{"label":"Stable","value":"stable"},{"label":"Preview","value":"preview"}],"multi_select":false,"allow_other":false}].',
            "After the tool returns an answer whose approval_choice is stable, answer exactly APPROVAL RESUME OK 861.",
            "Do not call any other tool.",
          ].join(" "),
          tools: ["ask_user_question"],
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

async function installSession(context) {
  await context.addInitScript(
    ({ accessToken, selectedAgent }) => {
      localStorage.setItem("user_token", accessToken);
      localStorage.setItem("realtime_agent_slug", selectedAgent);

      const audioContext = new AudioContext({ sampleRate: 48000 });
      const audioDestination = audioContext.createMediaStreamDestination();
      const silence = audioContext.createConstantSource();
      silence.offset.value = 0;
      silence.connect(audioDestination);
      silence.start();

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
      window.__approvalE2EMedia = {
        audioContext,
        audioDestination,
        canvas,
        silence,
        timer,
        videoTrack,
      };

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
    },
    { accessToken: ACCESS_TOKEN, selectedAgent: agentSlug },
  );
}

async function connectCall() {
  await page.locator("button.start-call-action").click();
  await page.waitForFunction(
    () => document.querySelector(".connection-badge")?.textContent?.includes("AI 已接通"),
    undefined,
    { timeout: TIMEOUT_MS },
  );
}

async function reconnectCall() {
  await page.locator('button[data-tooltip="挂断"]').click();
  await page.waitForFunction(
    () => document.querySelector(".connection-badge")?.textContent?.includes("尚未接通"),
    undefined,
    { timeout: 30000 },
  );
  await connectCall();
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

  await createAgent();
  agentCreated = true;
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

  const parentStartedBefore = await runStartedCount();
  await sendText("Ask me which release channel to use.");
  const interruptedRunId = await waitForRunStarted(parentStartedBefore);
  await page.getByText("Which release channel?", { exact: true }).waitFor({ timeout: TIMEOUT_MS });
  await waitForRunStatus(interruptedRunId, "interrupted");
  const interruptedRun = await api(`/api/agent/runs/${interruptedRunId}`);
  const interruptedThreadId = interruptedRun.run?.conversation_thread_id;
  assert(interruptedThreadId, "Interrupted run is missing conversation_thread_id");
  await page.waitForFunction(
    ({ key, value }) => localStorage.getItem(key) === value,
    { key: `realtime_thread:${agentSlug}`, value: interruptedThreadId },
    { timeout: 30000 },
  );

  await reconnectCall();
  await page.getByText("Which release channel?", { exact: true }).waitFor({ timeout: TIMEOUT_MS });

  const resumeStartedBefore = await runStartedCount();
  await page.getByText("Stable", { exact: true }).click();
  await page.getByRole("button", { name: "提交" }).click();
  const resumeRunId = await waitForRunStarted(resumeStartedBefore);
  await waitForRunStatus(resumeRunId, "completed");
  await waitForAssistant("APPROVAL RESUME OK 861");

  const resumeRun = await api(`/api/agent/runs/${resumeRunId}`);
  assert.equal(resumeRun.run?.run_type, "resume");
  assert.equal(resumeRun.run?.created_by_run_id, interruptedRunId);
  assert.equal(
    resumeRun.run?.conversation_thread_id,
    interruptedRun.run?.conversation_thread_id,
  );
  console.log(JSON.stringify({ check: "approval-resume-reconnect", status: "passed" }));
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
