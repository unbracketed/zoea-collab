/**
 * Auth Guard Component
 *
 * Protects routes by requiring authentication.
 * Shows loading spinner while checking auth, shows login if not authenticated.
 * Also tracks and restores session state (project, workspace, route).
 */

import { useEffect, useRef } from 'react';
import { useAuthStore } from '../stores';
import Login from './Login';
import SessionTracker from './SessionTracker';

function AuthGuard({ children }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const loading = useAuthStore((state) => state.loading);
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const hasCheckedAuth = useRef(false);

  // Call checkAuth only once on first mount
  useEffect(() => {
    if (!hasCheckedAuth.current) {
      hasCheckedAuth.current = true;
      checkAuth();
    }
  }, []); // Empty deps - only run once on mount

  // Show loading spinner while checking authentication
  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <svg className="animate-spin h-8 w-8 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="sr-only">Loading...</span>
      </div>
    );
  }

  // Show login if not authenticated
  if (!isAuthenticated) {
    return <Login />;
  }

  // Render protected content if authenticated
  // SessionTracker handles persisting and restoring session state
  return <SessionTracker>{children}</SessionTracker>;
}

export default AuthGuard;
