import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
vi.mock('../components/ExcalidrawEditor', () => ({
  __esModule: true,
  default: () => null,
  getSceneData: vi.fn(),
}))

import DocumentDetailPage from './DocumentDetailPage'

const mockDocument = {
  id: 1,
  name: 'Example Image',
  description: 'An example image document',
  image_file: 'https://example.com/image.png',
  width: 800,
  height: 600,
  project_id: 1, // Must match currentProjectId in the store mock
}

vi.mock('../components/layout/LayoutFrame', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="layout-frame">{children}</div>,
}))

vi.mock('../stores', () => ({
  useDocumentStore: (selector) =>
    selector({
      currentDocument: mockDocument,
      currentDocumentId: mockDocument.id,
      loading: false,
      error: null,
      setCurrentDocumentId: vi.fn(),
      clearCurrentDocumentId: vi.fn(),
      loadDocument: vi.fn(),
    }),
  useThemeStore: (selector) =>
    selector({
      getResolvedMode: () => 'light',
    }),
  useFlowsStore: (selector) =>
    selector({
      runWorkflow: vi.fn(),
    }),
  useWorkspaceStore: (selector) =>
    selector({
      currentProjectId: 1,
      currentWorkspaceId: 1,
    }),
}))

describe('DocumentDetailPage', () => {
  it('renders image documents with dimensions', async () => {
    render(
      <MemoryRouter initialEntries={[`/documents/${mockDocument.id}`]}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        </Routes>
      </MemoryRouter>
    )

    const img = screen.getByRole('img', { name: mockDocument.name })
    expect(img).toHaveAttribute('src', mockDocument.image_file)
    expect(screen.getByText(/800×600px/)).toBeInTheDocument()
  })
})
