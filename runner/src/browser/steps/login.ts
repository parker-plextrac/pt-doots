// Confirmed selectors (empirically verified against local stack):
//
// Form wrapper:  [data-testid="login-form"]  (name="login-form")
// Username:      input[name="username"]      (type="email")
// Password div:  [data-testid="password-field"]  (hidden with class "display-none" until step 1 submit)
// Password:      input[name="password"]
// Submit button: button[type="submit"]
//
// Login is two-step:
//  1. Fill username → submit → wait for password-field to lose display-none
//  2. Fill password → submit → wait for URL to leave /login
import type { Page } from "playwright";
import type { HarnessConfig } from "../../config.ts";

export async function performLogin(page: Page, cfg: HarnessConfig): Promise<void> {
  await page.goto(`${cfg.appUrl}/login`);
  await page.waitForLoadState("networkidle");

  // Step 1: username
  await page.fill('input[name="username"]', cfg.username);
  await page.click('button[type="submit"]');

  // Step 2: wait for password field to become visible, then fill it
  await page.waitForSelector('[data-testid="password-field"]:not(.display-none)', {
    timeout: 10_000,
  });
  await page.fill('input[name="password"]', cfg.password);
  await page.click('button[type="submit"]');

  // Confirm login by waiting for navigation away from /login
  await page.waitForURL((url) => !url.href.includes("/login"), { timeout: 15_000 });
}
