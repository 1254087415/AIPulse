# Popup「复制链接」改为链接框内联小按钮

日期：2026-07-29
状态：已完成（选项确认：1A 内联 SVG / 2A 框外右侧 flex；202 单测 + build:e2e + 验证 agent 复核通过）

## 背景与目标

当前 popup 底部 `.actions` 区有一个通栏大按钮「复制链接」（与「复制字幕」两列网格布局），占地方、视觉权重过高——它只是辅助动作，却和主 CTA「归档到 AIPulse」抢注意力。

目标：把「复制链接」改成「链接」字段框内/框尾的一个小占位按钮（icon 级尺寸），点击复制当前展示 URL；其余布局与逻辑不变。

## 现状代码锚点

- `extensions/chromium/src/popup.tsx:425-431` —「链接」字段：`.field > .url-value`（含可选 `.short-badge` 短链徽标）。
- `extensions/chromium/src/popup.tsx:489-502` — `.actions` 区：「复制链接」+ 条件渲染的「复制字幕」。
- `extensions/chromium/src/popup.tsx:302-312` — `handleCopyUrl`：写剪贴板后把状态栏设为「链接已复制」（反馈渠道保留不变）。
- `extensions/chromium/src/popup.css:175-184` — `.url-value` 样式；`:225-255` — `.actions` 两列网格与按钮样式。
- 测试：`tests/unit/popup.test.tsx` 目前**没有**覆盖复制按钮/`.actions`/`.url-value`，无存量断言会破。

## 方案

### 1. popup.tsx 结构改动

「链接」字段改为一行 flex 容器，URL 文本 + 内联复制小按钮：

```tsx
<label className="field">
  <span className="field-label">链接</span>
  <span className="url-row">
    <span className="url-value" title={displayUrl}>
      {isShortLink(displayUrl) && <span className="short-badge">短链</span>}
      {displayUrl}
    </span>
    <button
      type="button"
      className="copy-url-btn"
      onClick={handleCopyUrl}
      disabled={loading || subtitleLoading || shareUrlLoading}
      aria-label="复制链接"
      title="复制链接"
    >
      ⧉
    </button>
  </span>
</label>
```

- 图标用文本字符 `⧉`（或两个叠方块的 SVG，见「待定项」），不引入新依赖。
- `.actions` 区删除「复制链接」按钮；「复制字幕」保留在原位（仅字幕存在时出现）。`.actions` 只剩一个子项时半宽显示即可接受，无需改网格。

### 2. popup.css 新增样式

```css
.url-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.url-row .url-value {
  flex: 1;
  min-width: 0; /* 长 URL 在 flex 下正确换行 */
}
.copy-url-btn {
  flex: none;
  height: 24px;
  min-width: 24px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--card-bg);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.copy-url-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}
.copy-url-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
```

同时把 `.copy-url-btn:focus-visible` 加进现有 `popup.css:94` 的 focus 样式组。

### 3. 测试（tests/unit/popup.test.tsx 追加）

- 渲染后存在 `aria-label="复制链接"` 的按钮；点击后 `navigator.clipboard.writeText` 以 `displayUrl` 被调用，状态栏显示「链接已复制」。
- `.actions` 区不再包含「复制链接」文本。

## 验证

1. `cd extensions/chromium && pnpm vitest run tests/unit/popup.test.tsx`
2. `pnpm build:e2e` 后在真实浏览器重载扩展，打开抖音页目测：链接框右侧小按钮、点击复制成功、短链徽标不挤压、布局不破。

## 明确不做

- 不动「复制字幕」按钮与字幕预览区。
- 不改 `handleCopyUrl` 逻辑（状态栏反馈沿用）。
- 不引入图标库；不动其他字段布局。

## 待定项

1. 按钮内容：`⧉` 字符（零依赖，个别系统字形可能缺）vs 内联 16px SVG（两个叠放圆角矩形，最稳）。倾向 SVG。
2. 按钮放在 URL 框**内右侧**（绝对定位叠在 `.url-value` 内）还是框**外右侧**（flex 并列）。倾向框外 flex，简单且不伤 `.url-value` 内边距。
