import { chromium } from '@playwright/test';

async function globalSetup(config) {
  console.log('🚀 Starting global setup...');

  // Warm up the frontend by loading it in a real browser
  // This triggers JS bundle compilation on the dev server
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 60_000 });
    console.log('✅ Frontend warmed up');
  } catch (e) {
    console.warn('⚠️ Frontend warmup timed out:', e.message);
  }
  await browser.close();

  console.log('✅ Global setup completed');
}

export default globalSetup;