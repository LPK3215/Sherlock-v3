# Yuxi 全模态实时 Agent 集成实施计划

> 文档状态：实施中（阶段 1-4 已完成，下一步进入阶段 5：显式图片和屏幕输入）
>
> 编写日期：2026-08-02
>
> 目标：将 Sherlock 已验证的实时语音、视频、屏幕和文字交互能力，作为 Yuxi 的原生实时通道接入，完整复用 Yuxi 的 Agent、LangGraph、工具、Skills、MCP、知识库、记忆、权限、持久化、运行事件和管理能力。

---

## 1. 执行结论

本项目不再新建第二套简化 LangGraph Agent 系统，也不让 Pipecat 与 Yuxi 分别维护提示词、工具、记忆和会话。

最终采用以下分工：

- **Yuxi 是唯一 AI 系统和业务事实来源**：负责用户、Agent、模型、提示词、LangGraph、工具、Skills、MCP、知识库、记忆、Conversation、AgentRun、checkpoint、权限、用量和审计。
- **Pipecat 是实时媒体运行时**：负责 WebRTC、音频/视频轨道、VAD、STT、TTS、本地播放打断和实时画面缓存。
- **Realtime Channel Adapter 是唯一集成边界**：负责身份和线程映射、标准 Agent Run 提交、Yuxi SSE 事件消费、TTS 文本分段、运行打断协调和实时画面工具回调。
- **现有 Sherlock 页面是第一阶段验证客户端**：先保留 Next.js 页面，避免在验证后端集成时同时重写为 Vue。集成稳定后再决定保留独立客户端还是迁入 Yuxi Web。

物理上可以存在 Yuxi API、Yuxi Worker、Realtime Gateway 等多个进程，但逻辑上只能有一套 Agent 状态。多个服务不是多个 AI 系统；两套提示词、工具、记忆和会话才是两个系统。

---

## 2. 研究基线与已确认事实

### 2.1 版本基线

- Yuxi 官方仓库：<https://github.com/xerrors/Yuxi>
- Yuxi 稳定标签：`v0.7.1`，Git SHA `dfb3aa203ab3d6390465d99f718e5d7fce50eecb`
- 调研时 Yuxi `main`：Git SHA `4bca27add619729085f3acfe314fe09e9b3f81fe`
- 调研时 Pipecat `main`：Git SHA `c49bf69df42f235c125a2602fbfe8aec005b02e9`

正式开发不能直接依赖移动的 `main`。阶段 0 必须选择明确的 Yuxi 和 Pipecat 版本，生成兼容性锁文件，并在升级时重新执行集成测试。

### 2.2 Yuxi 已有能力

根据 Yuxi 官方 `ARCHITECTURE.md`、Agent 文档和源码，以下能力无需重复实现：

- FastAPI 登录、用户、多租户和权限边界
- 数据库中的 Agent 实例和运行配置
- LangGraph Agent、PostgreSQL/SQLite checkpoint
- Agent Context 与系统提示词
- 内置工具、动态工具、工具审批
- Skills、MCP、SubAgents
- 知识库、知识图谱、文件和沙盒
- PostgreSQL Conversation、Message、AgentRun 和 Request
- Redis/ARQ 请求投递和 Redis Stream 运行事件
- SSE 流式事件、断线重连和游标恢复
- 长上下文 Summary Middleware
- `AGENTS.md`、`USER.md`、`MEMORY.md` 跨对话工作区信息
- Token Usage、Langfuse、反馈和评估相关能力

### 2.3 与实时通道直接相关的已确认接口

- 标准 Agent Run 入口支持创建 Request/Run，并返回 Request 或 Run 事件地址。
- `/api/agent/runs/{run_id}/events` 支持 SSE 和 `Last-Event-ID`/`after_seq` 恢复。
- Yuxi 输入消息支持文本和 OpenAI 格式的 `image_url` 多模态内容。
- Yuxi 支持 `enqueue`、`reject`、`steer` 请求策略。
- Yuxi 支持取消排队请求和取消已创建的 Agent Run。
- 当前 `Agent Call` 接口明确不支持 `stream=true`，不能作为实时语音的正式输出接口。
- 当前 Channel 入口只接受纯文本，必须新增实时多模态 Adapter，不能把视频能力硬塞进现有纯文本 Channel DTO。
- 当前 `steer` 不会强杀已经开始的模型调用和完整工具批次，只会在安全点接力下一次 Run。

### 2.4 记忆能力的准确边界

Yuxi 当前包含四种相关能力：

1. Conversation/Message 持久化：保存业务会话和消息事实。
2. LangGraph checkpoint：保存同一线程的 Agent 状态。
3. Summary Middleware：压缩长上下文，不等于长期用户记忆。
4. `USER.md`/`MEMORY.md`：保存跨对话偏好和事实，但不是自动语义记忆平台。

Pipecat 最新源码提供可选 Mem0 Processor，但 Pipecat 本质仍是媒体 Pipeline。接入 Yuxi 后，不在 Pipecat 中启用第二套长期记忆。未来若需要自动提取、检索和遗忘，应在 Yuxi 内新增统一 Memory Middleware 或 Memory Service。

---

## 3. 目标与非目标

### 3.1 必须实现

