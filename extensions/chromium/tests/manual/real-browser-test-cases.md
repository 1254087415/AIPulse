# AIPulse Clipper 真实浏览器测试用例

> 目标：在真实 Chromium/Chrome 中验证扩展的链接提取、popup 交互、右键菜单、提交链路等行为。
> 执行方式：可以人工按步骤操作，也可以用 Playwright 自动化执行。

## 一、测试环境

| 项目 | 要求 |
|------|------|
| 浏览器 | Chrome / Edge / Chromium 最新稳定版 |
| 扩展目录 | `extensions/chromium/dist` |
| 前置命令 | `cd extensions/chromium && pnpm install && pnpm build:e2e`（自动化需 `build:e2e`，否则提交桥被剥离） |
| 后端（可选） | 如需测试真实提交，启动 AIPulse 桌面应用或 mock 服务器 |
| Native Messaging（可选） | 如需测试 Native Messaging，需安装 host manifest 并指向 Tauri 二进制 |

## 二、加载扩展

1. 打开浏览器，访问 `chrome://extensions/`。
2. 打开右上角「开发者模式」。
3. 点击「加载已解压的扩展程序」。
4. 选择 `extensions/chromium/dist` 目录。
5. **预期结果**：扩展列表出现「AIPulse Clipper」，图标显示在工具栏；无红色错误提示。

## 三、测试用例

### TC-01：Bilibili 视频页链接识别

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开 `https://www.bilibili.com/video/BV1xx411c7mD` | 页面正常加载 |
| 2 | 观察工具栏扩展图标 | 图标上出现 badge 数字（≥1），背景为蓝色 |
| 3 | 点击扩展图标打开 popup | popup 下拉框中显示 Bilibili 视频链接 |
| 4 | 下拉框选择该 Bilibili 链接 | 「归档到 AIPulse」按钮变为可点击 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-02：抖音首页视频卡片链接识别

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开抖音首页 `https://www.douyin.com/?recommend=1` | 页面正常加载，显示视频卡片网格 |
| 2 | 观察工具栏扩展图标 | 图标上出现 badge 数字（≥1），背景为蓝色 |
| 3 | 点击扩展图标打开 popup | popup 下拉框中显示 `https://www.douyin.com/video/<数字ID>` 链接 |
| 4 | 点击任意视频进入播放页 | 扩展仍保持识别状态 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-03：小红书笔记页链接识别

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开小红书笔记页 `https://www.xiaohongshu.com/explore/648292ea0000000027010e16?xsec_token=ABCgU1igjCRN41giTWs0p9l4tQonPeOu3JbsaY0R5YI04=&xsec_source=pc_feed` | 页面正常加载 |
| 2 | 观察扩展图标 | badge 数字 ≥1 |
| 3 | 点击扩展图标 | popup 中显示小红书笔记链接 |
| 4 | 打开分享链接 `https://www.xiaohongshu.com/discovery/item/647b0af200000000130034f9?source=webshare&xhsshare=pc_web&xsec_token=AB7jFDPm0WHbt0yO1kX3hJmQbrgt7FmiyboUUVNjKO2Ec=&xsec_source=pc_share` | 扩展仍能识别 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-04：微信公众号文章链接识别

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开 `https://mp.weixin.qq.com/s/abcdef` | 页面正常加载 |
| 2 | 观察扩展图标 | badge 数字 ≥1 |
| 3 | 点击扩展图标 | popup 中显示微信公众号文章链接 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-05：Popup 提交当前页面（HTTP fallback）

**前置条件**：未启动 AIPulse 桌面应用，或已配置 `chrome.storage.local` 的 `httpBaseUrl` 指向 mock 服务器。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在任意支持页面点击扩展图标 | popup 打开，下拉框默认选中「当前页面」 |
| 2 | 点击「归档到 AIPulse」 | 状态文字变为「提交中...」 |
| 3 | 等待 1-2 秒 | 状态文字变为「已提交: <task_id>」或显示失败原因 |
| 4 | 检查 mock 服务器日志 | 收到 `POST /api/videos/extract`，body 中 `source=browser_extension`、`mode=archive` |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-06：Popup 提交识别到的链接并触发知识缺口分析

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在 Bilibili 视频页点击扩展图标 | popup 显示多个链接选项 |
| 2 | 下拉框选择 Bilibili 视频链接 | 选中项更新 |
| 3 | 点击「归档并分析知识缺口」 | 状态显示提交成功，mock 服务器收到 `mode=knowledge_check` |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-07：右键菜单「归档当前页面」

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在 Bilibili 视频页空白处右键 | 上下文菜单出现「归档当前页面到 AIPulse」 |
| 2 | 点击该菜单项 | 扩展尝试提交当前页面 URL；如后端/mock 可达，服务器收到请求 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-08：右键菜单「归档此链接」

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在页面内右键点击一个超链接 | 上下文菜单出现「归档此链接到 AIPulse」 |
| 2 | 点击该菜单项 | 扩展提交该链接 URL |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-09：无链接页面不显示 badge

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开 `https://example.com` 或 `about:blank` | 页面加载 |
| 2 | 观察扩展图标 | 无 badge 数字（或为空） |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-10：Native Messaging 提交（需安装 host manifest）

**前置条件**：已安装 native host manifest，指向 Tauri 二进制 `--native-messaging`。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 启动 AIPulse 桌面应用（native host 已注册） | 应用正常运行 |
| 2 | 在支持页面点击扩展图标并提交 | 状态显示「已提交」 |
| 3 | 检查 Tauri/Python sidecar 日志 | 收到来自扩展的 `SUBMIT_URL` 请求 |
| 4 | 关闭 AIPulse 应用，再次提交 | 自动 fallback 到 HTTP，状态仍为「已提交」 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-11：无效 URL 拒绝

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 通过测试桥或开发者工具向 background 发送 `SUBMIT_URL` | 发送 `url: "javascript:alert(1)"` |
| 2 | 观察响应 | background 返回 `{ ok: false, error: "invalid message" }`，未发起网络请求 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

### TC-12：SPA 页面动态导航后重新识别

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 打开 Bilibili 首页 | 扩展图标无视频链接 badge |
| 2 | 点击一个视频进入播放页（不刷新整页） | 约 500ms 后 badge 出现 |
| 3 | 点击后退回到首页 | badge 消失或更新 |

**状态：** ☐ 通过 ☐ 失败 ☐ 阻塞

## 四、缺陷记录模板

| 字段 | 内容 |
|------|------|
| 用例 ID | TC-XX |
| 浏览器版本 | |
| 复现步骤 | |
| 实际结果 | |
| 预期结果 | |
| 截图 | |
| 严重程度 | 阻塞 / 高 / 中 / 低 |

## 五、自动化执行

上述用例中 TC-01 ~ TC-06、TC-09、TC-11 已可通过 Playwright 自动执行。命令：

```bash
cd extensions/chromium
pnpm build:e2e
pnpm e2e
```

TC-07、TC-08（右键菜单）和 TC-10（Native Messaging）因浏览器权限/系统级安装要求，目前建议人工执行或在受控 CI 环境中额外配置后自动化。
