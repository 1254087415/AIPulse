import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const USER_DATA_DIR = path.resolve(__dirname, '../../.tmp/user-data-douyin-share');
const COOKIE_FILE = path.resolve(__dirname, '../../.tmp/douyin-cookies.json');

async function main() {
  console.log('Launching Chromium with a fresh Douyin profile...');

  fs.rmSync(USER_DATA_DIR, { recursive: true, force: true });
  fs.mkdirSync(USER_DATA_DIR, { recursive: true });

  const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
    headless: false,
    args: ['--disable-blink-features=AutomationControlled', '--window-size=1280,720'],
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 720 },
  });

  const page = await context.newPage();
  page.on('console', (msg) => console.log('PAGE CONSOLE:', msg.text()));
  page.on('pageerror', (err) => console.log('PAGE ERROR:', err.message));

  await page.goto('https://www.douyin.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });

  console.log('\n========================================');
  console.log('请在新打开的 Chromium 窗口中登录抖音。');
  console.log('支持扫码登录、手机号/验证码登录。');
  console.log('登录成功后脚本会自动保存 Cookie 并退出。');
  console.log('如果不需要登录，请直接关闭浏览器。');
  console.log('========================================\n');

  // Wait for login by polling for auth cookies. Douyin sets sessionid /
  // sid_guard / login_uid after a successful login.
  const authCookieNames = ['sessionid', 'sid_guard', 'login_uid', 'sid_tt', 'uid_tt'];
  let loggedIn = false;
  const deadline = Date.now() + 600_000;
  while (Date.now() < deadline) {
    const cookies = await context.cookies();
    const hasAuth = cookies.some((c) => authCookieNames.includes(c.name));
    if (hasAuth) {
      loggedIn = true;
      console.log('Login detected via auth cookie:', authCookieNames.find((n) =>
        cookies.some((c) => c.name === n)
      ));
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  if (!loggedIn) {
    console.log('Timed out waiting for login auth cookies.');
    await context.close();
    process.exit(1);
  }

  await page.waitForTimeout(5000);

  const cookies = await context.cookies();
  fs.mkdirSync(path.dirname(COOKIE_FILE), { recursive: true });
  fs.writeFileSync(COOKIE_FILE, JSON.stringify(cookies, null, 2));
  console.log(`Saved ${cookies.length} cookies to ${COOKIE_FILE}`);

  await context.close();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