- 一个 Yuxi 用户可以从视频页面选择其有权访问的 Agent。
- 语音、文字、摄像头图片和屏幕图片进入同一个 Yuxi `thread_id`。
- 每一轮输入都经过 Yuxi 标准 Request/AgentRun 生命周期。
- Yuxi 输出按 token/文本片段实时进入 Pipecat TTS，不等待整段回答完成。
- 语音通道可以使用与 Web 通道相同的 Prompt、Tools、Skills、MCP、SubAgents、知识库和记忆。
- 工具调用、审批、错误、用量和终态可以显示在 Sherlock 的事件面板。
- 用户插话时，声音必须立即停止；后端状态必须在安全边界内继续、转向或取消。
- 摄像头和屏幕既支持随消息附图，也支持模型按需调用实时抓帧工具。
- 不开启实时模块时，Yuxi 原 Web、CLI、Agent Call、评估和 Worker 行为保持不变。

### 3.2 本计划暂不实现

- 连续逐帧视频理解或全程视频上传给模型
- 默认录制、保存或回放原始音视频
- 重写 Yuxi Agent Runtime
- 重新实现 Yuxi 已有用户、权限、工具、Skills、知识库或管理页面
- 第一阶段同时把 Next.js 视频页面重写为 Vue
- 在没有真实指标前提前做大规模分布式优化

---

## 4. 总体架构

```text
┌────────────────────────────────────────────────────────────┐
│ 用户端                                                     │
│ Sherlock 视频页面：音频 / 摄像头 / 屏幕 / 文字 / 事件 UI   │
└───────────────────────┬────────────────────────────────────┘
                        │ WebRTC + Data Channel/HTTPS
                        ▼
┌────────────────────────────────────────────────────────────┐
│ Realtime Gateway（Pipecat）                                │
│ Transport / VAD / STT / TTS / Barge-in / Frame Broker      │
└───────────────────────┬────────────────────────────────────┘
                        │ Realtime Channel Adapter
                        ▼
┌────────────────────────────────────────────────────────────┐
│ Yuxi 标准运行链路                                          │
│ RunSubmissionCommand → Request → AgentRun → ARQ Worker      │
│ → Agent Context → LangGraph → Middleware → Tools/Skills     │
│ → Redis Stream → SSE                                       │
└───────────────┬───────────────────────────┬────────────────┘
                │                           │
                ▼                           ▼
┌─────────────────────────────┐  ┌───────────────────────────┐
│ PostgreSQL / checkpoint     │  │ Redis / MinIO / Milvus    │
│ 用户、会话、消息、Run、状态 │  │ 事件、文件、知识和缓存    │
└─────────────────────────────┘  └───────────────────────────┘
```

### 4.1 唯一事实来源

| 数据 | 唯一来源 | Realtime Gateway 是否保存 |
|---|---|---|
| 用户和权限 | Yuxi PostgreSQL/Auth | 否，只缓存短期认证结果 |
| Agent 配置 | Yuxi Agent/Context | 否 |
| Prompt | Yuxi Agent Context | 否 |
| 工具、Skills、MCP | Yuxi Runtime | 否 |
| Conversation/Message | Yuxi PostgreSQL | 否 |
| Agent 状态 | LangGraph checkpoint | 否 |
| 长期记忆 | Yuxi Workspace/未来 Memory Service | 否 |
| 当前音视频轨道 | Pipecat Session | 是，仅会话生命周期 |
| 最新摄像头/屏幕帧 | Pipecat Frame Broker | 是，短 TTL，不默认持久化 |
| STT/TTS 运行态 | Pipecat Pipeline | 是，仅会话生命周期 |
| Agent Run 事件 | Yuxi Redis Stream/PostgreSQL 终态 | 只维护 SSE 游标和投影 |

---

## 5. 模块设计

### 5.1 Realtime Gateway

建议作为 Yuxi Docker Compose 中一个可选、独立扩缩容的服务，而不是塞进 FastAPI API 或 ARQ Worker 进程。

建议目录（最终名称可在阶段 0 确认）：

```text
realtime-gateway/
├── pyproject.toml
├── app/
│   ├── main.py                 # Pipecat runner / 服务入口
│   ├── settings.py             # STT/TTS/WebRTC 配置
│   ├── session_manager.py      # 实时会话生命周期
│   ├── frame_broker.py         # 摄像头/屏幕最新帧缓存
│   ├── yuxi_client.py          # Yuxi API/事件客户端
│   ├── run_bridge.py           # Request/Run/SSE 状态机
│   ├── event_mapper.py         # Yuxi 事件 → RTVI/UI/TTS
│   ├── interruption.py         # 本地打断与后端协调
│   └── security.py             # 短期令牌和内部调用验证
└── tests/
```

Gateway 只允许承担以下职责：

- 建立和关闭 WebRTC 会话
- 接收音频、摄像头和屏幕轨道
- VAD、STT、TTS 和音频播放控制
- 保存每种视频来源的最新一至三帧
- 调用 Yuxi 标准 Run 入口
- 消费 Request SSE 和 Run SSE
- 把模型文本增量送给 TTS
- 把 Yuxi 工具/状态事件投影给客户端
- 维护瞬时 `session_id → uid/agent/thread/run` 映射

Gateway 禁止承担：

