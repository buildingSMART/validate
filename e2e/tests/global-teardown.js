// tests/global-teardown.js
async function globalTeardown(config) {
  console.log('🧹 Starting global teardown...');
  
  // Any cleanup logic can go here
  // For example, cleaning up test data, closing database connections, etc.
  
  console.log('✅ Global teardown completed');
}

module.exports = globalTeardown;