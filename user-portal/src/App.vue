<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ChatScreen from './components/ChatScreen.vue'
import WorkbenchScreen from './components/WorkbenchScreen.vue'
import VideoCallScreen from './components/VideoCallScreen.vue'

// 设计稿基准尺寸（跟随画布 1440×900）
const BASE_W = 1440
const BASE_H = 900
// 顶部切换栏高度（应用外壳，不随缩放变化）
const BAR_H = 52

const screens = [
  { key: 'chat', label: '文字对话', comp: ChatScreen },
  { key: 'workbench', label: '全模态工作台', comp: WorkbenchScreen },
  { key: 'video', label: '视频通话', comp: VideoCallScreen }
]

const active = ref('video')
const activeComp = computed(() => screens.find((s) => s.key === active.value).comp)

// 等比缩放：取窗口可用区域与设计稿尺寸之比的最小值，整体 scale 适配
const scale = ref(1)
function fit() {
  const availW = window.innerWidth
  const availH = window.innerHeight - BAR_H
  scale.value = Math.min(availW / BASE_W, availH / BASE_H)
}
onMounted(() => {
  fit()
  window.addEventListener('resize', fit)
})
onUnmounted(() => window.removeEventListener('resize', fit))
</script>

<template>
  <div class="app-shell">
    <!-- 顶部屏幕切换栏（应用外壳，固定不缩放） -->
    <nav class="screen-bar">
      <span class="sb-brand">灵犀 AI · 设计还原</span>
      <div class="sb-tabs">
        <button
          v-for="s in screens"
          :key="s.key"
          class="sb-tab"
          :class="{ active: active === s.key }"
          @click="active = s.key"
        >
          {{ s.label }}
        </button>
      </div>
      <span class="sb-scale">缩放 {{ Math.round(scale * 100) }}%</span>
    </nav>

    <!-- 等比缩放舞台 -->
    <div class="stage-wrap">
      <div
        class="stage"
        :style="{
          width: BASE_W + 'px',
          height: BASE_H + 'px',
          transform: `translate(-50%, -50%) scale(${scale})`
        }"
      >
        <component :is="activeComp" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-app);
  overflow: hidden;
}

.screen-bar {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-soft);
  z-index: 10;
}
.sb-brand {
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 500;
}
.sb-tabs {
  display: flex;
  gap: 6px;
}
.sb-tab {
  padding: 7px 14px;
  border-radius: var(--r-pill);
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
  transition: background 0.15s, color 0.15s;
}
.sb-tab:hover {
  background: var(--surface-1);
  color: var(--text-primary);
}
.sb-tab.active {
  background: var(--accent);
  color: #fff;
  font-weight: 500;
}
.sb-scale {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 84px;
  text-align: right;
}

.stage-wrap {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.stage {
  position: absolute;
  top: 50%;
  left: 50%;
  transform-origin: center center;
}
</style>
