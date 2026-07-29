# AIPulse Web Dashboard UI 一致性审查报告（Round 7）

> 日期：2026-07-29
> 审查范围：`frontend/`（Vue 3 + Vite），`http://127.0.0.1:5173/dashboard` 全部 6 个 sidebar 页面 + dashboard 内 5 个子 tab
> 审查方式：kimi-webbridge 真实浏览器逐页截图 + 对照设计基线（见下）+ 关键组件源码核对
> 纪律：全程只读操作，未修改任何代码文件；产出仅本报告与截图

## 设计基线（审查依据）

1. **Design tokens**：`frontend/src/styles/tokens.css` + `frontend/src/components/sidebar/sidebar.css`
   - 色板：`--surface-bg #F7F7F5`、`--surface-elevated #FFF`、`--border-subtle #E8E8E6`、`--text-primary #1A1A1A`、`--text-secondary #6B6B6B`、`--accent-coral #F97316`、状态色 `--status-green/amber/red`
   - 字号阶：`--text-xs 11px` ~ `--text-2xl 28px`；圆角阶：`--radius-sm 6px` / `--radius-md 10px` / `--radius-lg 16px`
   - 按钮状态色（sidebar.css）：`--state-queued/running/done/error`
2. **设计文档**：`docs/superpowers/specs/2026-07-09-v0.2-web-dashboard-design.md`
   - §6.3 统一状态样式（`.state-empty` / `.state-loading` / `.state-error`）
   - §6.4 卡片悬停上浮加深阴影、标题跳转详情、标签化元信息
   - §8.4 错误处理：后端 sanitize + 前端统一文案，不直接展示原始报错

## 环境备注

- 审查开始时 vite dev 因 `@tanstack/vue-query` 未安装（package.json 已声明但 node_modules 缺失）而无法渲染，已执行 `pnpm install` 并重启 vite dev 后恢复。此为本轮发现的环境问题，不计入 UI 不一致清单。
- 页面右缘出现的粉色/蓝色悬浮图标为第三方浏览器扩展注入，非 AIPulse UI，已从 findings 中排除。

## 截图索引

| 文件 | 页面 |
|---|---|
| `01-dashboard.png` | AI 热点（dashboard 默认 tab） |
| `02-follow-list.png` | 关注列表 |
| `03-records.png` | 处理记录 |
| `04-upcoming.png` | 即将学习（empty state） |
| `05-failed.png` | 失败 |
| `06-sources.png` | 来源 |
| `07-keywords.png` | 关键词（empty state） |
| `08-jobs.png` | 定时任务 |
| `09-digests.png` | 摘要 |
| `10-settings.png` | 系统（设置） |

截图目录：`docs/.screenshots/ui-audit/`

---

## 不一致清单

### High

#### H1. 「总结」按钮引用未定义的旧主题变量，idle 态退化为浏览器默认样式

- **页面/位置**：处理记录、失败 tab 每一行右侧的「总结」按钮（`SummarizeButton.vue`）
- **问题**：`.summarize-btn--idle { background: var(--ink); color: var(--paper) }`（`SummarizeButton.vue:214-215`）引用的 `--ink` / `--paper` 在 frontend 主题（`tokens.css`、`sidebar.css`）中**均未定义**——它们属于 `web/` 旧「心电图纸」主题。idle 状态因此退化为 UA 默认按钮外观：白底 + 深色粗边框 + 黑字，与全站按钮体系（橙色实心主按钮、浅灰描边次按钮）完全脱节，视觉上像"没样式"的按钮。其余状态色用的 `--state-*` 定义在 `sidebar.css`（组件文件里的 `:root`），token 归属也错位。
- **截图**：`03-records.png`（右上角「总结」黑框按钮）
- **设计依据**：tokens.css 色板中无 `--ink`/`--paper`；sidebar.css 注释自称 "Sidebar design tokens"
- **建议**：idle 态改用现token（如 `background: var(--text-primary); color: var(--surface-elevated)`，或明确为 secondary 描边样式）；将 `--state-*` 上移到 `tokens.css`
- **严重程度**：High

