"use client";

import {
  RTVIEvent,
  type BotOutputData,
  type TranscriptData,
} from "@pipecat-ai/client-js";
import {
  PipecatClientVideo,
  usePipecatClient,
  usePipecatClientCamControl,
  usePipecatClientMicControl,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";
import { useBotAudioOutput } from "@pipecat-ai/voice-ui-kit";
import {
  ArrowLeft,
  CameraOff,
  Camera,
  Clock3,
  LoaderCircle,
  Logs,
  Mic,
  MicOff,
  MonitorUp,
  Paperclip,
  Phone,
  PhoneOff,
  SendHorizontal,
  Sparkles,
  Video,
  VideoOff,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  ApprovalPrompt,
  normalizeApprovalQuestions,
  type ApprovalQuestion,
} from "./ApprovalPrompt";
import { EventStreamPanel } from "./EventStreamPanel";

/* ------- Types ------- */

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  failed?: boolean;
  mediaSource?: MediaSource;
}

type MediaSource = "camera" | "screen";

type Diagnostic = [string, string];

interface Props {
  agentName: string;
  connect?: () => void | Promise<void>;
  disconnect?: () => void | Promise<void>;
  isMobile: boolean;
  onLeave: () => void;
  onThreadChange: (threadId: string) => void;
  apiBase: string;
  threadId: string | null;
  agentSlug: string;
  initialApprovalQuestions: ApprovalQuestion[];
  startResponse: unknown;
  accessToken: string;
}

export interface AgentEvent {
  id: string;
  timestamp: Date;
  type: string;
  data: Record<string, unknown>;
}

/* ------- Constants ------- */

const STATE_LABELS: Record<string, string> = {
  authenticated: "正在建立安全连接",
  authenticating: "正在验证连接",
  connected: "正在等待 AI",
  connecting: "正在连接",
  disconnected: "尚未接通",
  disconnecting: "正在挂断",
  error: "连接失败",
  initialized: "可以开始通话",
  initializing: "正在准备设备",
  ready: "AI 已接通",
};

const READY_STATES = new Set(["disconnected", "initialized", "error", "ready"]);

const createMessageId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const appendChunk = (current: string, chunk: string) => {
  if (!current) return chunk;
  if (current.endsWith(chunk)) return current;
  if (chunk.startsWith(current)) return chunk;

  const needsSpace =
    /[A-Za-z0-9]$/.test(current) && /^[A-Za-z0-9]/.test(chunk);
  return `${current}${needsSpace ? " " : ""}${chunk}`;
};

/* ------- Component ------- */

