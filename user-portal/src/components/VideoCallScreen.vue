<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import AppIcon from './AppIcon.vue'

// 主题色切换（驱动全局 --accent 系列变量）
const themes = [
  { key: 'violet', color: '#7c3aed' },
  { key: 'blue', color: '#3b82f6' },
  { key: 'green', color: '#10b981' },
  { key: 'amber', color: '#f59e0b' },
  { key: 'rose', color: '#f43f5e' }
]
const activeTheme = ref('violet')
function setTheme(key) {
  activeTheme.value = key
  document.documentElement.setAttribute('data-theme', key)
}

// 通话计时（从设计稿的 02:34 起递增）
const seconds = ref(154)
let timer = null
function fmt(s) {
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}
onMounted(() => {
  timer = setInterval(() => (seconds.value += 1), 1000)
})
onUnmounted(() => clearInterval(timer))

// 控制栏按钮激活态
const ctrl = ref({
  mic: true,
  cam: true,
  share: false,
  caption: true,
  emoji: false,
  more: false
})
</script>

<template>
  <div class="stage-video">
    <!-- 背景：近黑线性渐变 + 紫罗兰径向光晕 -->
    <div class="bg"></div>

    <!-- 顶部悬浮玻璃栏 -->
    <header class="top-bar">
      <div class="tb-left">
        <button class="icon-btn sq"><AppIcon name="arrow-left" :size="18" /></button>
        <div class="title-block">
          <div class="title">产品评审视频会</div>
          <div class="subtitle">灵犀 AI · 实时视频通话</div>
        </div>
        <div class="timer-pill">
          <span class="dot"></span>
          <span class="timer">{{ fmt(seconds) }}</span>
        </div>
      </div>
      <div class="tb-right">
        <div class="signal-pill">
          <AppIcon name="signal" :size="15" />
          <span>信号良好</span>
        </div>
        <button class="icon-btn sq"><AppIcon name="settings" :size="18" /></button>
        <button class="icon-btn sq"><AppIcon name="more" :size="18" /></button>
      </div>
    </header>

    <!-- 左上：通话信息卡 -->
    <section class="stats-card">
      <div class="sc-head">
        <span class="sc-dot"></span>
        <span class="sc-title">通话信息</span>
      </div>
      <div class="sc-row"><span class="sc-label">时长</span><span class="sc-val">{{ fmt(seconds) }}</span></div>
      <div class="sc-row"><span class="sc-label">分辨率</span><span class="sc-val">1080p · 30fps</span></div>
      <div class="sc-row">
        <span class="sc-label">网络</span>
        <span class="sc-net"><AppIcon name="signal" :size="16" /><span>良好</span></span>
      </div>
    </section>

    <!-- 右上：自视图 PiP -->
    <section class="self-pip">
      <div class="pip-avatar">你</div>
      <div class="pip-label">你 · 摄像头开启</div>
    </section>

    <!-- 右上：PiP 工具栏 -->
    <section class="pip-toolbar">
      <button class="pip-item">
        <span class="pip-ico"><AppIcon name="zoom-in" :size="18" /></span>
        <span class="pip-txt">放大</span>
      </button>
      <button class="pip-item">
        <span class="pip-ico"><AppIcon name="zoom-out" :size="18" /></span>
        <span class="pip-txt">缩小</span>
      </button>
      <button class="pip-item">
        <span class="pip-ico"><AppIcon name="flip" :size="18" /></span>
        <span class="pip-txt">翻转</span>
      </button>
    </section>

    <!-- 中央头像区 -->
    <div class="avatar-ring"></div>
    <div class="avatar-core">
      <AppIcon name="sparkle" :size="32" class="avatar-star" />
    </div>
    <div class="name-pill">灵犀 AI 助手</div>
    <div class="status-text">正在讲话 · 实时转写开启</div>
    <div class="sound-wave">
      <span v-for="n in 20" :key="n" class="bar" :style="{ animationDelay: (n * 0.07) + 's' }"></span>
    </div>

    <!-- 右侧：折叠栏 -->
    <aside class="collapse-rail">
      <button class="rail-btn has-badge">
        <AppIcon name="chat" :size="19" />
        <span class="badge">3</span>
      </button>
      <button class="rail-btn"><AppIcon name="info" :size="19" /></button>
      <button class="rail-btn"><AppIcon name="users" :size="19" /></button>
    </aside>

    <!-- 底部控制栏 -->
    <footer class="control-bar">
      <button class="ctrl-btn" :class="{ off: !ctrl.mic }" @click="ctrl.mic = !ctrl.mic">
        <AppIcon name="mic" :size="20" />
      </button>
      <button class="ctrl-btn" :class="{ off: !ctrl.cam }" @click="ctrl.cam = !ctrl.cam">
        <AppIcon name="video" :size="20" />
      </button>
      <button class="ctrl-btn" :class="{ on: ctrl.share }" @click="ctrl.share = !ctrl.share">
        <AppIcon name="screen-share" :size="20" />
      </button>
      <button class="ctrl-btn accent" :class="{ on: ctrl.caption }" @click="ctrl.caption = !ctrl.caption">
        <AppIcon name="captions" :size="20" />
      </button>
      <button class="ctrl-btn" :class="{ on: ctrl.emoji }" @click="ctrl.emoji = !ctrl.emoji">
        <AppIcon name="smile" :size="20" />
      </button>
      <button class="ctrl-btn" @click="ctrl.more = !ctrl.more">
        <AppIcon name="more" :size="20" />
      </button>
      <button class="ctrl-hangup"><AppIcon name="phone-off" :size="24" /></button>
    </footer>

    <!-- 左下：主题色切换器 -->
    <section class="theme-switcher">
      <span class="ts-icon"><AppIcon name="palette" :size="18" /></span>
      <button
        v-for="t in themes"
        :key="t.key"
        class="ts-dot"
        :class="{ active: activeTheme === t.key }"
        :style="{ background: t.color }"
        @click="setTheme(t.key)"
        :title="t.key"
      ></button>
    </section>
  </div>