#### H2. 失败 tab 直接渲染原始 API 错误 JSON（Python dict repr）

- **页面/位置**：失败 tab 每行标题下方
- **问题**：红色小字直接展示 `Error code: 401 - {'error': {'message': 'The API Key appears to be invalid or may have expired. Please verify your credentials and try again.', 'type': 'invalid_authentication_error'}}`——单行超长英文原始报错，含内部字段名。同一页另一条是中文 `业务侧结果字段缺失：hotspot_id, note_path 未填`，两种错误文案语言、格式都不统一。
- **截图**：`05-failed.png`
- **设计依据**：设计 §8.4「后端 sanitize_error_message 去除敏感信息；前端统一使用『信号中断』『接口异常』等文案」
- **建议**：前端对错误消息做映射/截断（如「API Key 失效，请到 系统 页检查 LLM 配置」），原始错误收进 title/tooltip 或折叠详情
- **严重程度**：High

#### H3. 页面头部（Page Header）三套体系并存，且含开发期占位文案

- **页面/位置**：全部页面
- **问题**：同为"页面标题区"，实际存在三套结构：
  - A 套：中文大标题 + 中文副标题（AI 热点「按发布时间展示最新信号」、关注列表「2 个 UP 主 · 全部启用」）
  - B 套：英文小号 eyebrow + 中文大标题（处理记录 `FOLLOW-UP`、即将学习 `LEARNING QUEUE`、失败 `ACTION REQUIRED`）
  - C 套：中文标题 + 描边 pill 占位提示「该视图将在 Phase X 完整实现（当前仅展示真实列表）」（来源/关键词=Phase 7、定时任务=Phase 1、摘要=Phase 4——阶段号本身也不一致）
  - 设置页则只有标题。头部右侧操作位也不统一：主按钮（关注列表）、「刷新」灰按钮（处理记录/即将学习/失败）、计数「52 条」（AI 热点）、无（其余）。
- **截图**：`01-dashboard.png`、`02-follow-list.png`、`03-records.png`、`06-sources.png`、`10-settings.png`
- **设计依据**：设计 §6.3「页面标题 + 副标题 + 数据读数」统一布局
- **建议**：定一套 PageHeader 组件（标题 + 副标题 + 右侧 slot），全站复用；Phase 占位 pill 在面向用户的界面移除或统一为「Beta」标记
- **严重程度**：High

### Medium

#### M1. 按钮样式至少 5 种，无统一按钮规范

- **页面/位置**：全站
- **问题**：并存——① 橙色实心主按钮（+ 添加 UP 主）；② 浅灰描边次按钮（立即同步/编辑）；③ 红色文字描边按钮（删除）；④ 蓝色文字链接（查看详情）；⑤ UA 默认黑框（总结，见 H1）；⑥ 全宽橙描边白底（设置页「保存」）；⑦ 灰色小按钮（刷新）。圆角也不一（`--radius-sm` vs `--radius-md` 混用）。`tokens.css` 没有任何按钮级 token，各组件各自为政。
- **截图**：`02-follow-list.png`（同一张卡片右侧就有 4 种风格）、`03-records.png`、`10-settings.png`
- **建议**：建立 `primary / secondary / danger / ghost` 四级按钮组件并收敛全部调用点；设置页「保存」应与「+ 添加 UP 主」同为实心主按钮
- **严重程度**：Medium

#### M2. 状态呈现方式不统一（badge / 纯文本 / mono chip 三种并存）

- **页面/位置**：关注列表、来源、处理记录、AI 热点、定时任务
- **问题**：同类"状态"信息表达各异——关注列表用彩色 badge（`B 站` 橙色、`启用`、`● 健康` 绿色）；来源页用绿色「启用」badge；处理记录用**纯英文文本** `Partial` / `Failed`（无 badge、Failed 未用 `--status-red` 着色）；热点卡的 `medium` 为纯文本、热度为橙色 `热度 0.0`；定时任务的 trigger 直接展示原始 repr 灰 chip `interval[0:01:00]` / `cron[hour='8', minute='0']`。
- **截图**：`02-follow-list.png`、`03-records.png`、`06-sources.png`、`08-jobs.png`
- **设计依据**：tokens.css 已定义 `--status-green/amber/red` 状态色
- **建议**：统一 StatusBadge 组件（颜色语义：成功绿/警告橙/失败红/中性灰）；trigger 转译为「每 30 分钟」「每天 08:00」
- **严重程度**：Medium

