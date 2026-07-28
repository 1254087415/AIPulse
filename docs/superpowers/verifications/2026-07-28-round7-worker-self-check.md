# Round 7 Worker Self-Check — spec §6.12 FollowDetailView 完整化

> **本轮工作分支**：`fix/up-detail-full-spec`
> **base**：`feat/extension-real-e2e @ 19043a4`
> **工作树**：`/Users/zab/.paseo/worktrees/1kstjvff/fix-up-detail-full-spec`
> **轮次定位**：替换 round 5 简版 `UpDetailView.vue`（仅 hero card + 关联 hotspots），
> 按 spec §6.12 (Q20) 完整化 FollowDetailView，并把路由从 `/up/<uid>` 切到
> `/followed-up/<uid>`。

## 1. 实现范围（与 spec §6.12 / §6.14 对齐）

| 区域 | spec 条款 | 本轮交付 |
|---|---|---|
| 路由表 | §6.14 | 删 `/up/:uid`、保 `/followed-up/:uid`（绑 `FollowDetailView`） |
| 详情 header | §6.12 头部 | 64x64 头像 `<img>` + `<h1>` 昵称 + HealthDot + healthy/warning/error 徽章 + enabled 状态 tag |
| 元数据 dl | §6.12 元数据 | 6 对 dt/dd：mid / 主页 URL / 策略 / 间隔 / 上次扫描 / 最近错误 |
| 合集 accordion | §6.12 合集 | `CollectionAccordion` 用 `<details>/<summary>` 展开后注入 `videos` |
| 视频分页 | §6.12 视频 | `useInfiniteQuery` 调 `listVideos(uid, { offset, limit: 20 })`，`getNextPageParam` 读 `nextOffset` |
| 散落视频 | §6.12 散落 | `variant="orphan"` 子区，h3 标题包含计数 |
| 操作按钮 | §6.12 操作 | 立即扫描 / 暂停(恢复) / 编辑占位 / 删除(ConfirmModal) / 加载更多历史 |
| 删除确认 | §6.12 删除 | `ConfirmModal` 二次确认 → DELETE `/api/followed-up/{uid}` → `router.push('/dashboard?tab=follow-list')` |
| 返回 | §6.12 返回 | 顶部 `← 返回` 调 `router.back()` |
| 视频条目 | §6.12 视频条目 | 新组件 `VideoListItem.vue`：bvid + title + status + 「在 B 站打开」`target="_blank"` 链接 |
| 跳转入口 | §6.11 | `FollowListPanel.vue:196` 路由链接 `/up/{uid}` → `/followed-up/{uid}` |
| API 客户端 | §6.12 | `followDetail.ts` 新增 `fetchDetail` / `listVideos`（保留 `fetchOverview` 兼容 D6 测试） |
| 删除旧实现 | spec 指令 | 删 `frontend/src/views/UpDetailView.vue`、`frontend/src/api/upDetail.ts`、`frontend/src/views/__tests__/UpDetailView.test.ts` |
| 旧测试更新 | 兼容 | 改 `tests/unit/follow-detail-d6.test.ts` 走新端点；删 `tests/unit/follow-detail-view.test.ts`（旧组件专属） |
| 依赖 | spec §6.12 使用 vue-query | `frontend/package.json` 新增 `@tanstack/vue-query@^5.101.4`，`main.ts` 安装 `VueQueryPlugin` |

## 2. 后端端点（本轮新增）

- `GET /api/followed-up/{uid}/detail` — spec-shaped payload（含 avatar/enabled/health/strategy/interval_minutes/collections/orphan_videos）
- `GET /api/followed-up/by-uid/bilibili/{uid}/detail` — 同 payload，uid-alias 入口
- `GET /api/followed-up/{uid}/videos?offset=&limit=&collection_id=` — 返回 `{ items, nextOffset }`
- `GET /api/followed-up/by-uid/bilibili/{uid}/videos?...` — 同上，uid-alias 入口
- avatar 解析：优先 `config.avatar_url`，否则懒查 B 站 card API 并回写 `config` 缓存

## 3. 测试覆盖（15 个 TC 1:1 对应）

`frontend/tests/unit/follow-detail-v7.test.ts`（15 测，全绿）：

