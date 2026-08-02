import { StrictMode, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

import type { PipecatBaseChildProps } from '@pipecat-ai/voice-ui-kit';
import { PipecatAppBase } from '@pipecat-ai/voice-ui-kit';

import { App } from './components/App';
import {
  createTransportProps,
  DEFAULT_AI_PROFILE,
  DEFAULT_CASCADE_PROVIDER,
  DEFAULT_REALTIME_PROVIDER,
  DEFAULT_TRANSPORT,
  type AIMode,
  type AIProvider,
} from './config';
import './index.css';

const CLIENT_OPTIONS = {
  enableCam: true,
  enableMic: true,
};

const THEME_PROPS = {
  defaultTheme: 'terminal' as const,
  disableStorage: true,
};

export const Main = () => {
  const [mode, setMode] = useState<AIMode>(DEFAULT_AI_PROFILE.mode);
  const [realtimeProvider, setRealtimeProvider] = useState<AIProvider>(
    DEFAULT_REALTIME_PROVIDER
  );
  const [cascadeProvider, setCascadeProvider] = useState<AIProvider>(
    DEFAULT_CASCADE_PROVIDER
  );
  const provider = mode === 'realtime' ? realtimeProvider : cascadeProvider;
  const handleProviderChange = (nextProvider: AIProvider) => {
    if (mode === 'realtime') {
      setRealtimeProvider(nextProvider);
    } else {
      setCascadeProvider(nextProvider);
    }
  };
  const transportProps = useMemo(
    () => createTransportProps(DEFAULT_TRANSPORT, { mode, provider }),
    [mode, provider]
  );

  return (
    <PipecatAppBase
      {...transportProps}
      clientOptions={CLIENT_OPTIONS}
      initDevicesOnMount
      themeProps={THEME_PROPS}
      transportType={DEFAULT_TRANSPORT}>
      {({ client, handleConnect, handleDisconnect, error }: PipecatBaseChildProps) =>
        client ? (
          <App
            client={client}
            error={error}
            handleConnect={handleConnect}
            handleDisconnect={handleDisconnect}
            mode={mode}
            onModeChange={setMode}
            onProviderChange={handleProviderChange}
            provider={provider}
          />
        ) : (
          <div className="boot-screen" role="status">
            <span className="boot-spinner" />
            <span>正在准备摄像头</span>
          </div>
        )
      }
    </PipecatAppBase>
  );
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Main />
  </StrictMode>
);
