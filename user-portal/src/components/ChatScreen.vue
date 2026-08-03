<script setup>
import AppIcon from './AppIcon.vue'

const conversations = [
  { title: 'Python 快速排序实现', time: '2分钟前', active: true },
  { title: '外骨骼控制方案探讨', time: '昨天' },
  { title: '论文摘要润色', time: '昨天' },
  { title: '旅行行程规划', time: '3天前' },
  { title: 'React 组件封装请教', time: '上周' },
  { title: '周报模板生成', time: '上周' }
]

const chips = ['帮我写一份周报', '用通俗语言解释量子计算', 'Python 爬虫示例', '制定一周健身计划']

const code = `def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    mid = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + mid + quick_sort(right)`
</script>

<template>
  <div class="chat-screen">
    <!-- 左侧栏 -->
    <aside class="sidebar">
      <div class="brand">
        <span class="logo"><AppIcon name="sparkle" :size="15" /></span>
        <span class="brand-name">灵犀 AI</span>
      </div>

      <button class="new-chat">
        <AppIcon name="plus" :size="18" />
        <span>新建对话</span>
      </button>

      <div class="search">
        <AppIcon name="search" :size="16" />
        <span>搜索对话</span>
      </div>

      <div class="recent-label">最近对话</div>

      <div class="conv-list">
        <button
          v-for="c in conversations"
          :key="c.title"
          class="conv-item"
          :class="{ active: c.active }"
        >
          <span class="conv-title">{{ c.title }}</span>
          <span class="conv-time">{{ c.time }}</span>
        </button>
      </div>

      <div class="divider"></div>

      <div class="user-card">
        <span class="user-avatar">刘</span>
        <span class="user-name">刘培宽</span>
        <AppIcon name="chevron-down" :size="14" class="user-caret" />
      </div>
    </aside>

    <!-- 右侧主区 -->
    <main class="main">
      <header class="main-top">
        <div class="mt-left">
          <span class="mt-title">Python 快速排序实现</span>
          <span class="mt-tag">智能会话</span>
        </div>
        <div class="mt-right">
          <button class="mt-btn"><AppIcon name="phone-off" :size="18" /></button>
          <button class="mt-btn"><AppIcon name="video" :size="18" /></button>
          <button class="mt-btn"><AppIcon name="more" :size="18" /></button>
        </div>
      </header>

      <div class="divider"></div>

      <div class="messages">
        <!-- AI 消息 1 -->
        <div class="msg-row ai">
          <span class="msg-avatar">灵</span>
          <div class="bubble ai-bubble">
            <p class="bubble-text">
              你好，我是灵犀 AI，你的智能对话助手。我可以帮你写作、分析数据、编写代码、解答疑问，随时开始吧。
            </p>
            <div class="chips">
              <button v-for="c in chips" :key="c" class="chip">{{ c }}</button>
            </div>
          </div>
        </div>

        <!-- 用户消息 -->
        <div class="msg-row user">
          <div class="bubble user-bubble">那帮我用 Python 实现一个快速排序吧，要简洁易懂。</div>
        </div>

        <!-- AI 消息 2 -->
        <div class="msg-row ai">
          <span class="msg-avatar">灵</span>
          <div class="bubble ai-bubble">
            <p class="bubble-text">
              当然可以！快速排序（Quick Sort）是一种基于分治思想的排序算法，平均时间复杂度为 O(n log
              n)。核心步骤是：选择一个基准值（pivot），将数组划分为小于和大于基准的两部分，再递归处理。
            </p>
            <pre class="code-block">{{ code }}</pre>
            <p class="bubble-text">
              上面使用列表推导式实现，代码简洁、可读性强。如果需要原地排序以节省内存，可以改为双指针写法。
            </p>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="composer">
        <div class="composer-box">
          <button class="cp-ico"><AppIcon name="paperclip" :size="18" /></button>
          <button class="cp-ico"><AppIcon name="smile" :size="18" /></button>
          <button class="cp-ico"><AppIcon name="image" :size="18" /></button>
          <input class="cp-input" placeholder="给灵犀 AI 发送消息…" />
          <button class="cp-send"><AppIcon name="send" :size="18" /></button>
        </div>
        <div class="composer-hint">Enter 发送，Shift + Enter 换行</div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.chat-screen {
  width: 1440px;
  height: 900px;
  display: flex;
  font-family: var(--font-sans);
  background: var(--bg-base);
}

/* 左侧栏 */
.sidebar {
  width: 280px;
  height: 900px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 4px; }
