"use client";

import { ArrowRight, Bot, LockKeyhole, LogIn, LogOut, Sparkles, UserRound } from "lucide-react";
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
  const selectedAgent = agents.find((agent) => agent.slug === agentSlug);

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
        <span className="session-brand-mark"><Sparkles /></span>
        <div>
          <strong>Sherlock</strong>
          <span>实时多模态助手</span>
        </div>
      </header>

      <section className="session-intro">
        <span className="session-kicker">SHERLOCK LIVE</span>
        <h1>与你的 AI Agent<br />自然交流</h1>
        <p>一套 Yuxi 后端，直接支持文字、语音、视频与屏幕内容。</p>
        <div className="session-capabilities" aria-label="支持的对话方式">
          <span>语音</span><span>视频</span><span>文字</span><span>屏幕</span>
        </div>
      </section>

      <section className="session-form" aria-busy={loading}>
        {!authenticated ? (
          <form onSubmit={submitLogin}>
            <div className="session-heading">
              <LogIn />
              <div><h2>登录</h2><p>使用 Yuxi 账号继续</p></div>
            </div>
            <label>
              <span>账号</span>
              <div className="field-control"><UserRound /><input autoComplete="username" autoFocus value={loginId} onChange={(event) => setLoginId(event.target.value)} /></div>
            </label>
            <label>
              <span>密码</span>
              <div className="field-control"><LockKeyhole /><input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></div>
            </label>
            <button type="submit" className="session-primary" disabled={loading || !loginId || !password}>
              <span>{loading ? "正在登录" : "登录"}</span><ArrowRight />
            </button>
          </form>
        ) : (
          <div>
            <div className="session-heading">
              <Bot />
              <div><h2>选择 Agent</h2><p>选择本次对话使用的助手</p></div>
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
            {selectedAgent?.description && <p className="agent-description">{selectedAgent.description}</p>}
            <button type="button" className="session-primary" disabled={loading || !agentSlug} onClick={onStart}>
              <span>进入通话</span><ArrowRight />
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