export function ClientApp({ agentName, connect, disconnect, isMobile, onLeave, onThreadChange, apiBase, threadId, startResponse, accessToken, agentSlug, initialApprovalQuestions }: Props) {
  /* ---------- Pipecat hooks ---------- */
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const cam = usePipecatClientCamControl();
  const mic = usePipecatClientMicControl();
  const { setVolume: setBotVolume } = useBotAudioOutput();

  /* ---------- Local state ---------- */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingSends, setPendingSends] = useState(0);
  const [screenShareEnabled, setScreenShareEnabled] = useState(false);
  const [mediaSource, setMediaSource] = useState<MediaSource | null>(null);
  const [mediaSourceUpdating, setMediaSourceUpdating] = useState(false);
  const [assistantActivity, setAssistantActivity] = useState<
    "idle" | "thinking" | "speaking"
  >("idle");
  const [showLog, setShowLog] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [approvalQuestions, setApprovalQuestions] = useState<ApprovalQuestion[]>([]);
  const [approvalProcessing, setApprovalProcessing] = useState(false);
  const [error, setError] = useState("");
  const [reconnecting, setReconnecting] = useState(false);
  const [connectedAt, setConnectedAt] = useState<number | null>(null);
  const [durationSeconds, setDurationSeconds] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const seenTranscriptsRef = useRef(new Set<string>());
  const pipRef = useRef<HTMLDivElement>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const [pipPosition, setPipPosition] = useState({ x: 24, y: 82 });
  const userHangupRef = useRef(false);
  const wasConnectedRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (initialApprovalQuestions.length > 0) setApprovalQuestions(initialApprovalQuestions);
  }, [initialApprovalQuestions]);

  useEffect(() => {
    if (!startResponse || typeof startResponse !== "object") return;
    const response = startResponse as { threadId?: unknown; thread_id?: unknown };
    const nextThreadId = response.threadId ?? response.thread_id;
    if (typeof nextThreadId === "string" && nextThreadId) onThreadChange(nextThreadId);
  }, [onThreadChange, startResponse]);

  useRTVIClientEvent(
    RTVIEvent.BotStarted,
    useCallback((response: unknown) => {
      if (!response || typeof response !== "object") return;
      const data = response as { threadId?: unknown; thread_id?: unknown };
      const nextThreadId = data.threadId ?? data.thread_id;
      if (typeof nextThreadId === "string" && nextThreadId) onThreadChange(nextThreadId);
    }, [onThreadChange]),
  );

  useEffect(() => {
    let cancelled = false;
    const checkApproval = async () => {
      const storedThreadId = typeof window !== "undefined"
        ? sessionStorage.getItem(`realtime_thread:${agentSlug}`)
        : null;
      const currentThreadId = threadId || storedThreadId;
      if (!currentThreadId) return;
      const response = await fetch(`${apiBase}/agent/thread/${currentThreadId}/active_run`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok || cancelled) return;
      const payload = (await response.json()) as { interrupt?: { chunk?: Record<string, unknown> } };
      const chunk = payload.interrupt?.chunk;
      const questions = normalizeApprovalQuestions(chunk?.questions);
      if (questions.length > 0 && !cancelled) {
        setApprovalQuestions(questions);
        setApprovalProcessing(false);
        setAssistantActivity("idle");
      }
    };
    void checkApproval();
    const timer = window.setInterval(() => void checkApproval(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [accessToken, agentSlug, apiBase, threadId]);

  /* ---------- Derived ---------- */
  const isConnected = transportState === "ready";
  const isTransitioning =
    transportState === "connecting" ||
    transportState === "authenticating" ||
    transportState === "authenticated" ||
    transportState === "connected";

  const stateLabel = reconnecting ? "重连中…" : (STATE_LABELS[transportState] ?? transportState);
  const isStable = READY_STATES.has(transportState);
  const formattedDuration = `${String(Math.floor(durationSeconds / 60)).padStart(2, "0")}:${String(durationSeconds % 60).padStart(2, "0")}`;

  /* ---------- Derived: error ---------- */

  /* ---------- Auto-scroll ---------- */
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!isConnected) {
      setConnectedAt(null);
      setDurationSeconds(0);
      return;
    }
    const startedAt = connectedAt ?? Date.now();
    if (!connectedAt) setConnectedAt(startedAt);
    const updateDuration = () => {
      setDurationSeconds(Math.floor((Date.now() - startedAt) / 1000));
    };
    updateDuration();
    const timer = window.setInterval(updateDuration, 1000);
    return () => window.clearInterval(timer);
  }, [connectedAt, isConnected]);

  /* ---------- RTVI events ---------- */
  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback((data: TranscriptData) => {
      const text = data.text?.trim();
      if (!data.final || !text) return;

      const transcriptKey = `${data.timestamp}:${data.user_id}:${text}`;
      if (seenTranscriptsRef.current.has(transcriptKey)) return;
      seenTranscriptsRef.current.add(transcriptKey);
      setAssistantActivity("thinking");
      setMessages((prev) => [
        ...prev,
        { id: createMessageId(), role: "user", text },
      ]);
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.BotOutput,
    useCallback((data: BotOutputData) => {
      // The same content is emitted once for generated text and again as it is
      // spoken. Rendering both streams is what caused entire answers to repeat.
      if (data.spoken) return;
      const text = data.text?.trim();
      if (!text) return;

      setAssistantActivity("speaking");
      setMessages((prev) => {
        const last = prev.at(-1);
        if (last?.role === "assistant") {
          return [
            ...prev.slice(0, -1),
            { ...last, text: appendChunk(last.text, text) },
          ];
        }
        return [
          ...prev,
          { id: createMessageId(), role: "assistant", text },
        ];
      });
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.BotLlmStarted,
    useCallback(() => setAssistantActivity("thinking"), []),
  );

  useRTVIClientEvent(
    RTVIEvent.BotLlmStopped,
    useCallback(
      () => setAssistantActivity((activity) =>
        activity === "thinking" ? "idle" : activity,
      ),
      [],
    ),
  );

  useRTVIClientEvent(
    RTVIEvent.BotStartedSpeaking,
    useCallback(() => {
      setBotVolume(1);
      setAssistantActivity("speaking");
    }, [setBotVolume]),
  );

  useRTVIClientEvent(
    RTVIEvent.UserStartedSpeaking,
    useCallback(() => setBotVolume(0), [setBotVolume]),
  );

  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => setAssistantActivity("idle"), []),
  );

  useRTVIClientEvent(
    RTVIEvent.ScreenTrackStarted,
    useCallback(() => setScreenShareEnabled(true), []),
  );

  useRTVIClientEvent(
    RTVIEvent.ScreenTrackStopped,
    useCallback(() => setScreenShareEnabled(false), []),
  );

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((data: Record<string, unknown> | string) => {
      const envelope = typeof data === "string" ? data : data;
      const rawMessage =
        envelope && typeof envelope === "object" && "data" in envelope
          ? (envelope.data as Record<string, unknown> | string)
          : envelope;
      const msg = (() => {
        if (typeof rawMessage !== "string") return rawMessage;
        try {
          const parsed = JSON.parse(rawMessage);
          return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
        } catch {
          return null;
        }
      })();
      if (!msg || typeof msg !== "object") return;
      const envelopeMessage = msg as Record<string, unknown>;
      let message = envelopeMessage;
      if (envelopeMessage.type === "server-message" && envelopeMessage.data !== undefined) {
        const serverData = envelopeMessage.data;
        if (serverData && typeof serverData === "object") {
          message = serverData as Record<string, unknown>;
        } else if (typeof serverData === "string") {
          try {
            const parsed = JSON.parse(serverData);
            if (parsed && typeof parsed === "object") message = parsed as Record<string, unknown>;
          } catch {
            return;
          }
        }
      }
      const payloadValue =
        typeof message.payload === "string"
          ? (() => {
              try {
                return JSON.parse(message.payload as string);
              } catch {
                return null;
              }
            })()
          : message.payload;
      const eventPayload =
        payloadValue && typeof payloadValue === "object" &&
        "payload" in (payloadValue as Record<string, unknown>) &&
        !("type" in (payloadValue as Record<string, unknown>))
          ? (payloadValue as Record<string, unknown>).payload
          : payloadValue;
      if (message.type === "media-diagnostics") {
        const entries = Object.entries((payloadValue as object) ?? {}) as Diagnostic[];
        setDiagnostics(entries);
      }
      if (message.type === "yuxi-agent-event") {
        const payload = eventPayload as Record<string, unknown>;
        const eventType = typeof payload?.type === "string" ? payload.type : "yuxi.event";
        setAgentEvents((current) => [
          ...current.slice(-499),
          { id: createMessageId(), timestamp: new Date(), type: eventType, data: payload },
        ]);
        if (typeof payload?.thread_id === "string") onThreadChange(payload.thread_id);
        if (eventType === "approval.required") {
          const detail = payload.detail as Record<string, unknown> | undefined;
          const interruptInfo = detail?.interrupt_info as Record<string, unknown> | undefined;
          const chunk = detail?.chunk as Record<string, unknown> | undefined;
          const questions = normalizeApprovalQuestions(
            detail?.questions ?? interruptInfo?.questions ?? chunk?.questions,
          );
          if (questions.length > 0) {
            setApprovalQuestions(questions);
            setApprovalProcessing(false);
            setAssistantActivity("idle");
          }
        }
        if (eventType === "run.started" && approvalQuestions.length > 0) {
          setApprovalQuestions([]);
          setApprovalProcessing(false);
        }
        if (eventType === "run.cancelled") {
          setAssistantActivity("idle");
        }
        if (eventType === "run.failed") {
          setApprovalProcessing(false);
          setAssistantActivity("idle");
          setError("AI 回复失败，请重试");
        }
      }
    }, [approvalQuestions.length, onThreadChange]),
  );

  useRTVIClientEvent(
    RTVIEvent.UICommand,
    useCallback((data: { command?: string; payload?: unknown }) => {
      if (data.command !== "yuxi.approval.required") return;
      const payload = data.payload as Record<string, unknown> | undefined;
      const detail = payload?.detail as Record<string, unknown> | undefined;
      const questions = normalizeApprovalQuestions(detail?.questions);
      if (questions.length > 0) {
        setApprovalQuestions(questions);
        setApprovalProcessing(false);
        setAssistantActivity("idle");
      }
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.Error,
    useCallback((data: unknown) => {
      const msg = data as Record<string, unknown> | undefined;
      setApprovalProcessing(false);
      setAssistantActivity("idle");
      setError((msg?.message as string) ?? JSON.stringify(data ?? {}));
    }, []),
  );

  /* ---------- Actions ---------- */
  const doConnect = useCallback(async () => {
    setError("");
    setMessages([]);
    setDiagnostics([]);
    setAgentEvents([]);
    setApprovalQuestions([]);
    setApprovalProcessing(false);
    setAssistantActivity("idle");
    setScreenShareEnabled(false);
    setMediaSource(null);
    setMediaSourceUpdating(false);
    seenTranscriptsRef.current.clear();
    try {
      mic.enableMic(true);
    } catch {
      /* continue even without mic */
    }
    try {
      cam.enableCam(true);
    } catch {
      /* continue even without camera */
    }
    if (connect) {
      try {
        await connect();
      } catch (e: unknown) {
        setError((e as Error)?.message ?? "连接失败");
      }
    }
  }, [cam, mic, connect]);

  const doDisconnect = useCallback(async () => {
    userHangupRef.current = true;
    try {
      if (disconnect) await disconnect();
    } finally {
      setBotVolume(1);
    }
    setMessages([]);
    setDiagnostics([]);
    setAgentEvents([]);
    setApprovalQuestions([]);
    setApprovalProcessing(false);
    seenTranscriptsRef.current.clear();
    setAssistantActivity("idle");
    setScreenShareEnabled(false);
    setMediaSource(null);
    setMediaSourceUpdating(false);
    setError("");
  }, [disconnect, setBotVolume]);

  const leaveSession = useCallback(async () => {
    if (isConnected || isTransitioning) await doDisconnect();
    onLeave();
  }, [doDisconnect, isConnected, isTransitioning, onLeave]);

  /* ---------- Auto-reconnect on unexpected disconnect ---------- */
  useEffect(() => {
    if (transportState === "ready") {
      wasConnectedRef.current = true;
      userHangupRef.current = false;
      setReconnecting(false);
      return;
    }
    if (
      wasConnectedRef.current &&
      !userHangupRef.current &&
      (transportState === "disconnected" || transportState === "error") &&
      !reconnecting &&
      connect
    ) {
      setReconnecting(true);
      reconnectTimerRef.current = setTimeout(() => {
        Promise.resolve(connect()).catch(() => {
          /* 重连失败，3 秒后再次尝试 */
          reconnectTimerRef.current = setTimeout(() => {
            setReconnecting(false);
          }, 3000);
        });
      }, 1000);
    }
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [transportState, reconnecting, connect]);

  const sendText = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || !client) return;
      const messageId = createMessageId();
      const attachedMediaSource = mediaSource;
      setPendingSends((count) => count + 1);
      setAssistantActivity("thinking");
      setMessages((prev) => [
        ...prev,
        { id: messageId, role: "user", text, mediaSource: attachedMediaSource ?? undefined },
      ]);
      setInput("");
      try {
        await client.sendText(text, { run_immediately: true, audio_response: true });
        setMediaSource(null);
      } catch (err: unknown) {
        if (attachedMediaSource) {
          try {
            client.sendClientMessage("yuxi.media.attach", { source: null });
            setMediaSource(null);
          } catch {
            /* keep the original send failure as the user-facing error */
          }
        }
        setMessages((prev) =>
          prev.map((message) =>
            message.id === messageId ? { ...message, failed: true } : message,
          ),
        );
        setError((err as Error)?.message ?? "发送失败");
      } finally {
        setPendingSends((count) => Math.max(0, count - 1));
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    },
    [client, input, mediaSource],
  );

  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback(
      (data: TranscriptData) => {
        if (data.final && data.text?.trim() && mediaSource) setMediaSource(null);
      },
      [mediaSource],
    ),
  );

  const selectMediaSource = useCallback(
    async (source: MediaSource | null) => {
      if (!client || mediaSourceUpdating) return;
      if (source === "camera" && !cam.isCamEnabled) {
        setError("请先打开摄像头");
        return;
      }
      if (source === "screen" && !screenShareEnabled) {
        setError("请先开始屏幕共享");
        return;
      }

      setMediaSourceUpdating(true);
      setError("");
      try {
        client.sendClientMessage("yuxi.media.attach", { source });
        setMediaSource(source);
      } catch (err: unknown) {
        setError((err as Error)?.message ?? "图片附加设置失败");
      } finally {
        setMediaSourceUpdating(false);
      }
    },
    [cam.isCamEnabled, client, mediaSourceUpdating, screenShareEnabled],
  );

  const toggleCam = useCallback(() => {
    cam.enableCam(!cam.isCamEnabled);
  }, [cam]);

  const toggleMic = useCallback(() => mic.enableMic(!mic.isMicEnabled), [mic]);
  const toggleScreen = useCallback(async () => {
    if (!client) return;
    const enabled = !screenShareEnabled;
    try {
      await Promise.resolve(client.enableScreenShare(enabled));
      setScreenShareEnabled(enabled);
    } catch (err: unknown) {
      setError((err as Error)?.message ?? "屏幕共享切换失败");
    }
  }, [client, screenShareEnabled]);

  const submitApproval = useCallback(
    (answer: Record<string, unknown> | "reject") => {
      if (!client || approvalProcessing) return;
      setApprovalProcessing(true);
      setAssistantActivity("thinking");
      try {
        client.sendClientMessage("yuxi.approval.answer", answer);
      } catch (err: unknown) {
        setApprovalProcessing(false);
        setAssistantActivity("idle");
        setError((err as Error)?.message ?? "提交回答失败");
      }
    },
    [approvalProcessing, client],
  );

  const clampPipPosition = useCallback((x: number, y: number) => {
    const pip = pipRef.current;
    if (!pip) return { x, y };
    const padding = 12;
    return {
      x: Math.min(Math.max(padding, x), window.innerWidth - pip.offsetWidth - padding),
      y: Math.min(Math.max(padding, y), window.innerHeight - pip.offsetHeight - padding),
    };
  }, []);

  const startPipDrag = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const pip = pipRef.current;
      if (!pip) return;
      const rect = pip.getBoundingClientRect();
      dragOffsetRef.current = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
      pip.setPointerCapture(event.pointerId);
    },
    [],
  );

  const movePip = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
      setPipPosition(
        clampPipPosition(
          event.clientX - dragOffsetRef.current.x,
          event.clientY - dragOffsetRef.current.y,
        ),
      );
    },
    [clampPipPosition],
  );

  useEffect(() => {
    const handleResize = () => {
      setPipPosition((position) =>
        clampPipPosition(position.x, position.y),
      );
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [clampPipPosition]);

  /* ---------- Boot screen ---------- */
  if (!client) {
    return (
      <div className="boot-screen">
        <div className="boot-spinner" />
        <span>正在初始化 Sherlock…</span>
      </div>
    );
  }

  /* ---------- Render ---------- */
  return (
    <main className="call-shell" onClick={() => setShowLog(false)}>
      <header className="call-header">
        <div className="header-primary">
          <button type="button" className="icon-btn" title="返回 Agent 选择" onClick={() => void leaveSession()}>
            <ArrowLeft />
          </button>
          <div>
            <strong>{agentName}</strong>
            <span>Sherlock 实时对话</span>
          </div>
        </div>
        <div className="header-actions">
          <div className={`connection-badge${isConnected ? " connection-ready" : ""}${transportState === "error" ? " connection-error" : ""}`}>
            <i />
            <span>{stateLabel}</span>
          </div>
          {isConnected && (
            <div className="duration-badge">
              <Clock3 />
              <time>{formattedDuration}</time>
            </div>
          )}
          {isConnected && (
            <button
              type="button"
              className={`icon-btn${showLog ? " icon-btn-active" : ""}`}
              title="事件日志"
              onClick={(e) => {
                e.stopPropagation();
                setShowLog((v) => !v);
              }}
            >
              <Logs />
            </button>
          )}
        </div>
      </header>

      {error && (
        <button type="button" className="error-banner" onClick={() => setError("")}>
          {error}
        </button>
      )}

      <section className="call-content">
        <div className="assistant-stage">
          <div className={`assistant-presence assistant-${assistantActivity}${isConnected ? " assistant-online" : ""}`}>
            <div className="assistant-avatar">
              <Sparkles />
            </div>
            <strong>{agentName}</strong>
            <span>
              {!isConnected
                ? stateLabel
                : assistantActivity === "thinking"
                  ? "正在思考"
                  : assistantActivity === "speaking"
                    ? "正在回答"
                    : "正在聆听"}
            </span>
            <div className="sound-wave" aria-hidden="true">
              {Array.from({ length: 16 }, (_, index) => <i key={index} />)}
            </div>
          </div>

          {!isConnected && (
            <div className="start-call-panel">
              <p>开始后即可使用语音、视频、文字或共享屏幕与 Agent 对话。</p>
              <button type="button" className="start-call-action" onClick={doConnect} disabled={!isStable}>
                {isTransitioning ? <LoaderCircle className="spin" /> : <Phone />}
                <span>{isTransitioning ? stateLabel : "开始通话"}</span>
              </button>
            </div>
          )}
        </div>

        <aside className="conversation-panel">
          <header className="conversation-header">
            <div>
              <strong>实时对话</strong>
              <span>{messages.length > 0 ? `${messages.length} 条消息` : "语音转写与文字消息"}</span>
            </div>
            {diagnostics.length > 0 && (
              <span className="diagnostic-count" title={diagnostics.map(([key, value]) => `${key}: ${value}`).join("\n")}>
                媒体正常
              </span>
            )}
          </header>

          <div className="conversation-layer" ref={scrollRef}>
            {messages.length === 0 && assistantActivity === "idle" ? (
              <div className="conversation-empty">
                <Sparkles />
                <p>{isConnected ? "等待你开始对话" : "接通后，对话内容会显示在这里"}</p>
              </div>
            ) : (
              <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`message${message.role === "user" ? " message-user" : ""}${message.failed ? " message-failed" : ""}`}
                >
                  <span>{message.role === "user" ? "你" : "AI"}</span>
                  <p>{message.text}</p>
                  {message.mediaSource && (
                    <small className="message-media">
                      {message.mediaSource === "camera" ? "已附带摄像头画面" : "已附带屏幕画面"}
                    </small>
                  )}
                  {message.failed && <small>发送失败</small>}
                </div>
              ))}
              {assistantActivity !== "idle" && (
                <div className="assistant-activity" role="status">
                  <i />
                  {assistantActivity === "thinking" ? "AI 正在思考" : "AI 正在回答"}
                </div>
              )}
              </>
            )}
          </div>

          {approvalQuestions.length > 0 && (
            <ApprovalPrompt questions={approvalQuestions} processing={approvalProcessing} onSubmit={submitApproval} onReject={() => submitApproval("reject")} />
          )}

          {isConnected && (
            <div className="composer-shell">
              <div className="media-attach-control" aria-label="下一轮附带画面">
                <Paperclip aria-hidden="true" />
                <button type="button" className={!mediaSource ? "media-option-active" : ""} disabled={mediaSourceUpdating} onClick={() => void selectMediaSource(null)}>
                  不附图
                </button>
                <button type="button" className={mediaSource === "camera" ? "media-option-active" : ""} disabled={mediaSourceUpdating || !cam.isCamEnabled} onClick={() => void selectMediaSource("camera")} title={cam.isCamEnabled ? "下一轮附带摄像头画面" : "请先打开摄像头"}>
                  <Camera aria-hidden="true" />摄像头
                </button>
                {!isMobile && (
                  <button type="button" className={mediaSource === "screen" ? "media-option-active" : ""} disabled={mediaSourceUpdating || !screenShareEnabled} onClick={() => void selectMediaSource("screen")} title={screenShareEnabled ? "下一轮附带共享屏幕" : "请先开始屏幕共享"}>
                    <MonitorUp aria-hidden="true" />屏幕
                  </button>
                )}
              </div>
              <form className="text-composer" onSubmit={sendText}>
                <input ref={inputRef} type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="发送消息" autoComplete="off" />
                <button type="submit" className={pendingSends > 0 ? "send-pending" : ""} disabled={!input.trim() || mediaSourceUpdating} title="发送">
                  <SendHorizontal />
                </button>
              </form>
            </div>
          )}
        </aside>
      </section>

      <div className={`log-overlay${showLog ? " log-overlay-open" : ""}`} onClick={(event) => event.stopPropagation()}>
        <EventStreamPanel agentEvents={agentEvents} onClose={() => setShowLog(false)} />
      </div>

      {isConnected && (
        <nav className="call-controls" onClick={(event) => event.stopPropagation()} aria-label="通话控制">
          <button type="button" className={`control-button${!mic.isMicEnabled ? " control-muted" : ""}`} data-tooltip={mic.isMicEnabled ? "关闭麦克风" : "打开麦克风"} onClick={toggleMic}>
            {mic.isMicEnabled ? <Mic /> : <MicOff />}
          </button>
          <button type="button" className={`control-button${cam.isCamEnabled ? " control-active" : ""}`} data-tooltip={cam.isCamEnabled ? "关闭摄像头" : "打开摄像头"} onClick={toggleCam}>
            {cam.isCamEnabled ? <Video /> : <VideoOff />}
          </button>
          {!isMobile && (
            <button type="button" className={`control-button${screenShareEnabled ? " control-active" : ""}`} data-tooltip={screenShareEnabled ? "停止共享" : "共享屏幕"} onClick={toggleScreen}>
              <MonitorUp />
            </button>
          )}
          <button type="button" className="control-button hangup-button" data-tooltip="挂断" onClick={doDisconnect}>
            <PhoneOff />
          </button>
        </nav>
      )}

      {isConnected && (
        <div ref={pipRef} className={`camera-pip${cam.isCamEnabled ? "" : " camera-pip-off"}`} aria-label="可拖动的摄像头预览" title="拖动调整预览位置" onPointerDown={startPipDrag} onPointerMove={movePip} onClick={(event) => event.stopPropagation()} style={{ left: pipPosition.x, top: pipPosition.y }}>
          <PipecatClientVideo participant="local" fit="cover" mirror className="camera-pip-video" />
          {!cam.isCamEnabled && <CameraOff />}
          <span>{cam.isCamEnabled ? "你" : "摄像头已关闭"}</span>
        </div>
      )}
    </main>
  );
}
