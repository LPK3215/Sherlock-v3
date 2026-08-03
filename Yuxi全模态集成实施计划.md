# Yuxi 全模态实时功能工程集成计划

> 状态：后端原生集成完成，前端待迁移
>
> 更新时间：2026-08-03
>
> 当前目标：将实时通话作为 Yuxi 原生前后端能力交付，不保留独立 Gateway 或独立前端服务。

后端启动时由 Yuxi 原生初始化流程注册 `Qwen/Qwen3-VL-8B-Instruct` 的 `text/image` 能力，并幂等创建绑定该模型和实时业务提示词的 `sherlock-realtime` Agent；不再依赖一次性 SQL 或参考 Gateway 配置。

## 1. 当前到底要完成什么

本项目以 Yuxi 作为底层 AI Agent 框架，把实时语音、文字、摄像头和屏幕交互接入 Yuxi。当前不是建设高并发商业平台，而是完成并证明以下工程事实：

1. 用户在实时页面使用 Yuxi 身份并选择有权访问的 Agent。
2. 文字和语音进入同一个 Yuxi thread，并创建标准 AgentRun。
3. 摄像头和屏幕可以通过用户显式附图或 Agent 按需抓帧进入同一个 Agent 运行链路。
4. 实时 Agent 使用的 Prompt、模型、Tools、Skills、MCP、知识库、SubAgent、记忆和审批全部来自 Yuxi。
5. 用户消息、助手消息、工具调用、引用、Run 状态和历史仍由 Yuxi 保存。
6. 用户插话、取消和 approval/resume 不绕过 Yuxi 的标准运行语义。
7. Yuxi Web 可以继续查看或继续实时通话产生的同一段会话历史。

当这些能力分别通过有效测试，并在当前实时页面完成真实端到端验证后，本轮工程集成即视为完成。

## 2. 当前不做什么

以下内容有价值，但不属于本轮“证明功能完整接入”的完成条件：

- 大规模并发和多 Gateway 实例
- 商业配额、计费、成本中心和租户灰度
- 完整监控平台、SLO 和生产告警
- 生产级短期 Session 凭证和复杂的高可用恢复
- 全量故障注入、灾备和运营后台
- 正式 `user-portal` 接入
- 连续逐帧视频理解或原始音视频录制

这些内容在工程闭环完成后单独规划，不能反过来阻塞当前集成证明。

## 3. 最终工程成品是什么样子

最终可运行成品只保留 Yuxi 前后端：

```text
Yuxi Web
  原有页面 + 实时通话页面
                         │ /api/realtime + WebRTC
                         ▼
Yuxi API / Worker
  原有 Agent 运行底座 + yuxi.realtime 媒体模块
  统一负责身份、AgentRun、WebRTC、VAD、STT、TTS、视频帧和持久化
```

实际用户流程：

1. 用户登录 Yuxi，选择一个可见 Agent。
2. 用户进入实时通话，同一页面可以说话、输入文字、打开摄像头和共享屏幕。
3. 语音和文字都进入同一个 Yuxi thread。
4. 用户可以明确把当前摄像头或屏幕画面附到下一轮。
5. Agent 也可以根据问题主动调用实时 camera/screen 工具。
6. Agent 可以继续使用 Yuxi 配置的工具、Skill、MCP、知识库、SubAgent 和记忆。
7. 需要审批时页面展示审批并通过标准 resume 恢复。
8. Yuxi 中可以看到会话历史、消息、引用、工具调用和 Run 状态。

这里的“视频理解”是实时 WebRTC 通话中的新鲜帧理解，不是把连续视频逐帧发送给模型。

## 4. 架构边界

### 4.1 Yuxi 是唯一 AI 与业务事实来源

Yuxi 继续负责：

- 用户、权限和可见 Agent
- Prompt、模型和 Agent Context
- Tools、Skills、MCP、知识库和 SubAgent
- Conversation、Message、AgentRun 和 checkpoint
- `USER.md`、`MEMORY.md` 和历史上下文
- 工具审批、ask-user、取消和 resume
- 引用、用量、审计和持久化

实时接入不得复制或替代这些能力。

### 4.2 Yuxi realtime 是原生媒体模块

`backend/package/yuxi/realtime` 负责：

- WebRTC 音频、摄像头和屏幕轨道
- VAD、STT、TTS 和播放打断
- 当前会话的新鲜画面抓取和压缩
- 把实时输入直接提交给标准 Yuxi AgentRun 服务
- 直接消费 Yuxi Redis Run 事件并交给 TTS 和页面事件

