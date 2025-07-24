
// tests/global-setup.js
async function globalSetup(config) {
  console.log('🚀 Starting global setup for Playwright tests...');
  
  // Any global setup logic can go here
  // For example, seeding test data, setting up test databases, etc.
  
  console.log('✅ Global setup completed');
}

module.exports = globalSetup;