| TC | 标题 | 状态 |
|---|---|---|
| TC-UI-FOLLOW-DETAIL-01 | 头部：头像 + 昵称 + 健康徽章 | ✓ |
| TC-UI-FOLLOW-DETAIL-02 | 元数据 dl：6 项 + last_error 红字 | ✓ |
| TC-UI-FOLLOW-DETAIL-03 | 合集区域渲染 `<CollectionAccordion>` 列表 | ✓ |
| TC-UI-FOLLOW-DETAIL-04 | 合集点击展开视频列表（`<details>` toggle） | ✓ |
| TC-UI-FOLLOW-DETAIL-05 | 视频列表 VideoListItem 渲染最近 20 条 | ✓ |
| TC-UI-FOLLOW-DETAIL-06 | 加载更多历史翻页 + 加载中… + disabled | ✓ |
| TC-UI-FOLLOW-DETAIL-07 | 立即扫描 → POST `/api/followed-up/{uid}/sync` | ✓ |
| TC-UI-FOLLOW-DETAIL-08 | 暂停 / 恢复 → PATCH enabled + label 翻转 | ✓ |
| TC-UI-FOLLOW-DETAIL-09 | 删除 → 二次确认 modal → DELETE + router.push | ✓ |
| TC-UI-FOLLOW-DETAIL-10 | 散落视频区块 `variant="orphan"` | ✓ |
| TC-UI-FOLLOW-DETAIL-11 | `useInfiniteQuery` `getNextPageParam` 解析 `nextOffset` | ✓ |
| TC-UI-FOLLOW-DETAIL-12 | `enabled: !!uid.value` 防止空 uid 触发请求 | ✓ |
| TC-UI-FOLLOW-DETAIL-13 | 返回按钮 → `router.back()` | ✓ |
| TC-UI-FOLLOW-DETAIL-14 | 时间渲染 `toLocaleString(zh-CN)` | ✓ |
| TC-UI-FOLLOW-DETAIL-15 | 「在 B 站打开」→ `window.open(https://www.bilibili.com/video/{bvid}, _blank)` | ✓ |

`frontend/src/components/__tests__/VideoListItem.test.ts`（6 测）：bvid + title + status、
default/orphan 变体、`href` + `target=_blank`、click 触发 `open-bilibili`、title 回退到 bvid。

`tests/integration/test_followed_up_v7_detail_videos.py`（6 测）：`/detail` 形状、
uid-alias fallback、404、`/videos` 分页 + nextOffset、uid-alias 视频、`/videos?collection_id=` 过滤。

## 4. 测试结果

| 套件 | 通过 / 总数 | 备注 |
|---|---|---|
| 单元 + 集成（前端） | 186 / 186（26 files） | 包含 v7 15 测、VideoListItem 6 测、D6 9 测、VideoListItem + API + 既有 156 测 |
| `vue-tsc -b --noEmit` | 0 错 | 全类型干净 |
| `vite build` | OK 159 modules, 705ms | `FollowDetailView-DY6WGcmM.js` 23.4 kB（gzip 8.1 kB） |
| 后端集成 `pytest tests/integration -q` | 111 passed, 2 skipped | 与 round 5 基线 111/2 一致，0 回归；新增 6 测全过 |
| 真实数据 E2E（Playwright） | dashboard → /followed-up/1567748478 → /followed-up/517327498 | 两个真实 UP 主详情页均渲染完整（hero / 6 项 metadata / 20 视频 / 散落视频 / 操作） |

## 5. 真实 E2E 截图

- `docs/superpowers/verifications/2026-07-28-round7-followed-up-detail.png`（跟李沐学AI / uid 1567748478 / 169 KB）
- `docs/superpowers/verifications/2026-07-28-round7-followed-up-detail-luoxiang.png`（罗翔说刑法 / uid 517327498 / 192 KB）

## 6. 副作用与约束遵守

- ✓ 没改 .env / .env.example / data/settings.json 真 secrets（worktree 内 .env 仅为指向主 checkout 的 symlink）
- ✓ 没 reset 真 DB；E2E 跑的是主 checkout 的 `data/aipulse.db` 已有 2 个真实 UP 主
- ✓ 没碰用户真实业务 Reminder 列表
- ✓ 没 git push；所有 commit 在 worktree 内
- ✓ 删除了 spec 要求删除的旧文件（不只是 `git restore`，按 §6.14 切到 `/followed-up/:uid` 后旧 `/up/:uid` 实现整体退役）
- ✓ 链式架构：未反向问询主会话/verifier；只发初始 ready 消息 + 最终回报

## 7. 待 verifier 复核

1. 路由表：仅 `/followed-up/:uid` 存在；`/up/:uid` 不再注册
2. FollowDetailView 严格 match spec §6.12 的 15 个 TC
3. 视频分页 nextOffset + 加载更多历史按钮状态正确翻转
4. 删除流程走 ConfirmModal 而非 window.confirm
5. 真实数据下 hero / 6 项 metadata / 20 视频 / 散落视频 完整呈现
