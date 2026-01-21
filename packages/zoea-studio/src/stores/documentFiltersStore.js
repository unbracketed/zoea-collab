/**
 * Document Filters Store
 *
 * Manages filter state for the Documents view.
 * Filters are ephemeral (not persisted).
 */

import { create } from 'zustand'

export const useDocumentFiltersStore = create((set, get) => ({
  // Filter state
  typeFilter: null, // 'Image', 'Markdown', 'YooptaDocument', 'D2Diagram', 'MermaidDiagram', 'ExcalidrawDiagram'
  ownerFilter: null, // 'me' or null
  modifiedFilter: null, // 'today', 'week', 'month', 'year'
  sourceFilter: null, // future use

  // Actions
  setTypeFilter: (type) => set({ typeFilter: type }),
  setOwnerFilter: (owner) => set({ ownerFilter: owner }),
  setModifiedFilter: (modified) => set({ modifiedFilter: modified }),
  setSourceFilter: (source) => set({ sourceFilter: source }),

  clearAllFilters: () =>
    set({
      typeFilter: null,
      ownerFilter: null,
      modifiedFilter: null,
      sourceFilter: null,
    }),

  // Check if any filters are active
  hasActiveFilters: () => {
    const { typeFilter, ownerFilter, modifiedFilter, sourceFilter } = get()
    return !!(typeFilter || ownerFilter || modifiedFilter || sourceFilter)
  },

  // Get modified date cutoff based on filter value
  getModifiedCutoff: () => {
    const { modifiedFilter } = get()
    if (!modifiedFilter) return null

    const now = new Date()
    switch (modifiedFilter) {
      case 'today':
        return new Date(now.getFullYear(), now.getMonth(), now.getDate())
      case 'week':
        return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      case 'month':
        return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      case 'year':
        return new Date(now.getFullYear(), 0, 1)
      default:
        return null
    }
  },
}))
