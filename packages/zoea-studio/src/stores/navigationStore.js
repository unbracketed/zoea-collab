/**
 * Navigation Store
 *
 * Manages navigation state including sidebar collapse state.
 * Uses Zustand persist middleware to save state to localStorage.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useNavigationStore = create(
  persist(
    (set) => ({
      // State
      isSidebarCollapsed: false,

      // Actions
      toggleSidebar: () =>
        set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),

      collapseSidebar: () => set({ isSidebarCollapsed: true }),

      expandSidebar: () => set({ isSidebarCollapsed: false }),
    }),
    {
      name: 'sidebarCollapsed', // localStorage key (matches existing key)
    }
  )
);