.logo {
  width: 28px; height: 28px; border-radius: var(--r-xs);
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.brand-name { font-size: 18px; font-weight: 700; color: var(--text-primary); }

.new-chat {
  width: 100%; padding: 11px;
  border-radius: var(--r-sm);
  background: var(--accent-grad);
  color: #fff; font-size: 14px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.search {
  display: flex; align-items: center; gap: 8px;
  padding: 9px; border-radius: var(--r-xs);
  background: var(--surface-1);
  border: 1px solid var(--border-gray);
  color: var(--text-tertiary); font-size: 13px;
}
.recent-label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); padding: 0 4px; }

.conv-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.conv-item {
  width: 100%; height: 39px; padding: 10px;
  border-radius: var(--r-xs);
  display: flex; align-items: center; justify-content: space-between;
  text-align: left;
}
.conv-item:hover { background: rgba(255, 255, 255, 0.03); }
.conv-item.active { background: var(--accent-soft); }
.conv-title { font-size: 13px; color: #d4d4d8; }
.conv-item.active .conv-title { color: var(--accent-text); font-weight: 500; }
.conv-time { font-size: 11px; color: var(--text-tertiary); }
.conv-item.active .conv-time { color: var(--accent-light); }

.divider { height: 1px; background: var(--border-gray); }

.user-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px; border-radius: var(--r-sm);
  background: var(--surface-1);
}
.user-avatar {
  width: 32px; height: 32px; border-radius: 16px;
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 14px; font-weight: 700;
}
.user-name { flex: 1; font-size: 14px; font-weight: 500; color: var(--text-primary); }
.user-caret { color: var(--text-tertiary); }

/* 右侧主区 */
.main {
  width: 1160px;
  height: 900px;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 50% 0%, rgba(124, 58, 237, 0.1), rgba(124, 58, 237, 0) 55%),
    var(--bg-base);
}
.main-top {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
}
.mt-left { display: flex; align-items: center; gap: 12px; }
.mt-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.mt-tag {
  font-size: 12px; color: var(--text-secondary);
  padding: 5px; border-radius: var(--r-pill);
  background: var(--surface-1);
  border: 1px solid var(--border-gray);
}
.mt-right { display: flex; align-items: center; gap: 8px; }
.mt-btn {
  width: 36px; height: 36px; border-radius: var(--r-xs);
  background: var(--surface-1);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary);
}

.messages {
  flex: 1; overflow-y: auto;
  display: flex; flex-direction: column; gap: 20px;
  padding: 28px; align-items: center;
}
.msg-row { display: flex; gap: 12px; width: 720px; }
.msg-row.user { justify-content: flex-end; }
.msg-avatar {
  width: 36px; height: 36px; border-radius: var(--r-md);
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 14px; font-weight: 600; flex-shrink: 0;
}
.bubble { border-radius: var(--r-md); }
.ai-bubble {
  background: var(--surface-1);
  border: 1px solid var(--border-gray);
  padding: 16px; width: 672px;
}
.bubble-text { font-size: 15px; line-height: 1.6; color: var(--text-primary); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.chip {
  padding: 8px 12px; border-radius: var(--r-xs);
  background: var(--bg-base);
  color: var(--text-secondary); font-size: 13px;
}
.chip:hover { color: var(--text-primary); }
.user-bubble {
  background: var(--accent-grad);
  color: #fff; font-size: 15px; line-height: 1.6;
  padding: 12px 16px; width: 504px;
}
.code-block {
  margin: 12px 0;
  padding: 16px;
  background: var(--bg-base);
  border-radius: var(--r-xs);
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; line-height: 1.55;
  color: #e4e4e7;
  white-space: pre-wrap;
  overflow-x: auto;
}

.composer { padding: 12px 24px 24px; display: flex; flex-direction: column; align-items: center; }
.composer-box {
  width: 760px; max-width: 100%;
  display: flex; align-items: center; gap: 8px;
  padding: 8px; border-radius: var(--r-lg);
  background: var(--surface-1);
  border: 1px solid var(--border-gray);
}
.cp-ico {
  width: 36px; height: 36px; border-radius: var(--r-xs);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
}
.cp-input {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-size: 14px; font-family: inherit;
}
.cp-input::placeholder { color: var(--text-tertiary); }
.cp-send {
  width: 40px; height: 40px; border-radius: var(--r-sm);
  background: var(--accent-grad);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
}
.composer-hint { margin-top: 10px; font-size: 12px; color: var(--text-tertiary); }
</style>
