<template>
  <div class="realtime-agent-view">
    <header class="realtime-header">
      <div>
        <h1>实时通话</h1>
        <p>{{ agentName }} · Yuxi 原生实时 Agent</p>
      </div>
      <a-button @click="router.back">返回对话</a-button>
    </header>

    <main class="realtime-layout">
      <section class="media-panel">
        <div class="media-stage">
          <video ref="localVideo" autoplay muted playsinline />
          <div v-if="!connected" class="media-empty">点击“开始通话”接入实时 Agent</div>
        </div>
        <div class="media-controls">
          <a-button type="primary" :loading="connecting" @click="toggleCall">
            {{ connected ? '结束通话' : '开始通话' }}
          </a-button>
          <a-button :disabled="!connected" @click="toggleCamera">{{ cameraOn ? '关闭摄像头' : '打开摄像头' }}</a-button>
          <a-button :disabled="!connected" @click="toggleScreen">{{ screenOn ? '停止共享' : '共享屏幕' }}</a-button>
        </div>
      </section>

      <section class="chat-panel">
        <div class="chat-messages">
          <a-empty v-if="messages.length === 0" description="暂无实时消息" />
          <div v-for="item in messages" :key="item.id" class="message" :class="`message-${item.role}`">
            {{ item.text }}
          </div>
        </div>
        <a-form class="composer" @submit.prevent="sendText">
          <a-input v-model:value="draft" :disabled="!connected" placeholder="输入实时消息" />
          <a-button html-type="submit" type="primary" :disabled="!connected || !draft.trim()">发送</a-button>
        </a-form>
        <a-alert v-if="error" type="error" :message="error" show-icon />
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

const route = useRoute()
const router = useRouter()
const localVideo = ref(null)
const draft = ref('')
const messages = ref([])
const connected = ref(false)
const connecting = ref(false)
const cameraOn = ref(false)
const screenOn = ref(false)
const error = ref('')
let peer = null
let dataChannel = null
let sessionId = ''
let pcId = ''

const agentSlug = computed(() => String(route.query.agent_id || route.query.agent_slug || ''))
const threadId = computed(() => String(route.query.thread_id || ''))
const agentName = computed(() => String(route.query.agent_name || agentSlug.value || '当前 Agent'))

const addMessage = (role, text) => messages.value.push({ id: `${Date.now()}-${Math.random()}`, role, text })

async function toggleCall() {
  if (connected.value) return disconnect()
  connecting.value = true
  error.value = ''
  try {
    const start = await fetch('/api/realtime/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_slug: agentSlug.value, thread_id: threadId.value || null, enableDefaultIceServers: true })
    })
    if (!start.ok) throw new Error('实时会话创建失败')
    const config = await start.json()
    sessionId = config.sessionId
    peer = new RTCPeerConnection({ iceServers: config.iceConfig?.iceServers || [] })
    peer.onicecandidate = event => {
      if (!event.candidate || !sessionId || !peer) return
      fetch(`/api/realtime/sessions/${sessionId}/offer`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pc_id: pcId,
          candidates: [{
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex
          }]
        })
      }).catch(() => {})
    }
    peer.onconnectionstatechange = () => {
      if (['failed', 'disconnected', 'closed'].includes(peer?.connectionState)) disconnect()
    }
    dataChannel = peer.createDataChannel('rtvi')
    dataChannel.onmessage = event => handleServerMessage(event.data)
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true })
    stream.getTracks().forEach(track => peer.addTrack(track, stream))
    if (localVideo.value) localVideo.value.srcObject = stream
    const offer = await peer.createOffer()
    await peer.setLocalDescription(offer)
    const response = await fetch(`/api/realtime/sessions/${sessionId}/offer`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sdp: offer.sdp, type: offer.type })
    })
    if (!response.ok) throw new Error('WebRTC 协商失败')
    const answer = await response.json()
    pcId = answer.pc_id || answer.pcId || ''
    await peer.setRemoteDescription(answer)
    connected.value = true
    message.success('实时 Agent 已接通')
  } catch (reason) {
    error.value = reason?.message || '实时连接失败'
    disconnect()
  } finally {
    connecting.value = false
  }
}

function sendText() {
  const text = draft.value.trim()
  if (!text || !dataChannel) return
  addMessage('user', text)
  dataChannel.send(JSON.stringify({ type: 'client-message', data: { t: 'send-text', d: { content: text, options: { run_immediately: true, audio_response: true } } } }))
  draft.value = ''
}

function handleServerMessage(raw) {
  try {
    const event = typeof raw === 'string' ? JSON.parse(raw) : raw
    const text = event?.data?.text || event?.data?.payload?.detail?.text
    if (text) addMessage('assistant', text)
  } catch { /* ignore non-JSON transport frames */ }
}

async function toggleCamera() {
  cameraOn.value = !cameraOn.value
  const track = localVideo.value?.srcObject?.getVideoTracks?.()[0]
  if (track) track.enabled = cameraOn.value
}

async function toggleScreen() {
  if (!peer) return
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
    const sender = peer.getSenders().find(item => item.track?.kind === 'video')
    if (sender && stream.getVideoTracks()[0]) sender.replaceTrack(stream.getVideoTracks()[0])
    screenOn.value = true
  } catch (reason) {
    error.value = reason?.message || '屏幕共享失败'
  }
}

function disconnect() {
  peer?.getSenders().forEach(sender => sender.track?.stop())
  peer?.close()
  peer = null
  dataChannel = null
  connected.value = false
  cameraOn.value = false
  screenOn.value = false
}

onBeforeUnmount(disconnect)
</script>

<style scoped>
.realtime-agent-view { display: flex; height: 100%; flex-direction: column; padding: 24px; background: var(--main-10); }
.realtime-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.realtime-header h1 { margin: 0; color: var(--gray-1000); font-size: 22px; }
.realtime-header p { margin: 6px 0 0; color: var(--gray-600); }
.realtime-layout { display: grid; min-height: 0; flex: 1; grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr); gap: 18px; }
.media-panel, .chat-panel { display: flex; min-height: 0; flex-direction: column; border: 1px solid var(--gray-200); border-radius: 12px; background: var(--main-0); box-shadow: 0 8px 30px rgba(0,0,0,.06); }
.media-stage { display: flex; min-height: 0; flex: 1; align-items: center; justify-content: center; overflow: hidden; border-radius: 12px 12px 0 0; background: #101820; }
.media-stage video { width: 100%; height: 100%; object-fit: cover; }
.media-empty { color: #d8e5ea; font-size: 16px; }
.media-controls, .composer { display: flex; flex-wrap: wrap; gap: 8px; padding: 14px; }
.chat-messages { min-height: 0; flex: 1; overflow: auto; padding: 18px; }
.message { max-width: 88%; margin-bottom: 10px; padding: 10px 12px; border-radius: 10px; white-space: pre-wrap; }
.message-user { margin-left: auto; color: #fff; background: var(--main-700); }
.message-assistant { color: var(--gray-1000); background: var(--gray-100); }
.composer { border-top: 1px solid var(--gray-200); }
</style>
