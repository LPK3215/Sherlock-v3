"use client";

import { Bot, LogIn, LogOut } from "lucide-react";
import { useState, type FormEvent } from "react";

export interface YuxiAgent {
  slug: string;
  name: string;
  description?: string | null;
}

interface Props {
  agents: YuxiAgent[];
  agentSlug: string;
  authenticated: boolean;
  error: string;
  loading: boolean;
  onAgentChange: (slug: string) => void;
  onLogin: (loginId: string, password: string) => Promise<void>;
  onLogout: () => void;
  onStart: () => void;
}

export function SessionGate({
  agents,
  agentSlug,
  authenticated,
  error,
  loading,
  onAgentChange,
  onLogin,
  onLogout,
  onStart,
}: Props) {
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");

  const submitLogin = async (event: FormEvent) => {
    event.preventDefault();
    setLocalError("");
    try {
      await onLogin(loginId.trim(), password);
    } catch (reason: unknown) {
      setLocalError((reason as Error).message);
    }
  };

  return (
    <main className="session-gate">
      <header className="session-brand">
        <span className="session-brand-mark">S</span>
        <div>
          <strong>Sherlock</strong>
          <span>Yuxi Realtime</span>
        </div>
      </header>

      <section className="session-form" aria-busy={loading}>
        {!authenticated ? (
          <form onSubmit={submitLogin}>
            <div className="session-heading">
              <LogIn />
              <h1>登录 Yuxi</h1>
            </div>
            <label>
              <span>账号</span>
              <input
                autoComplete="username"
                autoFocus
                value={loginId}
                onChange={(event) => setLoginId(event.target.value)}
              />
            </label>
            <label>
              <span>密码</span>
              <input
                autoComplete="current-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button type="submit" className="session-primary" disabled={loading || !loginId || !password}>
              {loading ? "正在登录" : "登录"}
            </button>
          </form>
        ) : (
          <div>
            <div className="session-heading">
              <Bot />
              <h1>选择 Agent</h1>
            </div>
            <label>
              <span>Agent</span>
              <select value={agentSlug} onChange={(event) => onAgentChange(event.target.value)}>
                {agents.map((agent) => (
                  <option key={agent.slug} value={agent.slug}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="session-primary" disabled={loading || !agentSlug} onClick={onStart}>
              进入通话
            </button>
            <button type="button" className="session-secondary" onClick={onLogout}>
              <LogOut />
              退出登录
            </button>
          </div>
        )}
        {(localError || error) && <p className="session-error">{localError || error}</p>}
      </section>
    </main>
  );
}