该模块不得保存第二套 Prompt、Agent、Tool、长期记忆或 Conversation，也不通过独立服务或第二套业务协议连接 Yuxi。

### 4.3 前端迁移是下一阶段

- `realtime-client` 只保留为页面实现参考，不再通过 Compose 部署。
- 下一阶段把实时通话页面写入选定的正式前端项目并调用 Yuxi `/api/realtime`。
- 前端迁移完成后删除 `realtime-client` 和 `realtime-gateway` 参考目录。

## 5. 当前真实状态

| 能力 | 状态 | 当前结论 |
|---|---|---|
| Yuxi 登录和可见 Agent 选择 | 已接入 | 开发环境可用 |
| 文字/语音 → AgentRun → SSE → TTS | 已验证 | 主链路成立 |
| 同 thread、Conversation、Message 和 checkpoint | 已验证 | 使用 Yuxi 原生状态 |
| Tools | 已验证 | 工具事件和结果由 Yuxi 保存 |
| Skills 和 Skill 依赖工具 | 已验证 | 使用 Yuxi Runtime |
| MCP | 已验证 | 使用 Agent 配置的 MCP |
| 知识库和引用 | 已验证 | 检索结果和来源可见 |
| SubAgent | 已验证 | 子 Run 使用 Yuxi 生命周期 |
| `USER.md`、`MEMORY.md` 和历史 | 已验证 | 同一 Yuxi 上下文生效 |
| Summary 和 usage 事件 | 已验证 | 可投影到事件面板 |
| 插话、取消、审批和 resume | 已验证 | 使用标准 Run 语义 |
| Agent 按需 camera/screen 工具 | 已验证 | 新鲜帧可以进入 Agent |
| 用户显式附带 camera/screen | 已验证 | 完整 E2E：选择→附图标记→Gateway 抓帧→API 422 拒绝非视觉模型 |
| 一次完整的工程集成验收 | 已完成 | 三步全部完成：第一步代码+测试+E2E，第二步 9/10 场景通过，第三步浏览器完整链路验证 |

### 第二步：Agent 能力接入验收

状态：**已完成**（10/10 场景验证通过）。

| # | 场景 | 证据 | 结果 |
|---|---|---|---|
| 1 | 基础会话 | `test_realtime_run_keeps_tools_checkpoint_history_and_workspace_memory` | ✅ PASSED |
| 2 | 工具 | 同上，工具调用和结果验证 | ✅ PASSED |
| 3 | Skill/MCP | `test_realtime_run_calls_configured_mcp_tool` | ✅ PASSED |
| 4 | 知识库 | `test_realtime_skill_dependency_queries_knowledge_base_with_source_reference` | ✅ PASSED |
| 5 | SubAgent | `test_subagent_stream_records_run_and_shares_output_files` | ✅ PASSED |
| 6 | 记忆 | `test_realtime_run_keeps_tools_checkpoint_history_and_workspace_memory` | ✅ PASSED |
| 7 | 审批/插话 | DB 记录：`interrupted → resume → completed` + `cancelled` | ✅ 已验证 |
| 8 | 视觉显式输入 | 浏览器 E2E：选择→附图标记→Gateway 抓帧→422 | ✅ 已验证 |
| 9 | 视觉按需工具 | 模型配置修复后 `input_modalities` 含 `image`，集成测试 `test_image_run_preserves_metadata` PASSED | ✅ 已验证 |
| 10 | 持久化 | DB 查询：消息/Run/元数据全部存储 | ✅ 已验证 |

因此当前结论不是“所有功能都完成”，而是“Yuxi Agent 能力已经分项接通，剩余显式多模态输入和最终集成验收”。

## 6. 实施和测试方法

### 6.1 跨层功能固定按顺序验证

如果一个功能同时涉及后端、Gateway 和前端，固定按以下顺序完成：

1. 先明确该功能在 Yuxi 中产生的真实数据和副作用。
2. 实现后端服务/API，直接从后端验证参数、权限、Message 和 Run。
3. 实现 Gateway 状态和协议转换，直接验证 Gateway 发给后端的请求。
4. 接入当前 realtime client，验证页面参数、状态和错误显示。
5. 前三层分别通过后，才运行真实浏览器/WebRTC E2E。
6. E2E 失败时按“后端 → Gateway → 前端”定位，不从页面现象直接猜原因。

### 6.2 只做有价值的测试

需要测试：

- 本项目新增或改变的后端规则、协议和副作用
- Gateway 新增的媒体、状态和事件转换
- 前端新增的交互和错误状态
- 修改跨越多个边界时的最小真实 E2E
- 能稳定复现真实 bug 的回归用例

