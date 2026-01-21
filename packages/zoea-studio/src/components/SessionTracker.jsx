/**
 * Session Tracker Component
 *
 * Wraps authenticated content to track and restore session state.
 * Persists the current project, workspace, and route to localStorage.
 */

import { useSessionTracker } from '../hooks/useSessionTracker';

function SessionTracker({ children }) {
  // Track session changes and handle restoration
  useSessionTracker();

  return children;
}

export default SessionTracker;