#### M3. 技术实现细节直接泄漏到 UI，且存在文本溢出布局 bug

- **页面/位置**：来源页、定时任务页、处理记录/失败
- **问题**：来源卡展示完整 Python 类路径 `aipulse.collectors.arxiv.ArxivCollector` 且**溢出卡片右边界**（布局 bug）；定时任务展示 func 全路径与 trigger repr；处理记录展示 BVID；arXiv 卡展示原始英文 httpx 错误 `Redirect response '301 Moved Permanently' for url '[URL]'...`（深色 mono 样式，与失败 tab 的红色错误样式又不一致）。
- **截图**：`06-sources.png`（采集器类名溢出、arXiv 错误）、`08-jobs.png`
- **设计依据**：设计 §8.4 错误信息应 sanitize
- **建议**：类路径/func 路径移入 tooltip 或「技术详情」折叠区；卡片内容加 `overflow-wrap`/省略；错误展示统一走 H2 的映射方案
- **严重程度**：Medium

#### M4. 日期/时间格式不统一

- **页面/位置**：AI 热点、关注列表、定时任务（`2026/7/24 11:00:00`，`toLocaleString()` 输出）vs 摘要页（`2026-07-29`，ISO）
- **问题**：同一产品内两种日期格式并存；间隔表达也有「30 分钟 / 次」（关注列表）与「30 分钟」（来源）两种。
- **截图**：`01-dashboard.png`、`02-follow-list.png`、`09-digests.png`
- **建议**：统一 `lib/format.ts` 时间格式化函数，全站一种格式（建议 `YYYY-MM-DD HH:mm`）
- **严重程度**：Medium

#### M5. 中英文混用无规则

- **页面/位置**：多页
- **问题**：英文 eyebrow（`FOLLOW-UP` 等）；定时任务名中英混排 `Scan all enabled followed UP主` 与 snake_case `sync_all_sources` 并存；状态词 `Partial`/`Failed`/`medium` 未翻译；`uid: 517327498` 直接展示；占位文案用「Phase X」开发术语。
- **截图**：`03-records.png`、`05-failed.png`、`08-jobs.png`
- **建议**：面向用户的文案全中文（或建立 i18n 键值）；内部标识符不直接上屏
- **严重程度**：Medium

#### M6. Empty state 呈现不一致

- **页面/位置**：关键词页 vs 即将学习 tab
- **问题**：关键词页 empty 是裸文本「暂无关键词」（`<p class="state-line">`，无卡片、无引导动作）；即将学习是虚线卡片 + 完整说明句「当前没有待学习内容。新的关注视频出现后会自动加入这里。」两种 empty state 结构、留白、引导性都不同。摘要页条目正文仅显示「—」也近似半空态但未做处理。
- **截图**：`07-keywords.png`、`04-upcoming.png`、`09-digests.png`
- **设计依据**：设计 §6.3 统一 `.state-empty` 样式；§7.1 空态应给出引导（如"前往关键词添加关注词"）
- **建议**：统一 EmptyState 组件（图标 + 说明 + 可选引导按钮）
- **严重程度**：Medium

#### M7. 热点卡片不可点击，无法进入详情页

- **页面/位置**：AI 热点 tab 卡片
- **问题**：`DashboardHotspotPanel.vue` 渲染为纯静态 `<div>` 列表——无 `RouterLink`、无 `@click`、无 `cursor: pointer`，a11y tree 中卡片无 link/button 角色，键盘无法触达。热点详情视图（`HotspotDetailView.vue`）存在，但 dashboard 没有任何入口可达。
- **截图**：`01-dashboard.png`
- **设计依据**：设计 §6.4「标题（跳转详情）」
- **建议**：卡片标题包 `RouterLink`（或整卡可点 + 标题链接），补 hover 指针与焦点环
- **严重程度**：Medium