- 自己调用第二个 LLM/VLM
- 自己维护系统提示词
- 自己注册与 Yuxi 重复的业务工具
- 自己维护长期记忆和聊天历史
- 绕过 Yuxi 权限直接选择 Agent、工具或知识库

### 5.2 Yuxi Realtime Adapter

Yuxi 侧采用增量扩展，不修改通用 Agent Graph 的默认行为。

建议新增：

```text
backend/server/routers/realtime_router.py
backend/package/yuxi/services/realtime_session_service.py
backend/package/yuxi/services/realtime_submission_service.py
backend/package/yuxi/agents/toolkits/realtime/
```

职责：

- 验证当前用户能否访问目标 Agent。
- 创建短期实时会话凭证。
- 为新会话创建或复用 Yuxi Conversation/thread。
- 将实时输入转换为 `AgentRunInputMessage`。
- 调用现有 `submit_run_command`，而不是复制 Request/Run 创建逻辑。
- 在 `RunOrigin` 中写入 `source=realtime`、`channel=voice|video` 和可信服务端元数据。
- 向运行 Context 注入只读隐藏字段，例如 `realtime_session_id`，但禁止客户端覆盖普通 Agent Context。
- 仅在实时会话有效时动态开放实时抓帧工具。

### 5.3 Session Registry

实时媒体状态是短期状态，默认使用 Redis TTL，不新增第二套长期 Session 数据库。

建议记录：

```json
{
  "session_id": "rt_xxx",
  "uid": "yuxi-user-id",
  "agent_slug": "assistant-slug",
  "thread_id": "yuxi-thread-id",
  "gateway_instance": "gateway-1",
  "connected_at": "ISO-8601",
  "last_heartbeat_at": "ISO-8601",
  "camera_enabled": true,
  "screen_enabled": false,
  "active_request_id": null,
  "active_run_id": null,
  "last_run_seq": "0-0"
}
```

约束：

- `uid` 只能从已验证的 Yuxi Token 获取，不能相信浏览器提交的 uid。
- 会话令牌必须短期有效，并绑定 `session_id`、`uid`、`agent_slug`。
- 心跳超时后清理帧缓存和内部回调能力。
- Conversation、Message、AgentRun 仍由 Yuxi PostgreSQL 保存。

### 5.4 Frame Broker

Frame Broker 负责让运行在 Yuxi Worker 中的工具按需读取当前实时画面。

- 每个 `session_id + source(camera|screen)` 保留最新帧或小型环形缓冲。
- 每帧记录 `captured_at`、尺寸、MIME、来源和新鲜度。
- 默认只存在内存中，必要时短期写入对象存储。
- 不默认保存原始连续视频。
- 工具请求必须携带仅服务端可获得的 capability token。
- 工具不能让模型自行传入其他用户的 session ID。
- 会话关闭后立即清理。

内部接口草案：

```http
POST /internal/realtime/sessions/{session_id}/frames/capture
Authorization: Bearer <internal-capability>
Content-Type: application/json

{
  "source": "camera",
  "max_age_ms": 1500,
  "wait_fresh_ms": 500
}
```

成功响应：

```json
{
  "session_id": "rt_xxx",
  "source": "camera",
  "mime_type": "image/jpeg",
  "width": 1280,
  "height": 720,
  "captured_at": "ISO-8601",
  "data_base64": "..."
}
```

轨道关闭、帧过期或会话失效必须返回结构化错误，工具再把错误转换为模型可理解但不泄漏内部信息的结果。

---

## 6. API 与事件契约草案

### 6.1 创建实时会话

```http
POST /api/realtime/sessions
Authorization: Bearer <yuxi-access-token>
Content-Type: application/json

{
  "agent_slug": "assistant-slug",
  "thread_id": null,
  "modalities": ["audio", "camera", "text"],
  "client": {
    "timezone": "Asia/Shanghai",
    "locale": "zh-CN"
  }
}
```

响应：

```json
{
  "session_id": "rt_xxx",
  "thread_id": "thread_xxx",
  "agent_slug": "assistant-slug",
  "gateway_url": "...",
  "gateway_token": "short-lived-token",
  "expires_at": "ISO-8601"
}
```

创建阶段必须完成：用户认证、Agent 可见性检查、Conversation 创建/复用、短期凭证签发。失败时不得先创建无主 WebRTC 会话。

### 6.2 提交实时 Turn

Gateway 内部把最终转写或文字消息转换为统一 Turn：

```json
{
  "request_id": "rt_req_xxx",
  "session_id": "rt_xxx",
  "thread_id": "thread_xxx",
  "agent_slug": "assistant-slug",
  "input": {
    "type": "text",
    "text": "用户最终转写",
    "images": []
  },
  "queue_policy": "steer"
}
```

实现时不重新创造 Yuxi Run 数据结构，而是转换成：

- `RunSubmissionCommand`
- `AgentRunInputMessage`
- `RunOrigin(source="realtime", channel="voice")`

### 6.3 标准化输出事件

Gateway 必须把 Yuxi SSE 转成稳定的客户端事件，不能让 UI 直接依赖 Yuxi 内部事件全部字段。

```text
run.queued
run.started
assistant.text.delta
assistant.text.completed
tool.started
tool.completed
tool.failed
approval.required
agent.interrupted
context.compressed
usage.updated
run.completed
run.cancelled
run.failed
```

