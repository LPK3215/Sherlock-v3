"use client";

import { PipecatAppBase } from "@pipecat-ai/voice-ui-kit";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ClientApp } from "./ClientApp";
import { SessionGate, type YuxiAgent } from "./SessionGate";

import "@pipecat-ai/voice-ui-kit/styles.scoped";

const TOKEN_KEY = "user_token";
const AGENT_KEY = "realtime_agent_slug";

export default function Home() {
  const [isMobile, setIsMobile] = useState(false);
  const [token, setToken] = useState("");
  const [agents, setAgents] = useState<YuxiAgent[]>([]);
  const [agentSlug, setAgentSlug] = useState("");
  const [sessionReady, setSessionReady] = useState(false);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAgents = useCallback(async (accessToken: string) => {
    const response = await fetch("/yuxi-api/agent", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) throw new Error(await responseMessage(response));
    const payload = (await response.json()) as { agents?: YuxiAgent[] };
    const visibleAgents = Array.isArray(payload.agents) ? payload.agents : [];
    if (visibleAgents.length === 0) throw new Error("当前账号没有可用的 Agent");
    setAgents(visibleAgents);
    setAgentSlug((current) => {
      const saved = localStorage.getItem(AGENT_KEY) || current;
      return visibleAgents.some((agent) => agent.slug === saved)
        ? saved
        : visibleAgents[0].slug;
    });
  }, []);

  useEffect(() => {
    setIsMobile(
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent,
      ),
    );
    const savedToken = localStorage.getItem(TOKEN_KEY) || "";
    if (!savedToken) {
      setLoading(false);
      return;
    }
    setToken(savedToken);
    loadAgents(savedToken)
      .catch((reason: unknown) => {
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
        setError((reason as Error).message);
      })
      .finally(() => setLoading(false));
  }, [loadAgents]);

  const login = useCallback(
    async (loginId: string, password: string) => {
      setLoading(true);
      setError("");
      try {
        const form = new URLSearchParams({ username: loginId, password });
        const response = await fetch("/yuxi-api/auth/token", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: form,
        });
        if (!response.ok) throw new Error(await responseMessage(response));
        const payload = (await response.json()) as { access_token?: string };
        if (!payload.access_token) throw new Error("Yuxi 登录响应缺少 access_token");
        localStorage.setItem(TOKEN_KEY, payload.access_token);
        setToken(payload.access_token);
        await loadAgents(payload.access_token);
      } finally {
        setLoading(false);
      }
    },
    [loadAgents],
  );

  const startSession = useCallback(() => {
    localStorage.setItem(AGENT_KEY, agentSlug);
    setCurrentThreadId(sessionStorage.getItem(`realtime_thread:${agentSlug}`));
    setSessionReady(true);
  }, [agentSlug]);

  const leaveSession = useCallback(() => {
    setSessionReady(false);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setAgents([]);
    setSessionReady(false);
    setError("");
  }, []);

  const startBotParams = useMemo(
    () => ({
      endpoint: "/yuxi-api/realtime/start",
      headers: new Headers({
        Authorization: `Bearer ${token}`,
      }),
      requestData: {
      agent_slug: agentSlug,
      thread_id:
        typeof window === "undefined"
          ? null
          : sessionStorage.getItem(`realtime_thread:${agentSlug}`),
        enableDefaultIceServers: true,
      },
    }),
    [agentSlug, token],
  );

  const handleThreadChange = useCallback(
    (nextThreadId: string) => {
      const requestData = startBotParams.requestData as {
        thread_id: string | null;
      };
      requestData.thread_id = nextThreadId;
      setCurrentThreadId(nextThreadId);
      sessionStorage.setItem(`realtime_thread:${agentSlug}`, nextThreadId);
    },
    [agentSlug, startBotParams],
  );

  const handleStartResponse = useCallback(
    (response: unknown) => {
      if (response && typeof response === "object") {
        const data = response as { threadId?: unknown; thread_id?: unknown };
        const threadId = data.threadId ?? data.thread_id;
        if (typeof threadId === "string" && threadId) handleThreadChange(threadId);
      }
      return response;
    },
    [handleThreadChange],
  );

  if (!sessionReady) {
    return (
      <SessionGate
        agents={agents}
        agentSlug={agentSlug}
        authenticated={Boolean(token)}
        error={error}
        loading={loading}
        onAgentChange={setAgentSlug}
        onLogin={login}
        onLogout={logout}
        onStart={startSession}
      />
    );
  }

  return (
    <div className="vkui-root">
      <div className="voice-ui-kit">
        <PipecatAppBase
          transportType="smallwebrtc"
          startBotParams={startBotParams}
          startBotResponseTransformer={handleStartResponse}
          transportOptions={{
            offerUrlTemplate: "/yuxi-api/realtime/sessions/:sessionId/offer",
          }}
        >
          {({ handleConnect, handleDisconnect }) => (
            <ClientApp
              agentName={agents.find((agent) => agent.slug === agentSlug)?.name || agentSlug}
              connect={handleConnect}
              disconnect={handleDisconnect}
              isMobile={isMobile}
              onLeave={leaveSession}
              onThreadChange={handleThreadChange}
              apiBase="/yuxi-api"
              threadId={currentThreadId}
            />
          )}
        </PipecatAppBase>
      </div>
    </div>
  );
}


async function responseMessage(response: Response) {
  const payload = (await response.json().catch(() => null)) as
    | { detail?: string; message?: string }
    | null;
  return payload?.detail || payload?.message || `请求失败 (${response.status})`;
}