</template>

<style scoped>
.stage-video {
  position: relative;
  width: 1440px;
  height: 900px;
  overflow: hidden;
  background: var(--bg-base);
  font-family: var(--font-sans);
}
.bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 50% 42%, rgba(124, 58, 237, 0.1), rgba(124, 58, 237, 0) 60%),
    linear-gradient(180deg, #06060b 0%, #040405 50%, #020203 100%);
}

/* 顶部栏 */
.top-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 1440px;
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(11, 11, 14, 0.55);
  border-bottom: 1px solid var(--border-soft);
  backdrop-filter: blur(20px);
  box-shadow: var(--shadow-bar);
}
.tb-left { display: flex; align-items: center; gap: 14px; }
.title-block { display: flex; flex-direction: column; gap: 2px; }
.title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.subtitle { font-size: 12px; color: var(--text-secondary); }
.timer-pill {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 11px; border-radius: var(--r-pill);
  background: rgba(52, 211, 153, 0.14);
}
.timer-pill .dot { width: 7px; height: 7px; border-radius: 3.5px; background: #34d399; }
.timer { font-size: 13px; font-weight: 500; color: var(--green-soft); }
.tb-right { display: flex; align-items: center; gap: 10px; }
.signal-pill {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 11px; border-radius: var(--r-pill);
  background: rgba(20, 20, 24, 0.7);
  border: 1px solid var(--border-soft);
  color: #d4d4d8; font-size: 12px;
}
.icon-btn.sq {
  width: 38px; height: 38px; border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  background: rgba(20, 20, 24, 0.7);
  border: 1px solid var(--border-soft);
  color: var(--text-primary);
}

/* 通话信息卡 */
.stats-card {
  position: absolute; left: 24px; top: 84px;
  width: 206px; height: 130px;
  padding: 14px;
  border-radius: var(--r-md);
  background: rgba(11, 11, 14, 0.55);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-card);
  display: flex; flex-direction: column; gap: 11px;
}
.sc-head { display: flex; align-items: center; gap: 7px; }
.sc-dot { width: 6px; height: 6px; border-radius: 3px; background: var(--accent-light); }
.sc-title { font-size: 12px; font-weight: 600; color: #d4d4d8; }
.sc-row { display: flex; align-items: center; justify-content: space-between; font-size: 12px; }
.sc-label { color: var(--text-tertiary); }
.sc-val { color: var(--text-primary); font-weight: 500; }
.sc-net { display: flex; align-items: center; gap: 6px; color: var(--green-soft); }

/* 自视图 PiP */
.self-pip {
  position: absolute; left: 1216px; top: 84px;
  width: 200px; height: 134px;
  border-radius: var(--r-md);
  background: linear-gradient(180deg, rgba(31, 27, 51, 0.92), rgba(15, 15, 23, 0.92));
  border: 1px solid var(--accent-ring);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  padding: 14px;
}
.pip-avatar {
  width: 46px; height: 46px; border-radius: 23px;
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 16px; font-weight: 700;
}
.pip-label { font-size: 12px; color: #d4d4d8; }

/* PiP 工具栏 */
.pip-toolbar {
  position: absolute; left: 1216px; top: 230px;
  width: 200px; height: 76px;
  border-radius: var(--r-lg);
  background: rgba(11, 11, 14, 0.7);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-card);
  display: flex; align-items: center; justify-content: center; gap: 18px;
  padding: 14px;
}
.pip-item { display: flex; flex-direction: column; align-items: center; gap: 5px; }
.pip-ico {
  width: 36px; height: 36px; border-radius: var(--r-md);
  background: rgba(24, 24, 28, 0.9);
  display: flex; align-items: center; justify-content: center;
  color: #d4d4d8;
}
.pip-txt { font-size: 11px; color: var(--text-secondary); }

/* 中央头像 */
.avatar-ring {
  position: absolute; left: 600px; top: 296px;
  width: 240px; height: 240px; border-radius: 50%;
  background: var(--accent-soft-2);
  border: 1px solid var(--accent-ring);
}
.avatar-core {
  position: absolute; left: 624px; top: 320px;
  width: 192px; height: 192px; border-radius: 50%;
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center;
}
.avatar-star { color: #fff; }
.name-pill {
  position: absolute; left: 635px; top: 544px;
  width: 170px; height: 32px;
  border-radius: var(--r-md);
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary); font-size: 13px; font-weight: 500;
}
.status-text {
  position: absolute; left: 520px; top: 592px;
  width: 320px; height: 19px;
  text-align: center; font-size: 13px; color: var(--accent-text);
}
.sound-wave {
  position: absolute; left: 608px; top: 624px;
  width: 224px; height: 48px;
  display: flex; align-items: center; gap: 4px;
}
.sound-wave .bar {
  width: 6px; border-radius: 3px;
  background: var(--accent-text);
  animation: sound 1.1s ease-in-out infinite;
  transform-origin: center;
}
.sound-wave .bar:nth-child(odd) { background: var(--accent-light); }
@keyframes sound {
  0%, 100% { height: 12px; }
  50% { height: 42px; }
}

/* 折叠栏 */
.collapse-rail {
  position: absolute; left: 1364px; top: 345px;
  width: 56px; height: 212px;
  border-radius: var(--r-3xl);
  background: rgba(11, 11, 14, 0.6);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-card);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
  padding: 10px;
}
.rail-btn {
  position: relative;
  width: 40px; height: 40px; border-radius: 20px;
  background: rgba(24, 24, 28, 0.9);
  display: flex; align-items: center; justify-content: center;
  color: #d4d4d8;
}
.rail-btn.has-badge { background: var(--accent-soft); color: var(--accent-text); }
.badge {
  position: absolute; top: -3px; right: -3px;
  min-width: 18px; height: 18px; padding: 0 4px;
  border-radius: 9px; background: var(--red);
  color: #fff; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

/* 控制栏 */
.control-bar {
  position: absolute; left: 410px; top: 800px;
  width: 620px; height: 72px;
  border-radius: var(--r-2xl);
  background: rgba(11, 11, 14, 0.72);
  border: 1px solid var(--border-strong);
  box-shadow: var(--shadow-pop);
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 14px;
}
.ctrl-btn {
  width: 44px; height: 44px; border-radius: 22px;
  background: #2a2a30;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
  transition: background 0.15s, transform 0.1s;
}
.ctrl-btn:hover { transform: translateY(-1px); }
.ctrl-btn.on { background: var(--accent); }
.ctrl-btn.accent { background: var(--accent); }
.ctrl-btn.off { background: #3a2330; color: #f9a8b4; }
.ctrl-hangup {
  width: 56px; height: 56px; border-radius: var(--r-lg);
  background: var(--red);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
}

/* 主题色切换器 */
.theme-switcher {
  position: absolute; left: 24px; top: 796px;
  width: 206px; height: 48px;
  border-radius: var(--r-xl);
  background: rgba(11, 11, 14, 0.7);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-card);
  display: flex; align-items: center; gap: 10px;
  padding: 8px;
}
.ts-icon { color: var(--text-secondary); display: flex; }
.ts-dot {
  width: 22px; height: 22px; border-radius: 11px;
  border: 2px solid transparent;
  transition: transform 0.12s;
}
.ts-dot.active { border-color: #fff; transform: scale(1.05); }
</style>
