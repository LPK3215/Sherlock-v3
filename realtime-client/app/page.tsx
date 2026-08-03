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
    setSessionReady(true);
  }, [agentSlug]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setAgents([]);
    setSessionReady(false);
    setError("");
  }, []);

  const requestData = useMemo(
    () => ({
      yuxi_access_token: token,
      agent_slug: agentSlug,
      thread_id:
        typeof window === "undefined"
          ? null
          : localStorage.getItem(`realtime_thread:${agentSlug}`),
    }),
    [agentSlug, token],
  );

  const handleThreadChange = useCallback(
    (nextThreadId: string) => {
      requestData.thread_id = nextThreadId;
      localStorage.setItem(`realtime_thread:${agentSlug}`, nextThreadId);
    },
    [agentSlug, requestData],
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
          connectParams={{ endpoint: "/api/start", requestData }}
        >
          {({ handleConnect, handleDisconnect }) => (
            <ClientApp
              agentName={agents.find((agent) => agent.slug === agentSlug)?.name || agentSlug}
              connect={handleConnect}
              disconnect={handleDisconnect}
              isMobile={isMobile}
              onThreadChange={handleThreadChange}
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
