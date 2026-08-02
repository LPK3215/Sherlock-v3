import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';

import { RTVIEvent, type PipecatClient } from '@pipecat-ai/client-js';
import {
  PipecatClientVideo,
  usePipecatClientCamControl,
  usePipecatClientMicControl,
  usePipecatClientScreenShareControl,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from '@pipecat-ai/client-react';
import type { PipecatBaseChildProps } from '@pipecat-ai/voice-ui-kit';
import {
  CameraOff,
  LoaderCircle,
  Mic,
  MicOff,
  MonitorUp,
  Phone,
  PhoneOff,
  SendHorizontal,
  Video,
  VideoOff,
} from 'lucide-react';

import type { AIMode, AIProvider } from '../config';

interface AppProps extends Omit<PipecatBaseChildProps, 'client'> {
  client: PipecatClient;
  mode: AIMode;
  provider: AIProvider;
  onModeChange: (mode: AIMode) => void;
  onProviderChange: (provider: AIProvider) => void;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

interface MediaDiagnostics {
  profile?: string;
  audio_in_frames: number;
  camera_frames: number;
  screen_frames: number;
  text_in_frames: number;
  audio_out_frames: number;
  requested_images: number;
}

const EMPTY_DIAGNOSTICS: MediaDiagnostics = {
  audio_in_frames: 0,
  camera_frames: 0,
  screen_frames: 0,
  text_in_frames: 0,
  audio_out_frames: 0,
  requested_images: 0,
};

const READY_STATES = new Set(['disconnected', 'initialized', 'error', 'ready']);

const STATE_LABELS: Record<string, string> = {
  authenticated: '正在建立安全连接',
  authenticating: '正在验证连接',
  connected: '正在等待 AI',
  connecting: '正在连接',
  disconnected: '尚未接通',
  disconnecting: '正在挂断',
  error: '连接失败',
  initialized: '可以开始通话',
  initializing: '正在准备设备',
  ready: 'AI 已接通',
};

export const App = ({
  client,
  error,
  handleConnect,
  handleDisconnect,
  mode,
  onModeChange,
  onProviderChange,
  provider,
}: AppProps) => {
  const transportState = usePipecatClientTransportState();
  const { enableCam, isCamEnabled } = usePipecatClientCamControl();
  const { enableMic, isMicEnabled } = usePipecatClientMicControl();
  const { enableScreenShare, isScreenShareEnabled } =
    usePipecatClientScreenShareControl();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [textError, setTextError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [diagnostics, setDiagnostics] =
    useState<MediaDiagnostics>(EMPTY_DIAGNOSTICS);
  const messageCounter = useRef(0);
  const activeBotMessage = useRef<string | null>(null);
  const botSegments = useRef(new Map<number, string>());
  const botTurnCounter = useRef(0);
  const botTurnOpen = useRef(false);
  const lastTypedMessage = useRef<{ text: string; at: number } | null>(null);

  const isConnected = transportState === 'ready';
  const isBusy = !READY_STATES.has(transportState);
  const profile = `${mode}/${provider}`;
  const isAIReady = isConnected && diagnostics.profile === profile;

  useEffect(() => {
    if (!isConnected || isAIReady) return;
    const timeout = window.setTimeout(() => {
      setTextError('AI 后端未就绪，请检查所选模型的服务配置和后端日志');
    }, 8000);
    return () => window.clearTimeout(timeout);
  }, [isAIReady, isConnected]);

  const appendMessage = useCallback((role: ChatMessage['role'], content: string) => {
    const value = content.trim();
    if (!value) return;
    setMessages((current) => {
      const last = current.at(-1);
      if (last?.role === role && last.text === value) return current;
      messageCounter.current += 1;
      return [
        ...current,
        { id: `${role}-${messageCounter.current}`, role, text: value },
      ].slice(-12);
    });
  }, []);

  useRTVIClientEvent(RTVIEvent.UserTranscript, (data) => {
    if (!data.final) return;
    const typed = lastTypedMessage.current;
    if (typed && typed.text === data.text.trim() && Date.now() - typed.at < 5000) {
      lastTypedMessage.current = null;
      return;
    }
    appendMessage('user', data.text);
  });

  useRTVIClientEvent(RTVIEvent.BotOutput, (data) => {
    const value = data.text;
    if (!value.trim()) return;
    if (!botTurnOpen.current) {
      botTurnCounter.current += 1;
      botTurnOpen.current = true;
    }

    let id: string;
    if (typeof data.segment_id === 'number') {
      id =
        botSegments.current.get(data.segment_id) ??
        `assistant-${botTurnCounter.current}-${data.segment_id}`;
      botSegments.current.set(data.segment_id, id);
    } else {
      id = activeBotMessage.current ?? `assistant-live-${++messageCounter.current}`;
      activeBotMessage.current = id;
    }

    setMessages((current) => {
      const existing = current.find((message) => message.id === id);
      if (!existing) {
        const message: ChatMessage = { id, role: 'assistant', text: value.trim() };
        return [...current, message].slice(-12);
      }
      const nextText = value.startsWith(existing.text)
        ? value
        : existing.text.endsWith(value)
          ? existing.text
          : existing.text + value;
      return current.map((message) =>
        message.id === id ? { ...message, text: nextText } : message
      );
    });
  });

  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, () => {
    activeBotMessage.current = null;
    botSegments.current.clear();
    botTurnOpen.current = false;
  });

  useRTVIClientEvent(RTVIEvent.ServerMessage, (data) => {
    if (!data || typeof data !== 'object') return;
    const payload = data as Record<string, unknown>;
    if (payload.type === 'session-profile' && typeof payload.profile === 'string') {
      setDiagnostics((current) => ({ ...current, profile: payload.profile as string }));
      setTextError(null);
    }
    if (payload.type === 'configuration-error' && typeof payload.message === 'string') {
      setTextError(payload.message);
    }
    if (payload.type === 'media-diagnostics') {
      setDiagnostics((current) => ({
        ...current,
        ...Object.fromEntries(
          Object.entries(payload).filter(
            ([key, value]) => key !== 'type' && (typeof value === 'number' || key === 'profile')
          )
        ),
      }));
    }
  });

  const toggleCall = () => {
    if (isConnected) {
      setTextError(null);
      void handleDisconnect?.();
      return;
    }
    setMessages([]);
    setDiagnostics(EMPTY_DIAGNOSTICS);
    setTextError(null);
    void handleConnect?.();
  };

  const sendText = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = text.trim();
    if (!value || !isAIReady || isSending) return;
    setIsSending(true);
    setTextError(null);
    lastTypedMessage.current = { text: value, at: Date.now() };
    try {
      await client.sendText(value, { run_immediately: true, audio_response: true });
      appendMessage('user', value);
      setText('');
    } catch (sendFailure) {
      lastTypedMessage.current = null;
      setTextError(
        sendFailure instanceof Error ? sendFailure.message : '文字消息发送失败'
      );
    } finally {
      setIsSending(false);
    }
  };

  return (
    <main className="call-shell">
      <div className="video-stage" aria-label="本地摄像头画面">
        <PipecatClientVideo
          className="camera-feed"
          fit="cover"
          mirror
          participant="local"
        />
        {!isCamEnabled && (
          <div className="camera-off-state">
            <CameraOff aria-hidden="true" size={34} strokeWidth={1.7} />
            <span>摄像头已关闭</span>
          </div>
        )}
        <div className="video-shade" aria-hidden="true" />
      </div>

      <header className="call-header">
        <div className="call-identity">
          <span className={`status-dot status-${transportState}`} />
          <div>
            <strong>AI 视频助手</strong>
            <span>
              {transportState === 'ready' && !isAIReady
                ? '正在等待 AI'
                : STATE_LABELS[transportState] ?? transportState}
            </span>
          </div>
        </div>

        <div className="header-actions">
          {isScreenShareEnabled && (
            <div className="screen-status">
              <MonitorUp aria-hidden="true" size={16} />
              <span>正在共享屏幕</span>
            </div>
          )}
          <div className="profile-controls" aria-label="AI 管线选择">
            <label>
              <span>模式</span>
              <select
                aria-label="AI 处理模式"
                disabled={isConnected || isBusy}
                onChange={(event) => onModeChange(event.target.value as AIMode)}
                value={mode}>
                <option value="realtime">实时直连</option>
                <option value="cascade">级联</option>
              </select>
            </label>
            <label>
              <span>模型</span>
              <select
                aria-label="模型供应商"
                disabled={isConnected || isBusy}
                onChange={(event) =>
                  onProviderChange(event.target.value as AIProvider)
                }
                value={provider}>
                <option value="google">Google</option>
                <option value="openai">OpenAI</option>
                {mode === 'cascade' && (
                  <option value="openai-compatible">Qwen / OpenAI 兼容</option>
                )}
              </select>
            </label>
          </div>
        </div>
      </header>

      {(error || textError) && (
        <div className="error-banner" role="alert">
          {error || textError}
        </div>
      )}

      {isConnected && (
        <div className="diagnostic-strip" aria-label="实时媒体诊断">
          <span className={diagnostics.profile === profile ? 'verified' : ''}>
            {diagnostics.profile ?? profile}
          </span>
          <span>麦克风 {diagnostics.audio_in_frames}</span>
          <span>摄像头 {diagnostics.camera_frames}</span>
          <span>屏幕 {diagnostics.screen_frames}</span>
          <span>视觉请求 {diagnostics.requested_images}</span>
          <span>AI 语音 {diagnostics.audio_out_frames}</span>
        </div>
      )}

      {messages.length > 0 && (
        <div className="conversation-layer" aria-live="polite">
          {messages.map((message) => (
            <div className={`message message-${message.role}`} key={message.id}>
              <span>{message.role === 'user' ? '你' : 'AI'}</span>
              <p>{message.text}</p>
            </div>
          ))}
        </div>
      )}

      <form className="text-composer" onSubmit={sendText}>
        <input
          aria-label="发送文字消息"
          disabled={!isAIReady || isSending}
          onChange={(event) => setText(event.target.value)}
          placeholder={isAIReady ? '输入消息' : '接通后可输入消息'}
          value={text}
        />
        <button
          aria-label="发送"
          data-tooltip="发送"
          disabled={!isAIReady || isSending || !text.trim()}
          type="submit">
          {isSending ? (
            <LoaderCircle aria-hidden="true" className="spin" />
          ) : (
            <SendHorizontal aria-hidden="true" />
          )}
        </button>
      </form>

      <nav className="call-controls" aria-label="视频通话控制">
        <button
          aria-label={isMicEnabled ? '关闭麦克风' : '打开麦克风'}
          aria-pressed={!isMicEnabled}
          className={`control-button ${isMicEnabled ? '' : 'control-muted'}`}
          data-tooltip={isMicEnabled ? '关闭麦克风' : '打开麦克风'}
          onClick={() => enableMic(!isMicEnabled)}
          type="button">
          {isMicEnabled ? <Mic aria-hidden="true" /> : <MicOff aria-hidden="true" />}
        </button>

        <button
          aria-label={isCamEnabled ? '关闭摄像头' : '打开摄像头'}
          aria-pressed={!isCamEnabled}
          className={`control-button ${isCamEnabled ? '' : 'control-muted'}`}
          data-tooltip={isCamEnabled ? '关闭摄像头' : '打开摄像头'}
          onClick={() => enableCam(!isCamEnabled)}
          type="button">
          {isCamEnabled ? <Video aria-hidden="true" /> : <VideoOff aria-hidden="true" />}
        </button>

        <button
          aria-label={isScreenShareEnabled ? '停止共享屏幕' : '共享屏幕'}
          aria-pressed={isScreenShareEnabled}
          className={`control-button ${isScreenShareEnabled ? 'control-active' : ''}`}
          data-tooltip={isScreenShareEnabled ? '停止共享屏幕' : '共享屏幕'}
          disabled={!isConnected}
          onClick={() => enableScreenShare(!isScreenShareEnabled)}
          type="button">
          <MonitorUp aria-hidden="true" />
        </button>

        <button
          aria-label={isConnected ? '挂断' : '呼叫 AI'}
          className={`control-button call-button ${isConnected ? 'hangup-button' : 'start-button'}`}
          data-tooltip={isConnected ? '挂断' : '呼叫 AI'}
          disabled={isBusy}
          onClick={toggleCall}
          type="button">
          {isBusy ? (
            <LoaderCircle aria-hidden="true" className="spin" />
          ) : isConnected ? (
            <PhoneOff aria-hidden="true" />
          ) : (
            <Phone aria-hidden="true" />
          )}
        </button>
      </nav>
    </main>
  );
};
