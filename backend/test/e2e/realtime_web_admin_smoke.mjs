import assert from "node:assert/strict";
import net from "node:net";

const token = process.env.E2E_ACCESS_TOKEN;
assert(token, "E2E_ACCESS_TOKEN is required");
const api = process.env.E2E_API_URL || "http://api:5050";
const web = process.env.E2E_WEB_URL || "http://web:5173";
const playwright = await import(process.env.PLAYWRIGHT_MODULE || "/work/node_modules/playwright-core/index.js");
const chromium = playwright.chromium || playwright.default?.chromium;
assert(chromium, "playwright chromium is unavailable");

async function request(path, options = {}) {
  const response = await fetch(`${api}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.body ? { "Content-Type": "application/json" } : {}) },
  });
  const body = await response.text();
  assert(response.ok, `${options.method || "GET"} ${path} failed: ${response.status} ${body}`);
  return body ? JSON.parse(body) : {};
}

const agents = await request("/api/agent");
const list = agents.data || agents.agents || [];
const agent = list.find((item) => item.slug === "sherlock-realtime") || list.find((item) => !item.is_subagent) || list[0];
assert(agent, "No agent is available for realtime smoke test");

const browser = await chromium.launch({ headless: true, executablePath: "/ms-playwright/chromium-1187/chrome-linux/chrome", args: ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"] });
const proxy = net.createServer((client) => {
  const upstream = net.connect({ host: "web", port: 5173 });
  client.on("error", () => upstream.destroy());
  upstream.on("error", () => client.destroy());
  client.pipe(upstream).pipe(client);
});
await new Promise((resolve, reject) => {
  proxy.once("error", reject);
  proxy.listen(5173, "127.0.0.1", resolve);
});
try {
  const context = await browser.newContext({ permissions: ["microphone", "camera"] });
  await context.addInitScript(({ accessToken }) => {
    localStorage.setItem("user_token", accessToken);
    navigator.mediaDevices.getUserMedia = async () => {
      const audio = new AudioContext().createMediaStreamDestination();
      const canvas = document.createElement("canvas");
      canvas.width = 640; canvas.height = 360;
      return new MediaStream([...audio.stream.getAudioTracks(), ...canvas.captureStream(5).getVideoTracks()]);
    };
    navigator.mediaDevices.getDisplayMedia = async () => document.createElement("canvas").captureStream(5);
  }, { accessToken: token });
  const page = await context.newPage();
  const agentSlug = agent.slug || agent.agent_id || String(agent.id);
  await page.goto(`http://localhost:5173/agent/realtime?agent_id=${encodeURIComponent(agentSlug)}`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "开始通话" }).click();
  await page.waitForFunction(() => document.querySelector(".realtime-header p")?.textContent?.includes("AI 已接通"), null, { timeout: 60000 });
  await page.getByPlaceholder("输入实时消息").fill("管理端实时 smoke");
  await page.getByRole("button", { name: "发送" }).click();
  await page.getByRole("button", { name: "共享屏幕" }).click();
  await page.getByRole("button", { name: "停止共享" }).waitFor({ timeout: 10000 });
  await page.getByRole("button", { name: "停止共享" }).click();
  await page.getByRole("button", { name: "静音麦克风" }).click();
  await page.getByRole("button", { name: "打开麦克风" }).waitFor({ timeout: 5000 });
  console.log(JSON.stringify({ check: "web-admin-realtime-smoke", status: "passed", agent: agent.id }));
} finally {
  await browser.close();
  await new Promise((resolve) => proxy.close(resolve));
}