每条事件至少包含：

```json
{
  "session_id": "rt_xxx",
  "thread_id": "thread_xxx",
  "request_id": "rt_req_xxx",
  "run_id": "run_xxx",
  "seq": "redis-stream-seq",
  "type": "assistant.text.delta",
  "timestamp": "ISO-8601",
  "payload": {}
}
```

`seq` 用于断线恢复和去重。TTS 只消费 `assistant.text.delta`，绝不能朗读工具日志、思考状态或内部错误栈。

---

## 7. 端到端业务时序

### 7.1 连接

1. 用户通过 Yuxi 登录获得 Access Token。
2. 视频页面请求创建实时会话并指定 `agent_slug`。
3. Yuxi 验证用户、Agent 权限和 thread 归属。
4. Yuxi 返回短期 Gateway Token。
5. 浏览器使用 Token 建立 WebRTC。
6. Gateway 写入 Redis Session Registry 并开始心跳。
7. 前端显示已连接，但 Agent 尚未产生 Run。

### 7.2 语音输入

1. Pipecat VAD 识别用户开始说话。
2. 如果 AI 正在朗读，立即停止本地 TTS 播放。
3. STT partial 只用于可选字幕，不写入 Yuxi Message。
4. STT final 生成唯一 `request_id`。
5. Gateway 提交标准 Yuxi Request/Run。
6. 如果返回 queued，先订阅 Request SSE；派发后切换到 Run SSE。
7. Yuxi Worker 使用原 Agent Context、Middleware、工具和 checkpoint 执行。
8. 文本 delta 进入分句缓冲，形成稳定片段后立即送 TTS。
9. Yuxi 保存用户消息、助手消息、工具调用和 Run 终态。

### 7.3 文字输入

文字和语音必须使用相同的 `thread_id`、Run 提交和 SSE 输出流程。区别只有输入来源元数据，禁止维护两套对话历史。

### 7.4 第一阶段图片输入

Yuxi 已支持多模态 `image_url` 输入。第一版视觉集成采用显式附图：

1. 用户提出视觉问题。
2. Gateway 从 Frame Broker 读取当前 camera/screen 帧。
3. 将文本和图片组成同一个 `AgentRunInputMessage`。
4. 使用支持视觉输入的 Yuxi 模型执行 Run。
5. 原始输入、消息和结果继续走 Yuxi 标准持久化。

在尚未完成按需工具前，可以通过客户端显式“附带当前画面”或受控策略附图；不建议无条件给每句话附图，因为会增加成本、延迟和隐私风险。

### 7.5 正式版按需抓帧

1. Yuxi Agent 判断需要看摄像头或屏幕。
2. Agent 调用 `capture_live_camera` 或 `capture_live_screen`。
3. 工具从可信 Runtime Context 获取隐藏 `realtime_session_id`。
4. 工具调用 Gateway 内部 Frame API。
5. Gateway 返回最新有效帧。
6. 工具把图片以当前模型和 LangChain 支持的多模态消息形式返回 Graph。
7. 工具调用全程仍产生 Yuxi Tool Event、审批和审计记录。

阶段 0 必须用技术探针验证“图片 ToolResult 进入下一次模型调用”的确切 LangChain 消息格式。如果供应商不支持图片 ToolResult，则采用受控替代方案：把图片存入 MinIO，并通过 LangGraph `Command`/状态更新追加多模态消息。不能在没有验证时把格式写死。

### 7.6 用户插话

插话分为媒体层和 Agent 层：

1. `UserStartedSpeaking` 到达时，Gateway 立即停止 TTS 和浏览器待播放音频。
2. 停止声音不等于立即破坏 Yuxi Run。
3. STT final 到达后，以 `steer` 提交新意图。
4. Yuxi 在模型/工具安全点结束当前 Graph，并在同一 thread 中派发新 Run。
5. 新 Run 从原 checkpoint 继续，避免丢失已经成功的工具结果。

必须接受的现状：Yuxi 当前 `steer` 不会强杀正在执行的模型调用和完整工具批次。因此第一版可以做到“声音立即停止、后端安全接力”，但不保证新 Run 在所有长工具执行中立即开始。

后续若要降低等待，只能新增受 `channel=realtime` 限制的安全取消能力：

- 模型 token 流可以取消。
- 无副作用、声明可取消的工具可以取消。
- 有副作用或不可重入工具不强杀。
- 取消后 checkpoint 和 AgentRun 终态必须一致。

### 7.7 工具审批和 Agent 中断

全功能集成不能忽略 Yuxi 的 `interrupted` 状态。

- `approval.required` 到达后停止继续朗读普通答案。
- 前端显示审批卡片；可选地用 TTS 简短说明需要确认。
- 用户按钮或明确语音回答转换为 Yuxi resume 请求。
- `ask_user_question` 同样映射为可见问题和 resume 输入。
- 在该能力完成前，实时 Agent 只能启用不需要人工审批的安全工具，不能静默自动批准高风险工具。

### 7.8 断线与恢复

