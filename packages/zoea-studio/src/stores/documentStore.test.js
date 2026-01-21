import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useDocumentStore } from './documentStore'
import api from '../services/api'

vi.mock('../services/api', () => ({
  __esModule: true,
  default: {
    fetchDocument: vi.fn(),
  },
}))

describe('documentStore', () => {
  beforeEach(() => {
    const { clearCurrentDocumentId, setCurrentDocumentId } = useDocumentStore.getState()
    clearCurrentDocumentId()
    setCurrentDocumentId(null)
    useDocumentStore.setState({ currentDocument: null, loading: false, error: null })
  })

  it('loads document and caches currentDocument', async () => {
    api.fetchDocument.mockResolvedValueOnce({ id: 1, name: 'Doc', content: 'Hello' })
    await act(async () => {
      await useDocumentStore.getState().loadDocument(1)
    })
    const state = useDocumentStore.getState()
    expect(state.currentDocument?.id).toBe(1)
    expect(state.loading).toBe(false)
  })

  it('sets error on load failure', async () => {
    api.fetchDocument.mockRejectedValueOnce(new Error('boom'))
    await act(async () => {
      await useDocumentStore.getState().loadDocument(2)
    })
    const state = useDocumentStore.getState()
    expect(state.error).toBe('boom')
    expect(state.loading).toBe(false)
  })

  it('skips fetch if same document already loaded', async () => {
    api.fetchDocument.mockResolvedValue({ id: 3, name: 'Doc3' })
    await act(async () => {
      await useDocumentStore.getState().loadDocument(3)
    })
    api.fetchDocument.mockClear()
    await act(async () => {
      await useDocumentStore.getState().loadDocument(3)
    })
    expect(api.fetchDocument).not.toHaveBeenCalled()
  })
})