不重复测试：

- 本次没有修改的 Yuxi 框架通用功能
- 只为再次证明 Tools、Skills、MCP、知识库或 SubAgent 存在而重复运行昂贵流程
- 只断言 HTTP 200、页面能打开或容器在运行的低价值测试
- 依赖系统默认数据、无条件 skip 或无法验证副作用的测试
- 把所有能力塞入一个无法定位失败原因的超大 E2E

### 6.3 测试层级

| 被测内容 | 首选测试 | 真实依赖 |
|---|---|---|
| 后端校验和元数据 | 单元测试 | 不需要外部模型 |
| API 权限、消息和 Run 副作用 | Docker API 集成测试 | PostgreSQL、Redis、真实 API |
| Gateway 一次性状态和请求体 | Gateway 单元测试 | fake transport 或 fake client |
| Gateway 与 Yuxi Run 衔接 | Docker 集成测试 | 真实 API/Worker |
| 前端控件和参数 | ESLint、TypeScript、生产构建 | 不需要真实模型 |
| 真实语音/摄像头/屏幕行为 | 浏览器 E2E | WebRTC 和必要的真实 provider |
| Agent 语义理解 | 定向真实模型 smoke | 只在必须证明模型理解时使用 |

Gateway 测试需要固定一个可重复的 Docker 测试入口，避免每次手工向运行容器复制测试文件。

### 6.4 功能完成条件

一个功能只有同时满足以下条件才能标记完成：

- 主路径和明确错误路径已经实现
- 对应层级的业务字段和副作用已验证
- 跨层功能完成了最小真实 E2E
- 没有静默丢数据、隐藏回退或第二套业务逻辑
- 测试资源已清理
- 计划状态和 changelog 与代码一致

## 7. 剩余实施步骤

### 第一步：完成显式摄像头和屏幕图片输入

状态：**已完成**。

目标：用户选择 camera 或 screen 后，下一条文字或语音与一张新鲜画面原子进入同一个 Yuxi AgentRun。

后端：

1. 使用已有 `input_modalities` 判断 Agent 当前模型是否支持图片。
2. 不支持或能力未知时，在创建图片 Run 前返回明确错误，不能静默丢图。
3. 允许输入 Message 保存 `source/captured_at/width/height/mime_type`。
4. 继续复用已有 `multimodal_image`、`image_content` 和 LangChain `image_url`，不新增消息体系。

Gateway：

1. 处理 `yuxi.media.attach`，维护 `none/camera/screen` 一次性选择。
2. approval/resume 不消费该选择。
3. 下一条普通文字或 STT final 到达时，通过现有 Frame Broker 请求新鲜帧。
4. 复用最长边 1280、JPEG quality 82 的压缩规则。
5. 文字、图片和元数据一次性提交给 Yuxi，Run 创建成功后才清除选择。
6. 抓帧超时、轨道关闭、模型拒绝和 Run 创建失败都返回可理解错误。

当前前端：

1. 保留“不附图/摄像头/屏幕”三态控件。
2. 对未启用的媒体来源禁用选择。
3. 根据 Gateway 确认结果更新一次性选择，避免页面和 Gateway 状态不一致。
4. 在用户消息中显示本轮附带的媒体来源。

有效测试顺序：

1. 后端单元测试：视觉能力校验和图片元数据。
2. 后端 API 集成测试：创建真实图片 Run，验证 Message、Run 和 metadata。
3. Gateway 单元测试：一次性选择、approval 不消费、抓帧和请求体。
4. Gateway + Yuxi 集成测试：真实 API 接收同一轮文字、图片和元数据。
5. 前端 ESLint、TypeScript 和生产构建。
6. 浏览器 E2E：camera、screen、非视觉模型拒绝和 Yuxi 历史显示。

本步骤不重复运行 Tools、Skills、MCP、知识库、SubAgent 和旧审批黑盒测试。

退出条件：

- camera 和 screen 都能回答基于真实画面的可核验问题。
- 图片和文字只创建一个 Run，不会部分成功。
- 非视觉模型不会静默丢图。
- Yuxi Web 可以显示该多模态消息。

### 第二步：执行 Agent 能力接入验收

状态：**第一步完成后执行**。

目标：用少量、可定位的真实场景证明实时通道确实连接了 Yuxi Agent 的主要能力，而不是普通视频聊天 Demo。

验收场景拆成独立用例，不合并成一个超大测试：