- WebRTC 短暂断线：保留 Session Registry TTL，允许客户端重连。
- SSE 断线：使用最后的 `seq`/`Last-Event-ID` 恢复，不能重新朗读已消费文本。
- Gateway 崩溃：Yuxi Run 事实仍在 PostgreSQL/Redis；恢复后查询 active run 并续订事件。
- 用户主动挂断：停止媒体、清理 Frame Broker，按配置决定取消当前 Run 或允许后台完成。
- Yuxi 不可用：Gateway 返回明确状态，不在本地偷偷调用备用 LLM。

---

## 8. 管理能力映射

### 8.1 复用 Yuxi

| 管理能力 | 处理方式 |
|---|---|
| 用户、登录、角色、租户 | 完全复用 Yuxi |
| Agent 创建和可见性 | 完全复用 Yuxi |
| 系统提示词 | 复用 Agent Context |
| 模型 | 复用 Yuxi Model Provider/Agent 配置 |
| Tools、Skills、MCP | 完全复用 Yuxi |
| 知识库和图谱 | 完全复用 Yuxi |
| 对话、Run、反馈、用量 | 完全复用 Yuxi |
| Langfuse 和评估 | 复用并增加实时 trace 元数据 |

### 8.2 需要新增的实时配置

这些配置属于 Channel，不建议混入普通系统提示词：

- 是否允许实时通话
- 启用的输入模态：audio/camera/screen/text
- STT provider/model/language
- TTS provider/model/voice/speed
- VAD 参数
- camera/screen 抓帧策略和图片尺寸
- 插话策略
- 断线后 Run 处理策略
- 是否朗读工具审批和错误摘要

数据结构建议放在 `Agent.config_json.channels.realtime` 或独立 Realtime Profile 中，而不是让 Gateway 保存第二份配置。第一版可由环境变量提供默认值，但进入管理后台前必须迁回 Yuxi 数据源。

### 8.3 Prompt 规则

- Agent 的人格、任务和业务规则仍由 Yuxi `system_prompt` 管理。
- 语音表达要求可以增加一个由 Yuxi 管理的 `voice_prompt_suffix`。
- Gateway 不得私自拼接不可追踪的业务提示词。
- 每个 Run 需要记录有效 Agent 配置版本或配置快照，以支持回溯。
- 如果 Yuxi 当前缺少完整 Prompt 版本管理，应独立列为后续增强，不阻塞实时通道 PoC。

---

## 9. 分阶段实施计划

任何阶段未达到退出条件，不进入下一阶段。每阶段单独提交，保证可以回退。

### 阶段 0：兼容性探针和基线冻结

目标：用最少代码证明确切接口和依赖，不开始大规模迁移。

任务：

1. 选择固定 Yuxi 基线，优先从 `v0.7.1` 建集成分支，再逐项吸收 `main` 必需改动。
2. 选择并固定 Pipecat 版本，验证其支持 Yuxi Python `>=3.12,<3.14`；若依赖冲突，保持独立 Gateway 进程。
3. 启动 Yuxi LITE 模式，创建测试用户和测试 Agent。
4. 调用标准 `/api/agent/runs`，验证 Request → Run → SSE → completed。
5. 记录真实 SSE 事件样本和 token 事件格式。
6. 用同一 `thread_id` 连续运行两轮，验证 checkpoint 和历史。
7. 运行一个内置工具、一个 Skill、一个 MCP，确认事件可观察。
8. 提交一条文本+图片消息，确认目标视觉模型能理解。
9. 验证 `steer`、cancel、approval/resume 的实际状态转换。
10. 验证图片作为工具结果进入下一模型调用的支持方式。

退出条件：

- 以上十个探针形成自动化脚本和结果记录。
- 明确所有使用的 API、DTO、事件类型和版本。
- 没有需要绕过 Yuxi Run 生命周期才能完成的核心能力。
- 若标准 Run 无法提供可用文本增量，停止实施并先解决 Yuxi 流事件，不允许改用非流式 Agent Call 假装完成。

### 阶段 1：Realtime Gateway 骨架和身份闭环

目标：建立一个不调用 Agent 的安全 WebRTC 会话。

任务：

1. 在目标 Yuxi fork/monorepo 中新增可选 `realtime-gateway` 服务。
2. 实现 `/api/realtime/sessions` 创建接口。
3. 复用 Yuxi Token、Agent 可见性和 Conversation 权限。
4. 实现短期 Gateway Token。
5. 实现 Redis Session Registry、心跳和关闭清理。
6. 建立 WebRTC，验证麦克风、摄像头和屏幕轨道状态。
7. 所有日志加入 `session_id/uid/agent_slug/thread_id`，但不得记录 Token。

退出条件：

- 未登录用户不能创建会话。
- 用户不能连接无权访问的 Agent/thread。
- Gateway 停止不影响 Yuxi Web 和 Worker。
- 会话过期后不能继续读取帧或提交 Turn。

### 阶段 2：纯语音最小纵向链路

目标：完成 `语音 → Yuxi Agent → 流式文本 → 语音`，且所有消息进入 Yuxi。

任务：

1. 接入 VAD/STT，只把 final transcript 提交 Yuxi。
2. 实现 `run_bridge` 状态机，同时处理立即派发和 queued 两种响应。
3. 订阅 Request SSE，再切换到 Run SSE。
4. 实现事件去重、游标保存和断线重连。
5. 映射文本 delta，增加按标点/长度/超时的 TTS 分段器。
6. TTS 只消费最终可见助手文本流。
7. Run 完成后从 Yuxi 查询最终状态做一致性校验。
8. 前端文字输入复用同一路径。

