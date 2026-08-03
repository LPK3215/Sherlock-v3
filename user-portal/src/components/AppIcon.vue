<script setup>
// 线性风格图标集（stroke=currentColor），提取自设计稿内的矢量 wireframe。
// viewBox 统一 24x24，与 Figma 矢量比例一致。
const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 }
})

const ICONS = {
  'arrow-left': '<path d="M15 18l-6-6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/>',
  video:
    '<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="M16 10l5-3v10l-5-3z"/>',
  'screen-share':
    '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M12 13V8m0 0l-2 2m2-2l2 2"/>',
  captions:
    '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M7 11h2M7 15h4M14 11h3M14 15h3"/>',
  smile:
    '<circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01M15 9h.01"/>',
  more: '<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/>',
  'phone-off':
    '<path d="M3.5 10.5c4.5-2.8 12.5-2.8 17 0l-1.8 3.2-3.2-.8v-1.8c-2.6-.9-7.4-.9-10 0v1.8l-3.2.8z"/><path d="M3 3l18 18"/>',
  'zoom-in':
    '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35M11 8v6M8 11h6"/>',
  'zoom-out': '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35M8 11h6"/>',
  flip:
    '<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/>',
  palette:
    '<path d="M12 3a9 9 0 0 0 0 18c1.5 0 2-1 2-2s-.5-1.5-.5-2.5S13.5 14 15 14h2a4 4 0 0 0 4-4c0-4.4-4-7-9-7z"/><circle cx="8" cy="9" r="1"/><circle cx="12" cy="7" r="1"/><circle cx="16" cy="9" r="1"/>',
  settings:
    '<circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>',
  signal: '<path d="M4 18v-3M9 18v-7M14 18v-11M19 18V6"/>',
  chat: '<path d="M4 5h16v11H9l-4 4V5z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  users:
    '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 5.5a3 3 0 0 1 0 5.5M21 20c0-2.8-1.8-5-4.5-5.8"/>',
  sparkle: '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>',
  send: '<path d="M4 12l16-7-7 16-2-7z"/>',
  paperclip:
    '<path d="M21 11l-9 9a5 5 0 0 1-7-7l9-9a3 3 0 0 1 4 4l-9 9a1 1 0 0 1-2-2l8-8"/>',
  check: '<path d="M5 12l5 5L19 7"/>',
  image:
    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>'
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="ICONS[name] || ''"
  ></svg>
</template>
