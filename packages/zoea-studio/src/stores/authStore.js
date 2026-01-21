/**
 * Auth Store
 *
 * Manages authentication state and methods.
 * Handles login, logout, and auth checking with async operations.
 */

import { create } from 'zustand';
import api from '../services/api';
import { useSessionStore } from './sessionStore';
import { useWorkspaceStore } from './workspaceStore';

export const useAuthStore = create((set, get) => ({
  // State
  isAuthenticated: false,
  user: null,
  organization: null,
  loading: true, // Start true for initial auth check
  error: null,

  // Actions

  /**
   * Check if user is authenticated
   * Called by AuthGuard on mount
   */
  checkAuth: async () => {
    try {
      set({ loading: true, error: null });
      const result = await api.checkAuth();

      if (result.authenticated) {
        set({
          isAuthenticated: true,
          user: {
            username: result.username,
            organization: result.organization ? { name: result.organization } : null,
          },
          organization: result.organization ? { name: result.organization } : null,
          error: null,
        });
      } else {
        set({
          isAuthenticated: false,
          user: null,
          organization: null,
          error: null,
        });
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      set({
        isAuthenticated: false,
        user: null,
        organization: null,
        error: err.message,
      });
    } finally {
      set({ loading: false });
    }
  },

  /**
   * Login user
   */
  login: async (username, password) => {
    try {
      set({ loading: true, error: null });

      const result = await api.login(username, password);

      // After successful login, fetch full user info including organization
      await get().checkAuth();

      return { success: true };
    } catch (err) {
      console.error('Login failed:', err);
      set({ error: err.message });
      return { success: false, error: err.message };
    } finally {
      set({ loading: false });
    }
  },

  /**
   * Logout user
   */
  logout: async () => {
    try {
      set({ loading: true });
      await api.logout();
    } catch (err) {
      console.error('Logout failed:', err);
      // Continue with logout even if API call fails
    } finally {
      // Clear session and workspace state
      useSessionStore.getState().clearSession();
      useWorkspaceStore.getState().reset();

      set({
        isAuthenticated: false,
        user: null,
        organization: null,
        error: null,
        loading: false,
      });
    }
  },

  /**
   * Clear error state
   */
  clearError: () => set({ error: null }),

  /**
   * Direct setters (if needed for advanced use cases)
   */
  setUser: (user) => set({ user }),
  setOrganization: (organization) => set({ organization }),
}));
