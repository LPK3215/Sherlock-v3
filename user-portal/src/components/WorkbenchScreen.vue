<script setup>
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'

const calls = [
  { title: '产品评审视频会', meta: '通话中 02:34', active: true, live: true },
  { title: '语音答疑 · 论文思路', meta: '昨天' },
  { title: '外骨骼控制方案探讨', meta: '昨天' },
  { title: 'Python 快速排序实现', meta: '3天前' },
  { title: '旅行行程语音规划', meta: '上周' },
  { title: 'React 组件封装请教', meta: '上周' }
]

const modes = ['语音', '视频', '会议']
const mode = ref('会议')

const captions = [
  { who: '灵犀 AI', text: '我先梳理一下这次产品评审的三个重点方向。' },
  { who: '刘培宽', text: '帮我对比方案 A 和 B 的可行性。' },
  { who: '灵犀 AI', text: '方案 A 落地快但扩展性弱，方案 B 更适合长期演进。' },
  { who: '刘培宽', text: '那就按方案 B 推进，下周出第一版原型。' },
  { who: '灵犀 AI', text: '已记录待办，并标注硬件接口标准待确认。' }
]

const ctrl = ref({ mic: true, cam: true, share: false, caption: true, emoji: false, more: false })
</script>

<template>
  <div class="workbench">
    <!-- 左侧栏 -->
    <aside class="wb-sidebar">
      <div class="brand">
        <span class="logo"><AppIcon name="sparkle" :size="15" /></span>
        <span class="brand-name">灵犀 AI</span>
      </div>

      <button class="new-call">
        <AppIcon name="plus" :size="18" />
        <span>新建通话</span>
      </button>

      <div class="search">
        <AppIcon name="search" :size="16" />
        <span>搜索对话与联系人</span>
      </div>

      <div class="recent-label">最近</div>

      <div class="conv-list">
        <button
          v-for="c in calls"
          :key="c.title"
          class="call-item"
          :class="{ active: c.active }"
        >
          <span class="call-dot" v-if="c.live"></span>
          <span class="call-dot idle" v-else></span>
          <span class="call-main">
            <span class="call-title">{{ c.title }}</span>
            <span class="call-meta">{{ c.meta }}</span>
          </span>
        </button>
      </div>

      <div class="divider"></div>

      <div class="user-card">
        <span class="user-avatar">刘</span>
        <span class="user-name">刘培宽</span>
        <span class="user-status">在线</span>
        <AppIcon name="chevron-down" :size="14" class="user-caret" />
      </div>
    </aside>

    <!-- 中央舞台 -->
    <main class="wb-stage">
      <header class="stage-top">
        <div class="st-left">
          <span class="st-title">产品评审视频会</span>
          <span class="st-badge">● 实时通话</span>
        </div>
        <div class="st-right">
          <button class="st-btn"><AppIcon name="settings" :size="18" /></button>
          <button class="st-btn"><AppIcon name="more" :size="18" /></button>
        </div>
      </header>

      <div class="mode-switch">
        <button
          v-for="m in modes"
          :key="m"
          class="mode-pill"
          :class="{ active: mode === m }"
          @click="mode = m"
        >
          {{ m }}
        </button>
      </div>

      <div class="stage-center">
        <div class="stage-card">
          <span class="card-tag">主讲人 · 灵犀 AI</span>
          <span class="card-tag">录制中</span>
          <div class="stage-avatar"><AppIcon name="sparkle" :size="56" /></div>
          <div class="stage-name">灵犀 AI 助手</div>
          <div class="stage-status">正在聆听并实时转写…</div>
          <div class="stage-wave">
            <span v-for="n in 16" :key="n" class="wbar" :style="{ animationDelay: (n * 0.08) + 's' }"></span>
          </div>
          <div class="stage-info">
            <div class="info-row"><span>通话时长</span><b>02:34</b></div>
            <div class="info-row"><span>参会人数</span><b>2 人</b></div>
          </div>
        </div>
      </div>

      <footer class="stage-controls">
        <div class="ctrl-pill">
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
        </div>
      </footer>
    </main>

    <!-- 右侧字幕面板 -->
    <aside class="wb-panel">
      <div class="panel-head">
        <div class="panel-title">实时字幕</div>
        <div class="panel-sub">通话进行中 · 自动转写</div>
      </div>

      <div class="caption-list">
        <div v-for="(c, i) in captions" :key="i" class="caption-item">
          <span class="cap-speaker" :class="c.who === '灵犀 AI' ? 'ai' : 'me'">{{ c.who }}</span>
          <p class="cap-text">{{ c.text }}</p>
        </div>
      </div>

      <div class="divider"></div>

      <div class="summary-card">
        <div class="summary-title">对话摘要</div>
        <div class="summary-list">
          <div class="summary-row"><span class="s-dot"></span>采用方案 B 作为主线</div>
          <div class="summary-row"><span class="s-dot"></span>下周产出第一版原型</div>
          <div class="summary-row"><span class="s-dot"></span>待确认：硬件接口标准</div>
        </div>
        <div class="summary-actions">
          <button class="sa-btn">生成纪要</button>
          <button class="sa-btn">翻译</button>
          <button class="sa-btn">收藏</button>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.workbench {
  width: 1440px;
  height: 900px;
  display: flex;
  font-family: var(--font-sans);
  background: var(--bg-base);
}

