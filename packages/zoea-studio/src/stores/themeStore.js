/**
 * Theme Store
 *
 * Manages the color theme and mode (light/dark) settings.
 * Persists to localStorage.
 * Supports system default theme from backend settings.
 *
 * Uses shadcn.io OKLCH-based theme system with:
 * - data-theme attribute for color themes
 * - .dark class for dark mode (compatible with shadcn/Tailwind)
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

export const THEMES = [
  { id: 'amber-minimal', name: 'Amber Minimal', description: 'Warm amber tones' },
  { id: 'claude', name: 'Claude', description: 'Anthropic-inspired' },
  { id: 'corporate', name: 'Corporate', description: 'Professional blue' },
  { id: 'modern-minimal', name: 'Modern', description: 'Clean contemporary' },
  { id: 'nature', name: 'Nature', description: 'Earthy greens' },
  { id: 'slack', name: 'Slack', description: 'Familiar purple' },
  { id: 'twitter', name: 'Twitter', description: 'Sky blue' },
  { id: 'cyberpunk', name: 'Cyberpunk', description: 'Neon vibes' },
  { id: 'red', name: 'Red', description: 'Bold crimson' },
  { id: 'summer', name: 'Summer', description: 'Bright and warm' },
  { id: 'notebook', name: 'Notebook', description: 'Paper-like' },
];

export const MODES = [
  { id: 'light', name: 'Light' },
  { id: 'dark', name: 'Dark' },
  { id: 'auto', name: 'System' },
];

// Map old theme IDs to new ones for localStorage migration
const THEME_MIGRATION_MAP = {
  slate: 'corporate',
  aubergine: 'slack',
  ocean: 'twitter',
  forest: 'nature',
  copper: 'amber-minimal',
  midnight: 'cyberpunk',
  sunrise: 'summer',
};

const migrateTheme = (theme) => {
  return THEME_MIGRATION_MAP[theme] || theme;
};

const getPreferredMode = () => {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const applyTheme = (theme) => {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
};

const applyMode = (mode) => {
  if (typeof document === 'undefined') return;
  const resolvedMode = mode === 'auto' ? getPreferredMode() : mode;
  // Toggle .dark class for shadcn/Tailwind dark mode
  if (resolvedMode === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
};

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'claude', // User's preferred theme (persisted)
      mode: 'auto', // 'light', 'dark', or 'auto'
      systemDefaultTheme: 'claude', // Loaded from backend settings
      activeProjectTheme: null, // Current project's theme (overrides user preference)

      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },

      setMode: (mode) => {
        applyMode(mode);
        set({ mode });
      },

      // Set the active project's theme (used when switching projects)
      setActiveProjectTheme: (projectTheme) => {
        set({ activeProjectTheme: projectTheme });
        // Apply project theme, or fall back to system default
        const effectiveTheme = projectTheme || get().systemDefaultTheme;
        applyTheme(effectiveTheme);
      },

      // Get the effective theme (project > system default)
      getEffectiveTheme: () => {
        const { activeProjectTheme, systemDefaultTheme } = get();
        return activeProjectTheme || systemDefaultTheme;
      },

      // Fetch system settings from backend
      fetchSystemDefaults: async () => {
        try {
          const settings = await api.fetchSystemSettings();
          // Migrate old theme IDs from backend
          const defaultTheme = migrateTheme(settings.default_theme) || 'claude';
          set({ systemDefaultTheme: defaultTheme });
          // If no project theme is set, apply the system default
          if (!get().activeProjectTheme) {
            applyTheme(defaultTheme);
          }
        } catch (error) {
          console.warn('Failed to fetch system settings, using defaults:', error);
        }
      },

      // Call on app init to apply persisted settings
      initialize: async () => {
        const { mode } = get();
        applyMode(mode);

        // Fetch system defaults from backend
        await get().fetchSystemDefaults();

        // Listen for system preference changes when mode is 'auto'
        if (typeof window !== 'undefined') {
          const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
          mediaQuery.addEventListener('change', () => {
            if (get().mode === 'auto') {
              applyMode('auto');
            }
          });
        }
      },

      getResolvedMode: () => {
        const mode = get().mode;
        return mode === 'auto' ? getPreferredMode() : mode;
      },
    }),
    {
      name: 'zoea-theme',
      partialize: (state) => ({
        theme: state.theme,
        mode: state.mode,
      }),
      onRehydrateStorage: () => (state) => {
        // Apply theme/mode after rehydration, with migration
        if (state) {
          // Migrate old theme IDs from localStorage
          const migratedTheme = migrateTheme(state.theme);
          if (migratedTheme !== state.theme) {
            state.theme = migratedTheme;
          }
          applyTheme(state.theme);
          applyMode(state.mode);
        }
      },
    }
  )
);