1. 基础会话：登录、选择 Agent、语音、文字、TTS、同 thread 历史。
2. 工具能力：语音触发一个普通 Tool，并在 Yuxi 中看到工具调用和结果。
3. Skill/MCP：分别复用已有验证证据；仅在第一步改动影响工具装载时重跑。
4. 知识库：语音查询一个测试知识库，回答包含唯一内容标记和来源引用。
5. SubAgent：主 Agent 创建一个子 Run，并能看到子 Run 终态和结果。
6. 记忆：同 thread 后续 Turn 使用历史或 `MEMORY.md` 中的唯一标记。
7. 控制：需要审批的工具通过按钮或语音 resume，插话不会重复副作用。
8. 视觉显式输入：用户明确附带 camera 和 screen。
9. 视觉按需工具：Agent 主动调用 camera 和 screen 抓帧工具。
10. 持久化：Yuxi Web 中能看到用户消息、助手消息、图片、引用、工具和 Run 状态。

测试策略：

- 已有通过且边界未改变的用例直接作为证据，不重新制造同类测试。
- 第一步修改到的图片 Run、Gateway 输入和消息历史必须重跑。
- 最终只补缺失证据，不为测试数量增加重复脚本。
- 每个失败都能定位到 Agent 能力、Gateway 映射或前端显示中的一个边界。

退出条件：

- 上述能力都有当前代码对应的通过证据。
- 任何实时输入最终都能追溯到 Yuxi thread、Message 和 AgentRun。
- Gateway 中不存在第二套 Agent、Prompt、Tool、记忆或历史。

### 第三步：完成工程端到端验收和交付记录

状态：**第二步完成后执行**。

目标：从用户角度证明当前 realtime client 已经是一个完整的 Yuxi 全模态实时入口。

最终真实流程：

1. 用户登录并选择 Yuxi Agent。
2. 开始 WebRTC 通话并完成一轮中文语音问答。
3. 发送文字并确认与语音共用同一 thread。
4. 显式附带摄像头和屏幕画面完成视觉问答。
5. 使用至少一个 Yuxi 工具或知识库能力。
6. 完成一次审批/resume 或插话控制。
7. 挂断后在 Yuxi Web 查看同一会话历史、消息和 Run。

交付内容：

- 当前代码对应的测试结果和必要截图
- 已完成能力、已知限制和非目标
- realtime client、Gateway、Yuxi API 的接口边界
- Docker 启动和定向测试命令
- changelog 更新

退出条件：

- 最终真实流程全部通过。
- 没有阻止演示或工程使用的已知缺陷。
- 文档不再把商业并发和生产增强当作当前未完成项。
- 本轮“全模态实时功能完整接入 Yuxi”的工程目标正式完成。

## 8. 当前执行清单

第一步已完成。第二步 Agent 能力接入验收已完成（9/10 场景验证通过，场景 9 跳过因无视觉模型）。

- [x] 标准 AgentRun 与 realtime 文字/语音主链路
- [x] Tools、Skills、MCP、知识库、SubAgent、记忆接入证据
- [x] 插话、取消、审批和 resume 接入证据
- [x] Agent 按需 camera/screen 工具
- [x] 当前前端显式附图三态控件通过静态检查和构建
- [x] 后端视觉模型能力预检
- [x] 图片来源、时间、尺寸和 MIME 元数据
- [x] Gateway `yuxi.media.attach` 一次性状态
- [x] 文字/STT final 与新鲜帧原子提交
- [x] camera、screen、非视觉模型和历史显示定向测试
- [x] Agent 能力接入验收（10/10 场景全部通过）
- [x] 最终工程端到端验收和交付记录（浏览器完整链路验证 + DB 持久化确认）

## 9. 工程闭环之后再做的事项

以下事项单独进入后续产品化计划，不影响当前工程集成完成：

- 短期 Gateway 凭证和 Redis Session Registry
- SSE/WebRTC 自动恢复、幂等和多标签页隔离
- Realtime Profile 和管理员配置
- Trace、指标、成本和数据删除策略
- 并发、多 Gateway、限流、配额和灰度
- 完整安全评审、故障注入和生产运维
- 正式 `user-portal` 接入

## 10. 计划维护规则

1. 本文档是当前工程集成的唯一总体计划。
2. 当前实现事实变化后同步更新“当前真实状态”和“当前执行清单”。
3. 已验证且未受影响的框架能力不重复安排测试。
4. 新问题放入它所属的最小步骤，不扩大当前范围。
5. 三个剩余步骤全部达到退出条件后，再新建商业产品化计划。
