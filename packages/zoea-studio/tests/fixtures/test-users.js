/**
 * Test User Credentials
 * 
 * Centralized test user data for E2E tests.
 */

export const testUsers = {
  default: {
    username: 'admin',
    password: 'admin',
    displayName: 'Admin',
  },
  
  // Add more test users as needed
  // testUser2: {
  //   username: 'test2',
  //   password: 'password2',
  //   displayName: 'Test User 2',
  // },
};

/**
 * Get default test user
 */
export function getDefaultUser() {
  return testUsers.default;
}
