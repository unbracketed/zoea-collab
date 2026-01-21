import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import AuthGuard from './components/AuthGuard'

const HomePage = lazy(() => import('./pages/HomePage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const ConversationsPage = lazy(() => import('./pages/ConversationsPage'))
const ExcalidrawCanvasPage = lazy(() => import('./pages/ExcalidrawCanvasPage'))
const D2CanvasPage = lazy(() => import('./pages/D2CanvasPage'))
const MermaidCanvasPage = lazy(() => import('./pages/MermaidCanvasPage'))
const ClipboardsPage = lazy(() => import('./pages/ClipboardsPage'))
const NotepadsListPage = lazy(() => import('./pages/NotepadsListPage'))
const WorkspacesPage = lazy(() => import('./pages/WorkspacesPage'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'))
const DocumentDetailPage = lazy(() => import('./pages/DocumentDetailPage'))
const DocumentEditorPage = lazy(() => import('./pages/DocumentEditorPage'))
const YooptaEditorPage = lazy(() => import('./pages/YooptaEditorPage'))
const ImageUploadPage = lazy(() => import('./pages/ImageUploadPage'))
const PDFUploadPage = lazy(() => import('./pages/PDFUploadPage'))
const DocxUploadPage = lazy(() => import('./pages/DocxUploadPage'))
const XlsxUploadPage = lazy(() => import('./pages/XlsxUploadPage'))
const TrashPage = lazy(() => import('./pages/TrashPage'))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))
const ProjectSettingsPage = lazy(() => import('./pages/ProjectSettingsPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'))
const WorkflowRunsPage = lazy(() => import('./pages/WorkflowRunsPage'))
const WorkflowRunDetailPage = lazy(() => import('./pages/WorkflowRunDetailPage'))

const Loader = () => (
  <div className="flex justify-center items-center w-full py-10">
    <svg className="animate-spin h-8 w-8 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status" aria-label="Loading">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
  </div>
)

function AppRoutes() {
  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        {/* Public routes - no authentication required */}
        <Route path="/verify-email" element={<VerifyEmailPage />} />

        {/* Protected routes - authentication required */}
        <Route
          element={
            <AuthGuard>
              <Suspense fallback={<Loader />}>
                <Outlet />
              </Suspense>
            </AuthGuard>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:conversationId" element={<ChatPage />} />
          <Route path="/conversations" element={<ConversationsPage />} />
          <Route path="/canvas" element={<ExcalidrawCanvasPage />} />
          <Route path="/canvas/d2" element={<D2CanvasPage />} />
          <Route path="/notepad" element={<ClipboardsPage />} />
          <Route path="/notepads" element={<NotepadsListPage />} />
          <Route path="/workspaces" element={<WorkspacesPage />} />
          <Route path="/flows/*" element={<Navigate to="/dashboard" replace />} />
          <Route path="/workflows" element={<WorkflowRunsPage />} />
          <Route path="/workflows/:runId" element={<WorkflowRunDetailPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/folder/:folderId" element={<DocumentsPage />} />
          <Route path="/documents/trash" element={<TrashPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="/documents/new" element={<DocumentEditorPage />} />
          <Route path="/documents/new/richtext" element={<YooptaEditorPage />} />
          <Route path="/documents/new/image" element={<ImageUploadPage />} />
          <Route path="/documents/new/pdf" element={<PDFUploadPage />} />
          <Route path="/documents/new/docx" element={<DocxUploadPage />} />
          <Route path="/documents/new/xlsx" element={<XlsxUploadPage />} />
          <Route path="/documents/new/mermaid" element={<MermaidCanvasPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id/settings" element={<ProjectSettingsPage />} />
          <Route path="/account" element={<AccountPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default AppRoutes