退出条件：

- Yuxi Web 可以看到来自语音通道的用户和助手消息。
- 同一 thread 的 Web 对话和语音对话上下文一致。
- SSE 重连不重复显示或朗读文本。
- Gateway 中不存在业务 Prompt、LLM 或独立历史。

### 阶段 3：Agent 能力完整性验证

状态：**已完成（2026-08-03）**。验证记录见 `docs/vibe/2026-08-03-realtime-agent-capability-verification.md`。

目标：证明实时通道没有让 Yuxi 退化成普通聊天 API。

任务：

1. 从语音请求触发内置工具。
2. 触发 Skill 依赖工具。
3. 调用 MCP。
4. 检索知识库并保留引用。
5. 调用一个 SubAgent。
6. 验证 Summary Middleware 事件。
7. 验证同线程 checkpoint。
8. 验证 `USER.md/MEMORY.md` 内容对语音回答生效。
9. 把工具、压缩、用量、SubAgent 和错误事件投影到 System Event Monitor。

退出条件：

- 同一个 Agent 在 Web 和实时通道下可见资源一致。
- 工具调用记录、消息、Run、用量全部由 Yuxi 保存。
- 权限受限用户无法借实时通道调用不可见工具、Skill、MCP 或知识库。

### 阶段 4：插话、取消、审批和恢复

状态：**已完成（2026-08-03）**。审批卡片、按钮与语音回答、标准 resume Run、父 Run 关联、同 thread 重连恢复、语音插话停播与旧 Run 终态，以及有副作用工具的取消边界均已通过独立 Docker 浏览器 E2E。阶段记录见 `docs/vibe/2026-08-03-realtime-interruption-approval-resume.md`。

目标：达到可持续通话所需的控制语义。

任务：

1. `UserStartedSpeaking` 立即清空 TTS 播放队列。
2. STT final 使用 `steer` 提交。
3. 显示当前回答已被用户打断，但不伪造 Yuxi Run 终态。
4. 映射 Run cancel 和 queued request cancel。
5. 实现 approval/resume UI。
6. 实现 `ask_user_question` 的语音和按钮回答。
7. 对有副作用工具执行不可强杀测试。
8. 如需新增实时安全取消，只对 `channel=realtime` 启用并补齐 checkpoint 一致性测试。

退出条件：

- 用户开口后 100ms 级别停止本地声音；该指标不包含 STT 和后端执行。
- 新意图不会丢失，也不会错误追加到旧助手消息。
- 审批中的 Run 可以正确恢复。
- 工具不会因音频打断出现重复副作用。

### 阶段 5：显式图片和屏幕输入

目标：不依赖实时工具，先证明 Yuxi 原生多模态 Run 完整可用。

任务：

1. 实现 Frame Broker。
2. 为客户端提供“本轮附带摄像头/屏幕画面”的受控选项。
3. 压缩、缩放图片并生成 Yuxi 支持的 `image_url` 输入。
4. 校验 Agent 所选模型是否具备 vision 能力。
5. 记录图片来源、时间和尺寸；制定 MinIO/DB 保存策略。
6. 验证图片消息在 Web 历史中的兼容显示。

退出条件：

- 摄像头和屏幕图片都能进入同一个 Yuxi Agent Run。
- 模型能够回答基于真实画面的可验证问题。
- 不支持视觉的模型得到明确提示或受控回退，不能静默丢图。
- 默认不持久化原始连续视频。

### 阶段 6：按需实时媒体工具

目标：由 Yuxi Agent 自主决定何时查看实时画面。

任务：

1. 实现 Gateway 内部 Frame Capture API。
2. 实现 Yuxi `capture_live_camera`/`capture_live_screen` 工具。
3. 从可信 Runtime Context 注入 session，不把 session ID 暴露为模型参数。
4. 仅对有效实时会话动态挂载工具。
5. 验证图片 ToolResult/Graph 状态更新方案。
6. 增加超时、轨道关闭、帧陈旧、Gateway 重启等错误处理。
7. 工具事件正常进入 Yuxi 审计和前端事件面板。

退出条件：

- 普通 Yuxi Web Agent 不会看到无效实时工具。
- 模型可以按需抓取 camera/screen，并根据抓取结果回答。
- 用户 A 的工具不能访问用户 B 的帧。
- 失败时 Agent 得到结构化错误，Graph 不崩溃。

### 阶段 7：管理配置和统一体验

目标：把临时环境变量升级为 Yuxi 管理的产品配置。

任务：

1. 增加 Realtime Profile 或 `channels.realtime` 配置。
2. 增加 STT/TTS/voice/VAD/模态/抓帧/插话配置 UI。
3. 把当前 System Event Monitor 映射到标准化实时事件。
4. 增加会话质量指标、错误原因和媒体诊断。
5. 决定前端形态：继续独立 Next 客户端，或在行为冻结后移植为 Yuxi Vue 页面。
6. 如果保留 Next，统一域名、SSO、主题和导航；不使用第二套登录。

退出条件：

