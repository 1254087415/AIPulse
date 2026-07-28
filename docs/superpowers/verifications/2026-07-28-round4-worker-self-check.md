# AIPulse v0.3 round 4 worker self-check

## UID resolution

- 跟李沐学AI：UID `1567748478`
  - Exa search resolved `https://space.bilibili.com/1567748478/`.
  - UAPI validation: `GET https://uapis.cn/api/v1/social/bilibili/archives?mid=1567748478&page=1&size=1` returned `total=188` and real videos.
- 罗翔说刑法：UID `517327498`
  - bili-cli video detail for `BV1WmgC6xEYw` returned owner `id=517327498`, name `罗翔说刑法`.
  - UAPI validation: `GET https://uapis.cn/api/v1/social/bilibili/archives?mid=517327498&page=1&size=1` returned `total=492` and real videos.

## Database cleanup

- Backup: `/Users/zab/Documents/project/AIPulse/data/aipulse.db.round3-backup`
- Removed every existing `followed_up` row whose UID was not `1567748478` or `517327498`, including:
  - `123_456_ui01`, `123_456`, `verify-with-token`, `abc123def456`, `verifier`,
    `redfix-final01`, `finalverify01`, `redfixabc01`, `abcdef12345`, `102`, `e2e-test-uid-001`, `102d224fbda7`.
- Added through real `POST http://127.0.0.1:8000/api/followed-up`:
  - 跟李沐学AI (`1567748478`)
  - 罗翔说刑法 (`517327498`)
- Final active rows: `2`.

## Real sync verification

- Playwright page: `http://127.0.0.1:5173/dashboard?tab=follow-list`
- Dashboard displayed exactly `2 个 UP 主`, with both requested names and numeric UIDs; no fixture names appeared.
- Clicked “立即同步” on both cards in the real page.
- The current frontend sync implementation calls `POST /api/followed-up/{id}/sync`; it does not open an `/api/sse` stream. Playwright network inspection found no `/api/sse` request, so there is no SSE `completed` event to claim.
- Direct real sync responses:
  - 罗翔说刑法: HTTP 202 response `status=timeout`, then health became `healthy` with no error.
  - 跟李沐学AI: HTTP 202 response `status=ok`, `new_videos=0` after the scheduled scan had already inserted the current videos.
- Final health endpoint checks for both accounts: `healthy`, `last_error=null`.
- Actual content table in this schema is `hotspots` (there is no `videos` table). Final count for active followed-up IDs: `52` hotspots.
  - 罗翔说刑法: `30`
  - 跟李沐学AI: `22`
- Screenshot: `docs/superpowers/verifications/2026-07-28-round4-dashboard-after-sync.png`

## Scope and side effects

- No `.env`, `.env.example`, or `data/settings.json` changes.
- No remote push.
- The only worktree artifacts are this self-check document and the required screenshot.
