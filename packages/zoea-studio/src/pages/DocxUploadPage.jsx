import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import LayoutFrame from '../components/layout/LayoutFrame'
import api from '../services/api'
import { useWorkspaceStore } from '../stores'

function DocxUploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef(null)
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId)

  const handleSelectFile = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (event) => {
    const selected = event.target.files?.[0]
    if (selected) {
      setFile(selected)
      setStatus(null)
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setStatus('Please select a Word document to upload.')
      return
    }
    if (!currentProjectId || !currentWorkspaceId) {
      setStatus('Select a project and workspace before uploading.')
      return
    }
    setIsUploading(true)
    setStatus('Uploading document...')
    try {
      await api.createDocxDocument({
        name: file.name,
        description,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        file,
      })
      setStatus('Upload successful. Redirecting...')
      navigate('/documents')
    } catch (error) {
      setStatus(error.message || 'Upload failed. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <LayoutFrame title="Upload Word Document" variant="content-centered">
      <div className="max-w-4xl mx-auto py-4 px-4">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Upload Word Document</h1>
          <p className="text-text-secondary">Upload a Word document (.docx) for viewing and text extraction.</p>
        </div>

        <div className="max-w-2xl">
          <div className="bg-surface rounded-lg shadow-soft border border-border">
            <div className="p-6">
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">Word Document File</label>
                <div className="flex gap-2 items-center">
                  <button
                    className="px-4 py-2 border border-primary text-primary rounded hover:bg-primary hover:text-white transition-colors disabled:opacity-50"
                    onClick={handleSelectFile}
                    disabled={isUploading}
                  >
                    Choose File
                  </button>
                  <span className="text-text-secondary">{file ? file.name : 'No file selected'}</span>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">Description</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description"
                />
              </div>

              <div className="flex gap-2">
                <button
                  className="px-4 py-2 bg-secondary text-white rounded hover:opacity-90 transition-opacity disabled:opacity-50"
                  onClick={() => navigate('/documents')}
                  disabled={isUploading}
                >
                  Back to Documents
                </button>
                <button
                  className="px-4 py-2 bg-primary text-white rounded hover:opacity-90 transition-opacity disabled:opacity-50"
                  onClick={handleUpload}
                  disabled={isUploading}
                >
                  {isUploading ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>

              {status && <div className="mt-3 text-primary text-sm">{status}</div>}
            </div>
          </div>
        </div>
      </div>
    </LayoutFrame>
  )
}

export default DocxUploadPage