### Low

#### L1. 热点卡片无 hover 反馈

- **页面/位置**：AI 热点 tab
- **问题**：`DashboardHotspotPanel.vue` 无任何 `:hover` 样式（全项目 14 个文件有 hover，该面板不在列）；关注列表卡片（`FollowCard.vue`）有 hover。同类卡片交互反馈不一致。
- **设计依据**：设计 §6.4「悬停时卡片上浮并加深阴影」
- **严重程度**：Low

#### L2. 热点卡元信息为未格式化的纯文本串

- **页面/位置**：AI 热点 tab 卡片底部
- **问题**：`bilibili_up medium 2026/7/24 11:00:00` 直接拼接展示——source_type 带下划线、importance 未翻译、与 M2/M4 的格式问题叠加；设计中应为标签化元信息。另外全部条目热度均为 `0.0`，橙色高亮「热度 0.0」反而视觉噪音大。
- **截图**：`01-dashboard.png`
- **设计依据**：设计 §6.4「来源/分类/重要性/发布时间标签」
- **严重程度**：Low

#### L3. Sidebar 图标为风格混搭的 unicode 字符

- **页面/位置**：左侧 sidebar 6 个导航项
- **问题**：图标为 ◐ / ⚙ / ✎ / ⌚ / ✦ / ☰ 等散装 unicode 字符，粗细、风格、语义体系均不统一（「系统」用汉堡 ☰ 通常表示菜单，「来源」用齿轮 ⚙ 通常表示设置，语义错位）。
- **截图**：`01-dashboard.png`（左侧栏）
- **建议**：换统一 icon set（如 lucide），保持同一线宽/风格
- **严重程度**：Low

#### L4. 关注列表头像占位符为空米色圆

- **页面/位置**：关注列表卡片左侧
- **问题**：两个 UP 主头像均为空白米色圆形占位，无首字符/默认图标，疑似头像加载失败的 fallback 未做内容。
- **截图**：`02-follow-list.png`
- **建议**：fallback 显示 UP 主名首字或统一默认头像
- **严重程度**：Low

#### L5. 错误状态配色两处不一致

- **页面/位置**：失败 tab（红色文字）vs 来源 arXiv 卡（深色 mono 文字）
- **问题**：同为"错误信息"，一处用 `--status-red`，一处无红色语义；与 M2 状态色问题同源但体现在 error 场景。
- **截图**：`05-failed.png`、`06-sources.png`
- **严重程度**：Low

---

## 汇总

### 按严重程度

| 严重程度 | 数量 |
|---|---|
| High | 3 |
| Medium | 7 |
| Low | 5 |
| **合计** | **15** |

### 按页面分布

| 页面 | High | Medium | Low |
|---|---|---|---|
| 处理记录 / 失败 | H1、H2 | M2、M3、M5 | L5 |
| 全站/头部 | H3 | M1、M4 | — |
| 来源 | — | M3、M5 | L5 |
| AI 热点 | — | M7 | L1、L2 |
| 关键词 | — | M6 | — |
| 即将学习 | — | M6 | — |
| 定时任务 | — | M2、M3、M5 | — |
| 摘要 | — | M4、M6 | — |
| 设置 | — | M1 | — |
| 关注列表 | — | M1、M2、M4 | L4 |
| Sidebar | — | — | L3 |

### Top 5 最值得先修

1. **H1 总结按钮变量失效**——修复成本极低（换两个 var），但当前是全站视觉上最"破"的元素，且每行重复出现。
2. **H2 失败页原始错误 JSON**——用户可直接看到内部报错原文，既有观感问题也有信息泄漏风险。
3. **H3 页面头部三套体系 + Phase 占位文案**——是「风格不统一」体感最强的来源；收敛为一个 PageHeader 组件可一次性解决。
4. **M1 按钮五级混乱**——在 H1 修复后顺势建立按钮组件规范，ROI 高。
5. **M3 技术细节泄漏 + 来源卡文本溢出**——含真实布局 bug（类名溢出卡片），修复时一并把类路径/trigger repr 转译为可读文案。
