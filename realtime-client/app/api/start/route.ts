import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  // Use BOT_START_URL from environment or fallback to localhost
  const botStartUrl =
    process.env.BOT_START_URL || 'http://localhost:7860/start';

  try {
    // Prepare headers - make API key optional
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Only add Authorization header if API key is provided
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

    const response = await fetch(botStartUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        createDailyRoom: false,
        enableDefaultIceServers: true,
        transport: 'webrtc',
        body: {
          yuxi_access_token: yuxiAccessToken,
          agent_slug: agentSlug,
          thread_id: threadId,
        },
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