- 管理员可配置，普通用户只能使用被授权的实时能力。
- 修改 Agent 工具/Skill/Prompt 后，实时通道无需改代码即可生效。
- 前端技术选型不会改变后端协议和 Agent 状态。

### 阶段 8：生产加固

目标：从功能正确进入可部署、可监控和可恢复状态。

任务：

1. 并发会话和多 Gateway 实例路由。
2. Redis Session TTL、Gateway 心跳和孤儿 Run 清理。
3. 限流、配额、Token/音频分钟成本统计。
4. 图片、音频和日志的数据保留及删除策略。
5. Trace ID 贯通 Browser → Gateway → Request → Run → Tool → Model/TTS。
6. 故障注入：Yuxi API、Worker、Redis、模型、STT、TTS、WebRTC 分别不可用。
7. 安全评审：越权、内部回调伪造、跨租户帧读取、Prompt 注入和工具审批绕过。
8. 完整回归与灰度开关。

退出条件：

- 关闭 realtime feature flag 后，Yuxi 行为与集成前一致。
- 单个 Gateway 故障不会破坏 Yuxi 持久化事实。
- 所有敏感数据都有明确生命周期和访问控制。
- 达到经过实测确定的并发、延迟和成本目标。

---

## 10. 测试计划

### 10.1 单元测试

- Session Token 签发、过期、篡改和绑定校验
- Session Registry TTL 和状态转换
- STT partial/final 去重
- Yuxi SSE 解析、游标恢复和事件去重
- Yuxi 事件到客户端事件的映射
- TTS 分段，不拆坏中文标点、英文单词和代码
- Frame Broker 新鲜度、来源和会话隔离
- 插话状态机
- 轨道关闭和抓帧错误

### 10.2 集成测试

- 创建实时会话时复用 Yuxi Auth/Agent 权限
- Request queued → dispatched → Run SSE
- 同 thread 多轮 checkpoint
- Tool、Skill、MCP、知识库、SubAgent
- Approval/Resume 和 ask-user
- 图片输入和实时抓帧工具
- Run cancel/steer/failed/interrupted
- Gateway 重启后 SSE 恢复

### 10.3 端到端测试

至少覆盖：

1. 中文语音问答并听到中文语音。
2. AI 回答过程中用户插话。
3. 语音调用普通工具。
4. 语音调用需要审批的工具。
5. 语音触发 Skill 和 MCP。
6. 语音检索知识库并显示引用。
7. 摄像头人物/物体识别。
8. 屏幕文字或页面理解。
9. 挂断重连后继续同一 thread。
10. 在 Yuxi Web 中继续刚才的语音会话。

### 10.4 Yuxi 回归测试

每阶段都必须运行 Yuxi 原有：

- Agent sync/async E2E
- Agent request queue
- Agent run events
- steer/cancel
- tool approval
- Skills/MCP/SubAgent
- conversation history
- attachment/image input
- auth/tenant visibility

新增实时代码不得通过修改或跳过原测试来获得通过。

---

## 11. 性能指标

先测基线，再确定供应商相关目标。必须分别记录：

```text
用户停止说话
  → VAD end
  → STT final
  → Yuxi Request committed
  → Run dispatched
  → 模型 first token
  → TTS first audio
  → 浏览器开始播放
```

建议对“集成自身增加的延迟”设独立预算：

- Session Registry 查询：本地环境 p95 目标 `< 50ms`
- Gateway → Yuxi 提交和事件桥接额外开销：p95 目标 `< 300ms`
- SSE delta → TTS 分段器处理：p95 目标 `< 100ms`
- 用户开始说话 → 本地停止播放：目标 `< 150ms`

以上不包含 STT、LLM 和 TTS 供应商自身耗时。端到端首音频目标必须在阶段 2 用真实模型测量后冻结，不能用理想数字代替实测。

并发基线至少测试 1、5、20 个同时会话，记录 CPU、内存、音频实时率、Redis 延迟、Run 排队时间和模型限流。

---

## 12. 安全、隐私与数据生命周期

- Browser 只持有短期 Gateway Token，不持有 Gateway 内部 capability。
- Gateway Token 必须绑定用户、Agent、Session 和过期时间。
- Yuxi Worker 抓帧必须再次验证 Run uid 与 Session uid 一致。
- 不把 `session_id` 作为模型可自由填写的工具参数。
- 不在日志记录 Access Token、Gateway Token、完整 base64 图片和原始音频。
- 原始音频和视频默认不持久化。
- 临时帧在会话结束或 TTL 到期后删除。
- 如果图片需要进入历史，先定义用户提示、保存位置、租户隔离和删除接口。
- 工具审批不能因为来自语音通道而自动绕过。
- 内部 Gateway API 不向公网暴露，使用服务间认证和网络边界。

---

## 13. 故障边界与降级规则

| 故障 | 正确行为 | 禁止行为 |
|---|---|---|
| STT 失败 | 提示无法识别，可继续文字输入 | 伪造转写 |
| TTS 失败 | 保留文字回答，提示音频不可用 | 丢弃 Yuxi 回答 |
| Yuxi API/Worker 失败 | 明确显示失败并允许重试 | Gateway 偷偷调用备用 LLM |
| SSE 中断 | 从最后 seq 恢复 | 从头重复朗读 |
| Redis 暂时不可用 | 中止/恢复实时 Session，保护事实一致性 | 用本地状态伪装 Run 成功 |
| 摄像头关闭 | 实时工具返回 unavailable | 返回旧用户或其他会话帧 |
| 模型不支持图片 | 明确阻止或受控 OCR 回退 | 静默删除图片 |
| 工具超时 | 记录 Yuxi Tool Error | Gateway 伪造工具结果 |
| 用户挂断 | 清理媒体；按策略处理 Run | 删除 Yuxi 历史 |

