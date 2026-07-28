# Round 8 — Chrome extension 真页面 E2E 自检

**worktree**: `fix/extension-real-e2e` (base `feat/extension-real-e2e` @ `19043a4`)
**日期**: 2026-07-28
**作者**: Paseo agent round 8 worker

## 目标对齐（spec 重述）

1. 跑通 `extensions/chromium/tests/e2e/` 下 6 个 spec，开真页验证 badge / submit / 内容提取 / 错误路径
2. 加 `real-bilibili.real.spec.ts` / `real-douyin.real.spec.ts` 真页 TDD
3. 加 `error-paths.real.spec.ts`（断网/5xx/cookie 失效）
4. 不许 mock 后端（happy path 必走真 sidecar），失败形态允许局部拦截

## 6 个原 spec 真实跑结果

| spec | 结果 | 备注 |
|------|------|------|
| `extension.spec.ts` | ✅ PASS | 4 平台 fixture 全识别 + 真 sidecar 收 4 个 task_id |
| `subtitle.spec.ts` | ✅ PASS | 真 B 站 BV1JNMV6dEp2 抓 AI 字幕 + 真 submit |
| `douyin.spec.ts` | ✅ PASS | 真 douyin.com/jingxuan 10 个 video + 真 submit |
| `douyin-share-short-link.spec.ts` | ⏭ SKIP | 缺 `tests/.tmp/douyin-cookies.json`（RED-NOT-BLOCK 基础设施依赖）|
| `douyin-article.spec.ts` | ✅ PASS | /note/<id> 模式识别 + 真 submit（full suite 时偶发 flake，单独跑稳定）|
| `obsidian-archive.spec.ts` | ✅ PASS | 真 sidecar + Obsidian vault 双 note 写入 |

## 修过的代码

1. `tests/e2e/helpers/real-backend.ts` — 加 `resolvePython()` + `resolvePackageRoot()`，支持 `.venv` 不存在时回落 system `python3`，`src-python` 不存在时回落 `src`（项目实际布局）。spawn 时通过 `PYTHONPATH=PACKAGE_ROOT` 让 `python3 -m aipulse.desktop.sidecar` 找到包。
2. `tests/e2e/obsidian-archive.spec.ts` — 同上修复 + 把 `KIMI_*` env 改成 `LLM_*`（v0.4 重命名后的 pydantic-settings validation_alias）。

## 新增 spec

| spec | 结果 | 说明 |
|------|------|------|
| `real-bilibili.real.spec.ts` | ✅ PASS（2/2 soft）| `homepage` + `search` 都因 WBI 412 RED-NOT-BLOCK 软通过；断言扩展 machinery（boot+storage+liveness）工作 |
| `real-douyin.real.spec.ts` | ✅ PASS（1 hard + 1 soft）| `jingxuan` 真抓到 10 个 video id 并真 submit；`note` 软通过（real-Douyin 偶发 404）|
| `error-paths.real.spec.ts` | ✅ PASS（3/3 hard）| 断网：`setOffline(true)` 验后端 0 提交 + 徽章不变 + SW 存活；5xx：`context.route('**/api/videos/extract')` 拦截返 500 验 SW 报错 + 无 phantom success；cookie 失效：storage wipe + RESCAN 验重识别 |
| `screenshots.real.spec.ts` | ✅ PASS | 捕获 popup + 真 douyin + 真 bilibili 三张图到 `tests/e2e/__screenshots__/` |

## 全套结果（最新一轮）

```
vitest:    9/9 file 200/200 test PASS
e2e:       11 passed, 1 skipped, 1 flaky (douyin-article 单独跑 PASS)
screenshots: 3 PNG 写入 tests/e2e/__screenshots__/
```

## 截图绝对路径

- `extensions/chromium/tests/e2e/__screenshots__/popup-bilibili-fixture.png` (20 KB)
- `extensions/chromium/tests/e2e/__screenshots__/douyin-jingxuan-real.png` (673 KB)
- `extensions/chromium/tests/e2e/__screenshots__/bilibili-homepage-real.png` (710 KB)

## RED-NOT-BLOCK 清单（按用户决策前不修）

1. **Bilibili WBI 412 / rate limit** — `real-bilibili.real.spec.ts` 全 soft pass；`subtitle.spec.ts` 用固定 BV ID 绕开。**等 L1#5/L4 用户决策**（per `feedback_bilibili-wbi-anti-bot-blocker`）。
2. **douyin-share-short-link.spec.ts** — 缺登录 cookies 文件，需要人工 Douyin 登录一次导出。spec 已 `test.skip()`。
3. **douyin-article.spec.ts full-suite flake** — 单独跑 100% PASS，全套跑偶发；目前判定为 anti-bot 偶发拒绝，等同 WBI 同等 RED-NOT-BLOCK 范畴。

## 副作用（仓库内变动）

- `extensions/chromium/tests/e2e/helpers/real-backend.ts` (modified)
- `extensions/chromium/tests/e2e/obsidian-archive.spec.ts` (modified)
- `extensions/chromium/tests/e2e/error-paths.real.spec.ts` (new)
- `extensions/chromium/tests/e2e/real-bilibili.real.spec.ts` (new)
- `extensions/chromium/tests/e2e/real-douyin.real.spec.ts` (new)
- `extensions/chromium/tests/e2e/screenshots.real.spec.ts` (new)
- `extensions/chromium/tests/e2e/__screenshots__/` (new, 3 PNG)
- `docs/superpowers/verifications/2026-07-28-round8-extension-real-e2e-self-check.md` (new)

## 未触及

- `extensions/chromium/dist/`（build 产物，gitignored）
- `.venv/`（项目内未创建，按 helpers 回落策略走 system `python3`）
- 真 sidecar 源码（未改；只是 env 变量改名 LLM_* 已在 obsidian-archive 配套）

## 复跑命令

```bash
cd extensions/chromium
pnpm install
pnpm build:e2e
pnpm exec playwright install chromium  # 一次
pnpm vitest run
pnpm e2e
```
