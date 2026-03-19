async function globalSetup(config) {
  console.log('🚀 Starting global setup for Playwright tests...');

  // Warm up the frontend dev server — it may still be compiling after the health check passes
  const baseURL = 'http://localhost:3000';
  const maxRetries = 30;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(baseURL);
      const body = await res.text();
      if (body.includes('<div id="root">') || body.includes('bundle.js') || res.ok) {
        console.log(`✅ Frontend ready after ${i + 1} attempt(s)`);
        break;
      }
    } catch {
      // server not ready yet
    }
    await new Promise(r => setTimeout(r, 2000));
  }

  console.log('✅ Global setup completed');
}

export default globalSetup;