---

## 14. 开发和 Git 策略

建议在目标 Yuxi fork 中建立独立分支，例如：

```text
feature/realtime-multimodal-channel
```

按阶段提交，避免一次性大合并：

```text
chore(realtime): pin compatibility baseline
feat(realtime): add authenticated session handshake
feat(realtime): bridge voice turns to agent runs
feat(realtime): stream agent events to tts
feat(realtime): support interruption and resume
feat(realtime): add explicit image turns
feat(realtime): add live camera and screen tools
feat(realtime): expose channel configuration
test(realtime): add multimodal regression suite
```

每次提交必须满足：

- 范围单一
- 可回退
- 有对应测试
- 不夹带 Yuxi 无关重构
- 不修改既有默认行为来迁就实时通道

---

## 15. Go/No-Go 决策门槛

### 可以进入正式集成

- 标准 Yuxi Agent Run 能提供稳定文本 delta。
- 标准 Run 下 Tools、Skills、MCP、checkpoint 和 Conversation 均正常。
- Yuxi 多模态图片输入在目标模型上可用。
- Gateway 可以在不维护第二套业务状态的情况下完成媒体桥接。
- 插话至少能做到本地立即静音和后端安全 steer。
- 版本依赖可以锁定或通过独立进程隔离。

### 必须暂停并重新设计

- 必须绕过 Yuxi Run/Worker 才能得到流式输出。
- 工具、Skills 或 checkpoint 在实时来源下无法运行。
- 图片只能由 Pipecat 自己的第二个 VLM 处理，不能进入 Yuxi Agent Context。
- 需要复制 Yuxi 用户、Agent、Prompt、Memory 或 Tool 数据库到 Gateway。
- 为支持实时通道必须改变所有普通 Yuxi Agent 的默认执行语义。
- 无法保证跨用户帧隔离或工具审批安全。

---

## 16. 最终验收清单

### 统一性

- [ ] 实时页面使用 Yuxi 用户身份。
- [ ] 实时页面选择 Yuxi Agent。
- [ ] 所有输入使用 Yuxi thread。
- [ ] 所有回答来自 Yuxi Agent Run。
- [ ] 没有第二套 Prompt、Tool、Skill、Memory、Conversation。

### Agent 能力

- [x] Prompt 和模型配置生效。
- [x] Tools 生效且有事件和审计。
- [x] Skills 生效。
- [x] MCP 生效。
- [x] SubAgent 生效。
- [x] 知识库和引用生效。
- [x] checkpoint、历史、Summary 和长期工作区信息生效。
- [x] 审批卡片、按钮结构化回答和标准 resume Run 生效。
- [x] 语音回答审批生效。

### 全模态

- [x] 语音输入可用。
- [x] 文字输入可用。
- [x] TTS 流式输出可用。
- [ ] 摄像头显式附图可用。
- [ ] 屏幕显式附图可用。
- [x] 摄像头按需工具可用。
- [x] 屏幕按需工具可用。
- [x] 回复未结束时再次发送文字会取消旧 Run，并正常执行新消息。
- [x] 语音插话可立即停止声音且不破坏 Agent 状态。

### 稳定与安全

- [ ] SSE 断线恢复不重复消息和语音。
- [ ] WebRTC 重连不串 Session。
- [ ] 多用户、多 Agent、多 thread 不串数据。
- [ ] 普通 Yuxi Web/CLI/API 回归通过。
- [ ] 默认不保存原始音视频。
- [ ] 权限、审批和内部回调不能绕过。
- [ ] 指标、日志、错误和成本可以关联到同一 trace/run。

---

## 17. 评审时需要最终确认的问题

以下问题不改变总体架构，但必须在阶段 0 或对应阶段前确认：

1. 正式集成基线选择 Yuxi `v0.7.1` 还是指定的后续版本？
2. Sherlock 页面长期保留 Next.js，还是功能稳定后迁移到 Yuxi Vue？
3. STT/TTS 首批固定哪些 provider，是否允许用户级音色配置？
4. 新会话默认新建 thread，还是允许用户选择历史 thread？
5. 摄像头开启时是否允许自动随 Turn 附图，还是必须用户/模型明确触发？
6. 挂断后未完成的 Agent Run 是取消还是后台完成？
7. 哪些工具在实时通道必须审批，审批主要使用按钮还是也支持语音？
8. 图片是否进入长期历史；若进入，保留多久？
9. 是否在第一版接入 `MEMORY.md` 即可，还是同步建设自动语义记忆？
10. 首期目标并发和可接受的端到端首音频延迟是多少？

评审确认后，先执行阶段 0。阶段 0 的目的不是再次讨论大方向，而是冻结版本和证明适配契约；只要探针结果满足 Go 条件，后续即可按阶段逐步实现，不需要重新设计整个系统。
