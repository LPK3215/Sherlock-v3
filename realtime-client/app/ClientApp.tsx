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
  CameraOff,
  Camera,
  LoaderCircle,
  Logs,
  Mic,
  MicOff,
  MonitorUp,
  Paperclip,
  Phone,
  PhoneOff,
  SendHorizontal,
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
  onThreadChange: (threadId: string) => void;
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

export function ClientApp({ agentName, connect, disconnect, isMobile, onThreadChange }: Props) {
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const seenTranscriptsRef = useRef(new Set<string>());
  const pipRef = useRef<HTMLDivElement>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const [pipPosition, setPipPosition] = useState({ x: 24, y: 82 });

  /* ---------- Derived ---------- */
  const isConnected = transportState === "ready";
  const isTransitioning =
    transportState === "connecting" ||
    transportState === "authenticating" ||
    transportState === "authenticated" ||
    transportState === "connected";

  const canMute = isConnected;
  const stateLabel = STATE_LABELS[transportState] ?? transportState;
  const isStable = READY_STATES.has(transportState);

  /* ---------- Derived: error ---------- */

  /* ---------- Auto-scroll ---------- */
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

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
      const msg = typeof data === "string" ? data : data;
      if (msg && (msg as Record<string, unknown>).type === "media-diagnostics") {
        const entries = Object.entries((msg as Record<string, unknown>).payload as object ?? {}) as Diagnostic[];
        setDiagnostics(entries);
      }
      if (msg && (msg as Record<string, unknown>).type === "yuxi-agent-event") {
        const payload = (msg as Record<string, unknown>).payload as Record<string, unknown>;
        const eventType = typeof payload?.type === "string" ? payload.type : "yuxi.event";
        setAgentEvents((current) => [
          ...current.slice(-499),
          { id: createMessageId(), timestamp: new Date(), type: eventType, data: payload },
        ]);
        if (typeof payload?.thread_id === "string") onThreadChange(payload.thread_id);
        if (eventType === "approval.required") {
          const detail = payload.detail as Record<string, unknown> | undefined;
          const interruptInfo = detail?.interrupt_info as Record<string, unknown> | undefined;
          const questions = normalizeApprovalQuestions(detail?.questions ?? interruptInfo?.questions);
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
            await client.sendClientRequest("yuxi.media.attach", { source: null }, 5000);
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
        await client.sendClientRequest("yuxi.media.attach", { source }, 5000);
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
      {/* ========== Video stage ========== */}
      <div className="video-stage">
        <PipecatClientVideo
          participant="local"
          fit="cover"
          mirror
          className="camera-feed"
        />

        {!cam.isCamEnabled && (
          <div className="camera-off-state">
            <CameraOff size={36} strokeWidth={1.4} />
            <span>摄像头已关闭</span>
          </div>
        )}

        <div className="video-shade" />
      </div>

      {/* ========== Header ========== */}
      <header className="call-header">
        <div className="call-identity">
          <div
            className={`status-dot${isConnected ? " status-ready" : ""}${
              isTransitioning ? " status-connecting" : ""
            }${transportState === "error" ? " status-error" : ""}`}
          />
          <div>
            <strong>{agentName}</strong>
            <span className="state-label">{stateLabel}</span>
          </div>
        </div>

        {isConnected && (
          <div className="header-actions">
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
          </div>
        )}
      </header>

      {/* ========== Error banner ========== */}
      {error && (
        <div className="error-banner" onClick={() => setError("")}>
          {error}
        </div>
      )}

      {/* ========== Diagnostic strip ========== */}
      {isConnected && diagnostics.length > 0 && (
        <div className="diagnostic-strip">
          {diagnostics.map(([k, v]) => (
            <span key={k}>
              {k}: {String(v).slice(0, 28)}
            </span>
          ))}
        </div>
      )}

      {/* ========== Conversation and live events ========== */}
      {isConnected && (
        <section
          className={`interaction-workspace${showLog ? " workspace-log-open" : ""}`}
        >
          {(messages.length > 0 || assistantActivity !== "idle") && (
            <div className="conversation-layer" ref={scrollRef}>
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
            </div>
          )}

          {approvalQuestions.length > 0 && (
            <ApprovalPrompt
              questions={approvalQuestions}
              processing={approvalProcessing}
              onSubmit={submitApproval}
              onReject={() => submitApproval("reject")}
            />
          )}

          <div
            className={`log-overlay${showLog ? " log-overlay-open" : ""}`}
            onClick={(e) => e.stopPropagation()}
          >
            <EventStreamPanel agentEvents={agentEvents} onClose={() => setShowLog(false)} />
          </div>
        </section>
      )}

      {/* ========== Text composer ========== */}
      {isConnected && (
        <div className="composer-shell">
          <div className="media-attach-control" aria-label="下一轮附带画面">
            <Paperclip aria-hidden="true" />
            <button
              type="button"
              className={!mediaSource ? "media-option-active" : ""}
              disabled={mediaSourceUpdating}
              onClick={() => void selectMediaSource(null)}
            >
              不附图
            </button>
            <button
              type="button"
              className={mediaSource === "camera" ? "media-option-active" : ""}
              disabled={mediaSourceUpdating || !cam.isCamEnabled}
              onClick={() => void selectMediaSource("camera")}
              title={cam.isCamEnabled ? "下一轮附带摄像头画面" : "请先打开摄像头"}
            >
              <Camera aria-hidden="true" />
              摄像头
            </button>
            {!isMobile && (
              <button
                type="button"
                className={mediaSource === "screen" ? "media-option-active" : ""}
                disabled={mediaSourceUpdating || !screenShareEnabled}
                onClick={() => void selectMediaSource("screen")}
                title={screenShareEnabled ? "下一轮附带共享屏幕" : "请先开始屏幕共享"}
              >
                <MonitorUp aria-hidden="true" />
                屏幕
              </button>
            )}
          </div>
          <form className="text-composer" onSubmit={sendText}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="发送消息…"
              autoComplete="off"
            />
            <button
              type="submit"
              className={pendingSends > 0 ? "send-pending" : ""}
              disabled={!input.trim() || mediaSourceUpdating}
              title="发送"
            >
              <SendHorizontal />
            </button>
          </form>
        </div>
      )}

      {/* ========== Call controls ========== */}
      <nav className="call-controls" onClick={(e) => e.stopPropagation()}>
        {/* Mic */}
        <button
          type="button"
          className={`control-button${!mic.isMicEnabled ? " control-muted" : ""}`}
          data-tooltip={mic.isMicEnabled ? "麦克风已开" : "麦克风已关"}
          onClick={toggleMic}
          disabled={transportState === "disconnecting"}
        >
          {mic.isMicEnabled ? <Mic /> : <MicOff />}
        </button>

        {/* Camera */}
        <button
          type="button"
          className={`control-button${cam.isCamEnabled ? " control-active" : ""}`}
          data-tooltip={cam.isCamEnabled ? "摄像头已开" : "摄像头已关"}
          onClick={toggleCam}
          disabled={!isStable && isConnected}
        >
          {cam.isCamEnabled ? <Video /> : <VideoOff />}
        </button>

        {/* Screen share (desktop only) */}
        {!isMobile && (
          <button
            type="button"
            className={`control-button${screenShareEnabled ? " control-active" : ""}`}
            data-tooltip={screenShareEnabled ? "屏幕共享中" : "屏幕共享已关"}
            onClick={toggleScreen}
            disabled={!canMute}
          >
            <MonitorUp />
          </button>
        )}

        {/* Call / Hangup */}
        {isConnected ? (
          <button
            type="button"
            className="control-button call-button hangup-button"
            data-tooltip="挂断"
            onClick={doDisconnect}
          >
            <PhoneOff />
          </button>
        ) : (
          <button
            type="button"
            className="control-button call-button start-button"
            data-tooltip="开始通话"
            onClick={doConnect}
            disabled={!isStable}
          >
            {isTransitioning ? <LoaderCircle className="spin" /> : <Phone />}
          </button>
        )}
      </nav>

      {/* ========== PIP (connected) ========== */}
      {isConnected && (
        <div
          ref={pipRef}
          className="camera-pip"
          aria-label="可拖动的全局摄像头预览"
          title="拖动调整预览位置"
          onPointerDown={startPipDrag}
          onPointerMove={movePip}
          onClick={(event) => event.stopPropagation()}
          style={{
            left: pipPosition.x,
            top: pipPosition.y,
          }}
        >
          <PipecatClientVideo
            participant="local"
            fit="contain"
            mirror
            className="camera-pip-video"
          />
        </div>
      )}
    </main>
  );
}
