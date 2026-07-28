# spec09 残留修复 01：UID 正则字符集

日期：2026-07-27
角色：worker 自检（最终结论由独立 verifier 给出）

## 修复范围

- `AddFollowForm` 的裸 UID 与 Bilibili space URL 捕获字符集从 `[0-9a-z]` 放宽为 `[0-9a-z_-]`。
- 保持最小改动，不改变表单提交结构或后端接口。

## RED 证据

命令：

```bash
pnpm --dir frontend test:unit -- tests/unit/add-follow-form-url.test.ts
```

新增用例：

```text
AddFollowForm (URL input) > submits a bilibili uid containing an underscore without truncation
```

修复前失败片段：

```text
Expected uid: "123_456"
Received uid: "123"
Test Files  1 failed | 22 passed
Tests       1 failed | 170 passed
```

## GREEN 证据

同一命令在最小实现后通过：

```text
Test Files  23 passed (23)
Tests       171 passed (171)
```

## 真实后端 POST

请求发送到当前主 checkout 的真实 AIPulse 后端 `127.0.0.1:8000`，没有 mock、fixture 或数据替换：

```json
{
  "platform": "bilibili",
  "uid": "123_456",
  "profile_url": "https://space.bilibili.com/123_456"
}
```

响应：

```text
HTTP 201
uid: 123_456
profile_url: https://space.bilibili.com/123_456
```

## 真浏览器完整路径

使用 `mcp__playwright` 打开：

```text
http://127.0.0.1:5173/dashboard?tab=follow-list
```

默认 Vite proxy 指向需要 Bearer 的 18000 实例。为避免读取或修改任何 secret，Playwright 仅把页面的 `/api/*` 请求转发到同一主 checkout 中已运行的真实、无鉴权 AIPulse 8000 实例；没有伪造响应或业务数据。

步骤：

1. 打开 dashboard 的「关注列表」。
2. 点击「添加 UP 主」。
3. 输入 `https://space.bilibili.com/123_456_ui01`。
4. 点击「添加」。
5. 页面出现 `uid: 123_456_ui01`。

精确值 `123_456` 已先通过真实 POST 入库，因此浏览器再次提交时真实后端返回预期的 409 重复冲突；页面列表仍展示完整 `uid: 123_456`。

截图：`docs/superpowers/verifications/2026-07-27-spec09-redfix-residual-01.png`

## DB 直查

只追加测试行，未 reset、DELETE 或改写既有数据：

```text
123_456|123_456|https://space.bilibili.com/123_456|2026-07-27 14:57:38.858118
123_456_ui01|123_456_ui01|https://space.bilibili.com/123_456_ui01|2026-07-27 15:03:29.283086
```

## 代码审查处理

独立 `code-reviewer` 未发现 CRITICAL。其两项 HIGH 建议将 URL 捕获重新收紧为纯数字并改测裸 UID，但这会直接破坏本轮明确验收输入 `space.bilibili.com/123_456`，且与当前已支持 hex-style 测试 UID 的产品约束冲突；后端 UID schema 也允许该字符集，因此不采纳。其余 host 锚定、query 边界建议属于本次字符集放宽前已存在的解析器范围问题，不在本轮最小残留修复中扩展。

## 自检边界

- 未修改 `.env`、`data/settings.json` 或任何 secret。
- 未 reset 真实 DB。
- 未使用 mock 后端。
- 只扩大 UID 字符集，不接受字符集之外的路径字符。
