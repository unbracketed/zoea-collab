/**
 * Document Store
 *
 * Manages document state including current document ID and recent documents.
 * Uses persist middleware to save currentDocumentId to localStorage.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

export const useDocumentStore = create(
  persist(
    (set, get) => ({
      // State
      currentDocumentId: null, // Active document ID
      currentDocument: null,
      loading: false,
      error: null,

      // Recent documents state
      recentDocuments: [],
      recentDocumentsLoading: false,
      recentDocumentsError: null,
      recentDocumentsProjectId: null, // Track which project's documents are loaded

      // Actions

      /**
       * Set the current document ID
       * This persists the selected document across navigation
       */
      setCurrentDocumentId: (documentId) => {
        set({ currentDocumentId: documentId });
      },

      /**
       * Clear the current document ID
       * Called when navigating back to document list
       */
      clearCurrentDocumentId: () => {
        set({ currentDocumentId: null, currentDocument: null });
      },

      loadDocument: async (documentId, force = false) => {
        if (!documentId) {
          set({ currentDocument: null });
          return;
        }

        // Avoid refetching the same document if it is already loaded (unless forced)
        if (!force && get().currentDocument?.id === documentId && !get().error) {
          return;
        }

        set({ loading: true, error: null, currentDocumentId: documentId });
        try {
          const data = await api.fetchDocument(documentId, { include_preview: true });
          set({ currentDocument: data, loading: false });
        } catch (err) {
          console.error('Failed to load document', err);
          set({ error: err.message || 'Failed to load document', loading: false });
        }
      },

      /**
       * Load recent documents for a project
       * Fetches documents sorted by updated_at descending
       */
      loadRecentDocuments: async (projectId) => {
        if (!projectId) {
          set({ recentDocuments: [], recentDocumentsProjectId: null });
          return;
        }

        // Avoid refetching if already loaded for this project
        if (get().recentDocumentsProjectId === projectId && get().recentDocuments.length > 0) {
          return;
        }

        set({ recentDocumentsLoading: true, recentDocumentsError: null });
        try {
          const data = await api.fetchDocuments({
            project_id: projectId,
            page_size: 10,
            include_previews: false,
          });
          set({
            recentDocuments: data.items || [],
            recentDocumentsLoading: false,
            recentDocumentsProjectId: projectId,
          });
        } catch (err) {
          console.error('Failed to load recent documents', err);
          set({
            recentDocumentsError: err.message || 'Failed to load recent documents',
            recentDocumentsLoading: false,
          });
        }
      },

      /**
       * Force refresh recent documents for current project
       */
      refreshRecentDocuments: async () => {
        const projectId = get().recentDocumentsProjectId;
        if (!projectId) return;

        set({ recentDocumentsLoading: true, recentDocumentsError: null });
        try {
          const data = await api.fetchDocuments({
            project_id: projectId,
            page_size: 10,
            include_previews: false,
          });
          set({
            recentDocuments: data.items || [],
            recentDocumentsLoading: false,
          });
        } catch (err) {
          console.error('Failed to refresh recent documents', err);
          set({
            recentDocumentsError: err.message || 'Failed to refresh recent documents',
            recentDocumentsLoading: false,
          });
        }
      },
    }),
    {
      name: 'zoea-document', // localStorage key
      partialize: (state) => ({
        // Only persist currentDocumentId
        currentDocumentId: state.currentDocumentId,
      }),
    }
  )
);