/* 左侧栏 */
.wb-sidebar {
  width: 280px; height: 900px; flex-shrink: 0;
  background: var(--bg-sidebar);
  display: flex; flex-direction: column; gap: 12px; padding: 16px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 4px; }
.logo {
  width: 28px; height: 28px; border-radius: var(--r-xs);
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.brand-name { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.new-call {
  width: 100%; padding: 11px; border-radius: var(--r-sm);
  background: var(--accent-grad); color: #fff; font-size: 14px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.search {
  display: flex; align-items: center; gap: 8px; padding: 9px;
  border-radius: var(--r-xs); background: var(--surface-1);
  border: 1px solid var(--border-gray); color: var(--text-tertiary); font-size: 13px;
}
.recent-label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); padding: 0 4px; }
.conv-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.call-item {
  width: 100%; height: 39px; padding: 10px; border-radius: var(--r-xs);
  display: flex; align-items: center; gap: 10px; text-align: left;
}
.call-item:hover { background: rgba(255, 255, 255, 0.03); }
.call-item.active { background: var(--accent-soft); }
.call-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-light); flex-shrink: 0; }
.call-dot.idle { background: var(--text-tertiary); }
.call-main { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.call-title { font-size: 13px; color: #d4d4d8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.call-item.active .call-title { color: var(--accent-text); font-weight: 500; }
.call-meta { font-size: 11px; color: var(--text-tertiary); }
.call-item.active .call-meta { color: var(--accent-light); }
.divider { height: 1px; background: var(--border-gray); }
.user-card {
  display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: var(--r-sm);
  background: var(--surface-1);
}
.user-avatar {
  width: 32px; height: 32px; border-radius: 16px; background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center; color: #fff; font-size: 14px; font-weight: 700;
}
.user-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.user-status { font-size: 11px; color: var(--text-tertiary); }
.user-caret { color: var(--text-tertiary); margin-left: auto; }

/* 中央舞台 */
.wb-stage {
  width: 840px; height: 900px; flex-shrink: 0;
  display: flex; flex-direction: column;
  background:
    radial-gradient(circle at 50% 0%, rgba(124, 58, 237, 0.14), rgba(124, 58, 237, 0) 55%),
    var(--bg-base);
}
.stage-top { height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; }
.st-left { display: flex; align-items: center; gap: 10px; }
.st-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.st-badge { font-size: 12px; color: var(--accent-text); background: var(--accent-soft); padding: 5px 8px; border-radius: var(--r-pill); }
.st-right { display: flex; align-items: center; gap: 8px; }
.st-btn {
  width: 36px; height: 36px; border-radius: var(--r-xs); background: var(--surface-1);
  display: flex; align-items: center; justify-content: center; color: var(--text-secondary);
}

.mode-switch {
  height: 55px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 0;
}
.mode-pill {
  min-width: 79px;
  height: 35px;
  padding: 8px 16px;
  border-radius: var(--r-pill);
  background: var(--surface-1);
  border: 1px solid var(--border-gray);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--text-secondary);
}
.mode-pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.stage-center { flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; }
.stage-card {
  width: 760px; height: 520px; border-radius: var(--r-md);
  background:
    radial-gradient(circle at 50% 45%, rgba(124, 58, 237, 0.22), rgba(124, 58, 237, 0) 70%),
    #16111e;
  border: 1px solid var(--accent-ring);
  position: relative;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;
}
.card-tag {
  position: absolute; top: 16px;
  padding: 8px; border-radius: var(--r-pill);
  background: rgba(0, 0, 0, 0.4); color: var(--text-primary); font-size: 12px;
}
.card-tag:nth-of-type(1) { left: 16px; }
.card-tag:nth-of-type(2) { right: 16px; }
.stage-avatar {
  width: 144px; height: 144px; border-radius: 72px; background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.stage-name {
  padding: 8px 16px; border-radius: var(--r-md); background: rgba(0, 0, 0, 0.5);
  color: var(--text-primary); font-size: 14px;
}
.stage-status { color: var(--accent-text); font-size: 13px; }
.stage-wave { display: flex; align-items: center; gap: 4px; height: 44px; }
.wbar { width: 6px; border-radius: 3px; background: var(--accent-text); animation: swave 1.2s ease-in-out infinite; transform-origin: center; }
.wbar:nth-child(odd) { background: var(--accent-light); }
@keyframes swave { 0%, 100% { height: 10px; } 50% { height: 40px; } }
.stage-info {
  width: 180px; background: var(--surface-1); border: 1px solid var(--border-gray);
  border-radius: var(--r-md); padding: 14px;
}
.info-row { display: flex; align-items: center; justify-content: space-between; font-size: 13px; padding: 4px 0; }
.info-row span { color: var(--text-tertiary); }
.info-row b { color: var(--text-primary); font-weight: 500; }

.stage-controls { padding: 16px 24px 24px; display: flex; align-items: center; justify-content: center; }
.ctrl-pill {
  width: 600px; max-width: 100%;
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 10px; border-radius: var(--r-pill);
  background: var(--surface-1); border: 1px solid var(--border-gray);
}
.ctrl-btn {
  width: 44px; height: 44px; border-radius: 22px; background: #2a2a30;
  display: flex; align-items: center; justify-content: center; color: var(--text-primary);
}
.ctrl-btn.on { background: var(--accent); }
.ctrl-btn.accent { background: var(--accent); }
.ctrl-btn.off { background: #3a2330; color: #f9a8b4; }
.ctrl-hangup {
  width: 56px; height: 56px; border-radius: var(--r-lg); background: var(--red);
  display: flex; align-items: center; justify-content: center; color: #fff;
}

/* 右侧字幕面板 */
.wb-panel {
  width: 320px; height: 900px; flex-shrink: 0;
  background: var(--bg-sidebar);
  display: flex; flex-direction: column; gap: 16px; padding: 20px;
}
.panel-head { display: flex; flex-direction: column; gap: 4px; }
.panel-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.panel-sub { font-size: 12px; color: var(--text-tertiary); }
.caption-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
.caption-item { display: flex; flex-direction: column; gap: 6px; }
.cap-speaker { font-size: 12px; width: fit-content; }
.cap-speaker.ai { color: var(--accent-text); }
.cap-speaker.me { color: var(--text-secondary); }
.cap-text { font-size: 13px; line-height: 20px; color: #d4d4d8; }

.summary-card {
  background: var(--surface-1); border: 1px solid var(--border-gray);
  border-radius: var(--r-md); padding: 16px;
}
.summary-title { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 10px; }
.summary-list { display: flex; flex-direction: column; gap: 8px; }
.summary-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #d4d4d8; }
.s-dot { width: 6px; height: 6px; border-radius: 3px; background: var(--accent); flex-shrink: 0; }
.summary-actions { display: flex; gap: 8px; margin-top: 14px; }
.sa-btn {
  padding: 8px 14px; border-radius: var(--r-pill);
  background: var(--surface-2); border: 1px solid var(--border-gray);
  color: var(--text-secondary); font-size: 13px;
}
</style>
