import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const botStartUrl =
    process.env.BOT_START_URL || 'http://localhost:7860/start';
  const yuxiApiUrl =
    process.env.YUXI_SERVER_URL || 'http://localhost:5050';

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (process.env.BOT_START_PUBLIC_API_KEY) {
      headers.Authorization = `Bearer ${process.env.BOT_START_PUBLIC_API_KEY}`;
    }

    const requestData = (await request.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const yuxiAccessToken =
      typeof requestData.yuxi_access_token === "string"
        ? requestData.yuxi_access_token
        : "";
    const agentSlug =
      typeof requestData.agent_slug === "string" ? requestData.agent_slug : "";
    const threadId =
      typeof requestData.thread_id === "string" ? requestData.thread_id : null;

    if (!yuxiAccessToken || !agentSlug) {
      return NextResponse.json(
        { error: "缺少 Yuxi 登录凭证或 Agent" },
        { status: 400 },
      );
    }

    // 通过 Yuxi API 将 access_token 存入 Redis，获取 session_id
    // Gateway 只收到 session_id，不再明文传递 token
    const sessionResponse = await fetch(
      `${yuxiApiUrl}/api/realtime/session`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${yuxiAccessToken}`,
        },
        body: JSON.stringify({
          agent_slug: agentSlug,
          thread_id: threadId,
        }),
      },
    );

    let yuxiSessionId: string | null = null;
    if (sessionResponse.ok) {
      const sessionData = await sessionResponse.json();
      yuxiSessionId = sessionData.session_id;
    }

    // 构建 Gateway 请求体：优先使用 session_id，回退到明文 token（兼容）
    const gatewayBody: Record<string, unknown> = {
      agent_slug: agentSlug,
    };
    if (yuxiSessionId) {
      gatewayBody.yuxi_session_id = yuxiSessionId;
    } else {
      gatewayBody.yuxi_access_token = yuxiAccessToken;
    }
    if (threadId) {
      gatewayBody.thread_id = threadId;
    }

    const response = await fetch(botStartUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        createDailyRoom: false,
        enableDefaultIceServers: true,
        transport: 'webrtc',
        body: gatewayBody,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to connect to Pipecat: ${response.statusText}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: `Failed to process connection request: ${error}` },
      { status: 500 }
    );
  }
}
