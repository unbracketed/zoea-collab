/**
 * Session Tracker Hook
 *
 * Tracks navigation and project/workspace changes to persist session state.
 * Also handles restoring the last session on app load.
 *
 * Works with LayoutFrame's initializeFromUrl - this hook handles:
 * - Tracking state changes to localStorage
 * - Restoring navigation path on default landing
 * - LayoutFrame handles URL param initialization
 */

import { useEffect, useRef } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useSessionStore, useWorkspaceStore } from '../stores';

/**
 * Hook to track session state and save to localStorage.
 * Should be used in a component that wraps the entire app (after router setup).
 */
export function useSessionTracker() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const saveSession = useSessionStore((state) => state.saveSession);
  const getSession = useSessionStore((state) => state.getSession);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const initializeFromUrl = useWorkspaceStore((state) => state.initializeFromUrl);

  const hasRestoredSession = useRef(false);
  const initialPath = useRef(location.pathname + location.search);

  // Restore session on initial load
  useEffect(() => {
    if (hasRestoredSession.current) return;
    hasRestoredSession.current = true;

    const restoreSession = async () => {
      const session = getSession();

      // Check if URL has project/workspace params
      const hasUrlParams = searchParams.has('project') || searchParams.has('workspace');

      // Only restore if we're at the root or dashboard (default landing page)
      // and there are no URL params taking precedence
      const isDefaultLanding = initialPath.current === '/' || initialPath.current === '/dashboard';

      if (!isDefaultLanding || hasUrlParams) {
        // User navigated directly to a URL with params, let LayoutFrame handle it
        // But if no URL params, still restore project/workspace from session
        if (!hasUrlParams && session.lastProjectId) {
          await initializeFromUrl(session.lastProjectId, session.lastWorkspaceId);
        }
        return;
      }

      // First-time user detection: no saved path and no saved project
      // Send them to the home page for onboarding
      const isFirstTimeUser = !session.lastPath && !session.lastProjectId;
      if (isFirstTimeUser) {
        navigate('/home', { replace: true });
        return;
      }

      // Restore full session - we're at default landing with no URL params
      if (session.lastProjectId) {
        await initializeFromUrl(session.lastProjectId, session.lastWorkspaceId);
      }

      // Navigate to last path if available and not a default page
      if (session.lastPath && session.lastPath !== '/' && session.lastPath !== '/dashboard') {
        navigate(session.lastPath, { replace: true });
      }
    };

    restoreSession();
  }, []);

  // Track path changes
  useEffect(() => {
    const fullPath = location.pathname + location.search;
    saveSession({ path: fullPath });
  }, [location.pathname, location.search, saveSession]);

  // Track project changes
  useEffect(() => {
    if (currentProjectId) {
      saveSession({ projectId: currentProjectId });
    }
  }, [currentProjectId, saveSession]);

  // Track workspace changes
  useEffect(() => {
    if (currentWorkspaceId) {
      saveSession({ workspaceId: currentWorkspaceId });
    }
  }, [currentWorkspaceId, saveSession]);
}

export default useSessionTracker;
