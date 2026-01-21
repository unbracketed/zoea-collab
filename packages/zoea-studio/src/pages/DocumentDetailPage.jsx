import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, X, Save, MessageSquare, Workflow, Loader2, Download, FileText, Code, Type } from 'lucide-react'
import toast from 'react-hot-toast'
import LayoutFrame from '../components/layout/LayoutFrame'
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions'
import D2DiagramDisplay from '../components/D2DiagramDisplay'
import MarkdownViewer from '../components/MarkdownViewer'
import ExcalidrawEditor, { getSceneData } from '../components/ExcalidrawEditor'
import YooptaEditor from '../components/documents/YooptaEditor'
import YooptaViewer from '../components/documents/YooptaViewer'
import PDFViewer from '../components/documents/PDFViewer'
import DocxViewer from '../components/documents/DocxViewer'
import XlsxViewer from '../components/documents/XlsxViewer'
import { DocumentRAGModal } from '../components/document-rag'
import { useDocumentStore, useFlowsStore, useWorkspaceStore } from '../stores'
import api from '../services/api'
import { markdownToYoopta } from '../utils/markdownToYoopta'

function DocumentDetailPage() {
  const navigate = useNavigate()
  const { documentId } = useParams()
  const docId = documentId ? Number(documentId) : null

  const currentDocument = useDocumentStore((state) => state.currentDocument)
  const setCurrentDocumentId = useDocumentStore((state) => state.setCurrentDocumentId)
  const clearCurrentDocumentId = useDocumentStore((state) => state.clearCurrentDocumentId)
  const loadDocument = useDocumentStore((state) => state.loadDocument)
  const loading = useDocumentStore((state) => state.loading)
  const error = useDocumentStore((state) => state.error)

  // SECURITY: Get current project to validate document belongs to it
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)

  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [isTwoPane, setIsTwoPane] = useState(false)
  const [ragModalOpen, setRagModalOpen] = useState(false)
  const [isSummarizing, setIsSummarizing] = useState(false)
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isConverting, setIsConverting] = useState(false)
  const excalidrawAPIRef = useRef(null)
  const exportMenuRef = useRef(null)

  const runWorkflow = useFlowsStore((state) => state.runWorkflow)

  useEffect(() => {
    if (docId) {
      setCurrentDocumentId(docId)
      loadDocument(docId)
    }
    return () => {
      clearCurrentDocumentId()
    }
  }, [docId, setCurrentDocumentId, loadDocument, clearCurrentDocumentId])

  // SECURITY: Validate document belongs to current project (ZoeaStudio-5kn)
  // If a user switches projects while viewing a document, this will redirect them
  useEffect(() => {
    if (currentDocument && currentProjectId && currentDocument.project_id !== currentProjectId) {
      console.warn(
        `Document ${currentDocument.id} belongs to project ${currentDocument.project_id} ` +
        `but current project is ${currentProjectId}. Redirecting to documents.`
      )
      toast.error('That document belongs to a different project')
      clearCurrentDocumentId()
      navigate('/documents', { replace: true })
    }
  }, [currentDocument, currentProjectId, clearCurrentDocumentId, navigate])

  useEffect(() => {
    if (currentDocument?.content) {
      setEditContent(currentDocument.content)
    }
  }, [currentDocument?.content])

  const handleStartEdit = () => {
    setEditContent(currentDocument?.content || '')
    setSaveError(null)
    setIsEditing(true)
    setIsTwoPane(false)
  }

  const handleCancelEdit = () => {
    setEditContent(currentDocument?.content || '')
    setSaveError(null)
    setIsEditing(false)
    setIsTwoPane(false)
  }

  const handleSave = async () => {
    if (!docId) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (isExcalidraw && excalidrawAPIRef.current) {
        const sceneData = getSceneData(excalidrawAPIRef.current)
        await api.updateExcalidrawDocument(docId, {
          content: JSON.stringify(sceneData),
        })
      } else if (isYoopta) {
        await api.updateYooptaDocument(docId, { content: editContent })
      } else {
        await api.updateMarkdownDocument(docId, { content: editContent })
      }
      await loadDocument(docId, true)
      setIsEditing(false)
    } catch (err) {
      setSaveError(err.message || 'Failed to save document')
    } finally {
      setIsSaving(false)
    }
  }

  const handleExcalidrawRef = useCallback((api) => {
    excalidrawAPIRef.current = api
  }, [])

  const handleSummarize = useCallback(async () => {
    if (!docId || isSummarizing || !currentDocument) return

    setIsSummarizing(true)
    try {
      const result = await runWorkflow(
        'summarize_content',
        {
          source_type: 'document',
          source_id: String(docId),
          summary_style: 'brief',
        },
        {
          background: true,
          workspace_id: currentDocument.workspace_id,
        }
      )

      if (result?.run_id) {
        toast.success('Summarizing document...', {
          duration: 3000,
          icon: '📝',
        })
        // Stay on page - toast notifications will inform user of completion
      }
    } catch (err) {
      console.error('Failed to start summarization:', err)
      toast.error(err.message || 'Failed to start summarization')
    } finally {
      setIsSummarizing(false)
    }
  }, [docId, isSummarizing, runWorkflow, currentDocument])

  const isMarkdown = currentDocument?.document_type === 'Markdown'
  const isExcalidraw = currentDocument?.document_type === 'ExcalidrawDiagram'
  const isYoopta = currentDocument?.document_type === 'YooptaDocument'

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target)) {
        setShowExportMenu(false)
      }
    }
    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showExportMenu])

  const handleExport = useCallback(async (format) => {
    if (!docId || isExporting) return

    setIsExporting(true)
    setShowExportMenu(false)

    try {
      const result = await api.exportYooptaDocument(docId, format)

      // Create a file extension based on format
      const extension = format === 'html' ? 'html' : 'md'
      const mimeType = format === 'html' ? 'text/html' : 'text/markdown'

      // Create blob and download
      const blob = new Blob([result.content], { type: `${mimeType};charset=utf-8` })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${result.document_name || 'document'}.${extension}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      toast.success(`Exported as ${format.toUpperCase()}`)
    } catch (err) {
      console.error('Export failed:', err)
      toast.error(err.message || 'Failed to export document')
    } finally {
      setIsExporting(false)
    }
  }, [docId, isExporting])

  const handleCopyExport = useCallback(async (format) => {
    if (!docId || isExporting) return

    setIsExporting(true)
    setShowExportMenu(false)

    try {
      const result = await api.exportYooptaDocument(docId, format)

      await navigator.clipboard.writeText(result.content)
      toast.success(`Copied ${format.toUpperCase()} to clipboard`)
    } catch (err) {
      console.error('Copy failed:', err)
      toast.error(err.message || 'Failed to copy to clipboard')
    } finally {
      setIsExporting(false)
    }
  }, [docId, isExporting])

  const handleConvertToRichText = useCallback(async () => {
    if (!currentDocument || isConverting) return

    const markdownContent = currentDocument.content
    if (!markdownContent) {
      toast.error('No content to convert')
      return
    }

    setIsConverting(true)

    try {
      // Convert markdown to Yoopta JSON
      const yooptaContent = markdownToYoopta(markdownContent)

      // Create new YooptaDocument
      const newDoc = await api.createYooptaDocument({
        name: `${currentDocument.name} (Rich Text)`,
        description: currentDocument.description || '',
        content: JSON.stringify(yooptaContent),
        project_id: currentDocument.project_id,
        workspace_id: currentDocument.workspace_id,
        folder_id: currentDocument.folder_id || null,
      })

      toast.success('Created rich text version!', { icon: '📝' })

      // Navigate to the new document
      navigate(`/documents/${newDoc.id}`)
    } catch (err) {
      console.error('Conversion failed:', err)
      toast.error(err.message || 'Failed to convert to rich text')
    } finally {
      setIsConverting(false)
    }
  }, [currentDocument, isConverting, navigate])

  const content = () => {
    if (loading) {
      return <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded">Loading document...</div>
    }

    if (error) {
      return <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">{error}</div>
    }

    if (!currentDocument) {
      return <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded">Document not found.</div>
    }

    const isImage = Boolean(currentDocument.image_file)
    const isPdf = currentDocument.document_type === 'PDF'
    const isDocx = currentDocument.document_type === 'WordDocument'
    const isXlsx = currentDocument.document_type === 'SpreadsheetDocument'
    const isD2Diagram = currentDocument.document_type === 'D2Diagram'
    const isExcalidrawDiagram = currentDocument.document_type === 'ExcalidrawDiagram'
    const hasContent = Boolean(currentDocument.content)

    if (isEditing && isMarkdown) {
      const editorPane = (
        <div className="bg-surface border border-border rounded-md shadow-soft flex-1 min-h-[320px] min-w-0 overflow-hidden">
          <textarea
            className="w-full h-full p-4 bg-transparent text-text-primary font-mono text-sm resize-none focus:outline-none"
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            placeholder="Write your markdown here..."
          />
        </div>
      )

      const previewPane = (
        <div className="bg-surface border border-border rounded-md shadow-soft w-full lg:w-[38%] min-h-[320px] overflow-auto">
          <div className="p-4 space-y-3">
            <h3 className="text-base font-semibold">Preview</h3>
            {editContent.trim() ? (
              <MarkdownViewer content={editContent} />
            ) : (
              <p className="text-sm text-text-secondary">Start typing to see a preview.</p>
            )}
          </div>
        </div>
      )

      return (
        <div className="flex flex-col flex-1 min-h-0 gap-4 p-6">
          {saveError && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">{saveError}</div>
          )}

          {isTwoPane ? (
            <div className="flex flex-col lg:flex-row gap-4 flex-1 min-h-[520px]">
              {editorPane}
              {previewPane}
            </div>
          ) : (
            <div className="flex flex-col flex-1 min-h-[520px]">
              {editorPane}
            </div>
          )}
        </div>
      )
    }

    return (
      <div className={isEditing ? "flex flex-col flex-1 min-h-0" : "space-y-4"}>
        {saveError && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">{saveError}</div>
        )}

        {isD2Diagram && hasContent ? (
          <div className="border border-border rounded-md bg-surface h-[70vh] overflow-hidden">
            <D2DiagramDisplay d2Source={currentDocument.content} />
          </div>
        ) : isExcalidrawDiagram ? (
          <div className="flex-1 min-h-0 w-full overflow-hidden">
            {(() => {
              let initialData = null
              if (hasContent) {
                try {
                  initialData = JSON.parse(currentDocument.content)
                } catch (e) {
                  console.error('Failed to parse Excalidraw content:', e)
                }
              }
              return (
                <ExcalidrawEditor
                  initialData={initialData}
                  readOnly={!isEditing}
                  excalidrawRef={handleExcalidrawRef}
                />
              )
            })()}
          </div>
        ) : isYoopta ? (
          isEditing ? (
            <div className="flex flex-col flex-1 min-h-0 p-6">
              <div className="border border-border rounded-md bg-surface flex-1 min-h-0 overflow-hidden">
                <YooptaEditor
                  value={editContent}
                  onChange={(newValue) => setEditContent(JSON.stringify(newValue))}
                  className="h-full p-4"
                  projectId={currentDocument?.project_id}
                  workspaceId={currentDocument?.workspace_id}
                />
              </div>
            </div>
          ) : (
            <div className="border border-border rounded-md bg-surface min-h-[400px] overflow-hidden">
              <YooptaViewer
                value={currentDocument.content}
                className="p-4"
              />
            </div>
          )
        ) : (
          <div className="border border-border rounded-md bg-surface p-4">
            {isImage ? (
              <div className="flex flex-col items-center gap-3">
                <img
                  src={currentDocument.image_file}
                  alt={currentDocument.name}
                  className="max-h-[70vh] w-auto object-contain rounded-md border border-border"
                />
                {currentDocument.width && currentDocument.height && (
                  <p className="text-xs text-text-secondary">
                    {currentDocument.width}×{currentDocument.height}px
                  </p>
                )}
              </div>
            ) : isPdf ? (
              <div className="h-[70vh] overflow-hidden">
                <PDFViewer document={currentDocument} />
              </div>
            ) : isDocx ? (
              <div className="h-[70vh] overflow-hidden">
                <DocxViewer document={currentDocument} />
              </div>
            ) : isXlsx ? (
              <div className="h-[70vh] overflow-hidden">
                <XlsxViewer document={currentDocument} />
              </div>
            ) : hasContent ? (
              <MarkdownViewer content={currentDocument.content} />
            ) : (
              <p className="text-text-secondary">No content available.</p>
            )}
          </div>
        )}
      </div>
    )
  }

  const headerActions = (
    <ViewPrimaryActions>
      {isEditing ? (
        <>
          <ViewPrimaryActions.Button variant="outline" onClick={handleCancelEdit} title="Cancel editing">
            <X className="h-4 w-4" />
          </ViewPrimaryActions.Button>
          {isMarkdown && (
            <ViewPrimaryActions.Button
              variant="outline"
              onClick={() => setIsTwoPane((prev) => !prev)}
              title={isTwoPane ? 'Switch to single pane' : 'Switch to two-pane with preview'}
            >
              {isTwoPane ? 'Two-pane: On' : 'Two-pane: Off'}
            </ViewPrimaryActions.Button>
          )}
          <ViewPrimaryActions.Button onClick={handleSave} disabled={isSaving} title="Save changes">
            <Save className="h-4 w-4" />
          </ViewPrimaryActions.Button>
        </>
      ) : (
        <>
          <ViewPrimaryActions.Button
            variant="outline"
            onClick={() => {
              clearCurrentDocumentId()
              navigate('/documents')
            }}
            title="Back to documents"
          >
            <ArrowLeft className="h-4 w-4" />
          </ViewPrimaryActions.Button>
          {(isMarkdown || isExcalidraw || isYoopta) && (
            <ViewPrimaryActions.Button variant="outline" onClick={handleStartEdit} title="Edit document">
              <Pencil className="h-4 w-4" />
            </ViewPrimaryActions.Button>
          )}
          {isMarkdown && currentDocument && (
            <ViewPrimaryActions.Button
              variant="outline"
              onClick={handleConvertToRichText}
              disabled={isConverting}
              title="Convert to Rich Text (Yoopta)"
            >
              {isConverting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Type className="h-4 w-4" />
              )}
            </ViewPrimaryActions.Button>
          )}
          {isYoopta && currentDocument && (
            <div className="relative" ref={exportMenuRef}>
              <ViewPrimaryActions.Button
                variant="outline"
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={isExporting}
                title="Export document"
              >
                {isExporting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
              </ViewPrimaryActions.Button>
              {showExportMenu && (
                <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-surface border border-border z-50">
                  <div className="py-1">
                    <div className="px-3 py-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">
                      Download
                    </div>
                    <button
                      onClick={() => handleExport('markdown')}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
                    >
                      <FileText className="h-4 w-4" />
                      Markdown (.md)
                    </button>
                    <button
                      onClick={() => handleExport('html')}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
                    >
                      <Code className="h-4 w-4" />
                      HTML (.html)
                    </button>
                    <div className="border-t border-border my-1" />
                    <div className="px-3 py-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">
                      Copy to Clipboard
                    </div>
                    <button
                      onClick={() => handleCopyExport('markdown')}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
                    >
                      <FileText className="h-4 w-4" />
                      Copy as Markdown
                    </button>
                    <button
                      onClick={() => handleCopyExport('html')}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
                    >
                      <Code className="h-4 w-4" />
                      Copy as HTML
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {currentDocument && (
            <>
              <ViewPrimaryActions.Button
                variant="outline"
                onClick={handleSummarize}
                disabled={isSummarizing}
                title="Summarize document"
              >
                {isSummarizing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Workflow className="h-4 w-4" />
                )}
              </ViewPrimaryActions.Button>
              <ViewPrimaryActions.Button
                variant="outline"
                onClick={() => setRagModalOpen(true)}
                title="Chat with document"
              >
                <MessageSquare className="h-4 w-4" />
              </ViewPrimaryActions.Button>
            </>
          )}
        </>
      )}
    </ViewPrimaryActions>
  )

  return (
    <>
      <LayoutFrame
        title={currentDocument?.name || 'Document'}
        actions={headerActions}
        variant="content-centered"
        noPadding={isEditing || isExcalidraw}
        maxWidth={isExcalidraw ? '' : undefined}
      >
        {content()}
      </LayoutFrame>
      <DocumentRAGModal
        isOpen={ragModalOpen}
        onClose={() => setRagModalOpen(false)}
        contextType="single"
        contextId={docId}
        contextName={currentDocument?.name}
      />
    </>
  )
}

export default DocumentDetailPage
