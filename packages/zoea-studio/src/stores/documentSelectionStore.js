/**
 * Document Selection Store
 *
 * Manages document selection state for multi-select functionality.
 * Selection is ephemeral and scoped to the current folder context.
 */

import { create } from 'zustand'

export const useDocumentSelectionStore = create((set, get) => ({
  // State
  selectedDocumentIds: new Set(),
  lastSelectedIndex: null,
  folderId: null,

  /**
   * Select a single document (replaces existing selection)
   */
  selectDocument: (documentId, index) => {
    set({
      selectedDocumentIds: new Set([documentId]),
      lastSelectedIndex: index,
    })
  },

  /**
   * Toggle document selection (Cmd/Ctrl+Click)
   */
  toggleDocumentSelection: (documentId, index) => {
    const { selectedDocumentIds } = get()
    const newSet = new Set(selectedDocumentIds)

    if (newSet.has(documentId)) {
      newSet.delete(documentId)
    } else {
      newSet.add(documentId)
    }

    set({
      selectedDocumentIds: newSet,
      lastSelectedIndex: newSet.has(documentId) ? index : get().lastSelectedIndex,
    })
  },

  /**
   * Extend selection with range (Shift+Click)
   * Selects all documents between lastSelectedIndex and current index
   */
  extendSelectionRange: (documentIds, currentIndex) => {
    const { selectedDocumentIds, lastSelectedIndex } = get()

    if (lastSelectedIndex === null) {
      // No previous selection, just select the clicked item
      set({
        selectedDocumentIds: new Set([documentIds[currentIndex]]),
        lastSelectedIndex: currentIndex,
      })
      return
    }

    const start = Math.min(lastSelectedIndex, currentIndex)
    const end = Math.max(lastSelectedIndex, currentIndex)
    const rangeIds = documentIds.slice(start, end + 1)

    // Merge with existing selection
    const newSet = new Set([...selectedDocumentIds, ...rangeIds])

    set({
      selectedDocumentIds: newSet,
      lastSelectedIndex: currentIndex,
    })
  },

  /**
   * Clear all selections
   */
  clearSelection: () => {
    set({
      selectedDocumentIds: new Set(),
      lastSelectedIndex: null,
    })
  },

  /**
   * Set folder context and clear selection if folder changed
   */
  setFolderContext: (newFolderId) => {
    const { folderId } = get()
    if (folderId !== newFolderId) {
      set({
        selectedDocumentIds: new Set(),
        lastSelectedIndex: null,
        folderId: newFolderId,
      })
    }
  },

  /**
   * Check if a document is selected
   */
  isSelected: (documentId) => {
    return get().selectedDocumentIds.has(documentId)
  },

  /**
   * Get array of selected document IDs (for bulk operations)
   */
  getSelectedIds: () => {
    return Array.from(get().selectedDocumentIds)
  },

  /**
   * Get selection count
   */
  getSelectionCount: () => {
    return get().selectedDocumentIds.size
  },
}))
