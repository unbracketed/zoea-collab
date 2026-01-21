import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import LayoutFrame from '../components/layout/LayoutFrame'
import api from '../services/api'
import { useWorkspaceStore } from '../stores'

function SearchPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const queryParam = searchParams.get('q') || ''
  const projectIdParam = searchParams.get('project')
  const workspaceIdParam = searchParams.get('workspace')

  const { currentProjectId, currentWorkspaceId, projects } = useWorkspaceStore(
    useShallow((state) => ({
      currentProjectId: state.currentProjectId,
      currentWorkspaceId: state.currentWorkspaceId,
      projects: state.projects,
    }))
  )

  const resolvedProjectId = projectIdParam ? Number(projectIdParam) : currentProjectId
  const resolvedWorkspaceId = workspaceIdParam ? Number(workspaceIdParam) : currentWorkspaceId

  const activeProject = useMemo(() => {
    if (!projects || projects.length === 0 || !resolvedProjectId) return null
    return projects.find((project) => project.id === resolvedProjectId) || null
  }, [projects, resolvedProjectId])

  const [queryInput, setQueryInput] = useState(queryParam)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setQueryInput(queryParam)
  }, [queryParam])

  useEffect(() => {
    const trimmedQuery = queryParam.trim()

    if (!trimmedQuery || !resolvedProjectId) {
      setResult(null)
      setError(null)
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)
    setError(null)

    api
      .geminiFileSearch({
        query: trimmedQuery,
        project_id: resolvedProjectId,
      })
      .then((data) => {
        if (!active) return
        setResult(data)
      })
      .catch((err) => {
        if (!active) return
        setError(err.message)
        setResult(null)
      })
      .finally(() => {
        if (!active) return
        setLoading(false)
      })

    return () => {
      active = false
    }
  }, [queryParam, resolvedProjectId])

  const handleSubmit = (event) => {
    event.preventDefault()

    const params = new URLSearchParams()
    const projectForParams = projectIdParam || (resolvedProjectId ? String(resolvedProjectId) : null)
    const workspaceForParams = workspaceIdParam || (resolvedWorkspaceId ? String(resolvedWorkspaceId) : null)
    const trimmed = queryInput.trim()

    if (projectForParams) {
      params.set('project', projectForParams)
    }
    if (workspaceForParams) {
      params.set('workspace', workspaceForParams)
    }
    if (trimmed) {
      params.set('q', trimmed)
    }

    setSearchParams(params)
  }

  const renderAnswer = () => {
    if (!result) return null

    const answerText = result.answer?.trim()
    return (
      <div className="rounded-lg border border-border bg-surface shadow-soft p-4 space-y-3">
        <div className="flex items-center gap-2 flex-wrap text-xs text-text-secondary">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1">
            Model: {result.model_id}
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 break-all">
            Store: {result.store_id}
          </span>
          {activeProject && (
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1">
              Project: {activeProject.name}
            </span>
          )}
        </div>
        <div className="text-sm leading-relaxed space-y-2">
          {answerText ? (
            answerText.split('\n').map((line, idx) => (
              <p key={idx} className="m-0">
                {line}
              </p>
            ))
          ) : (
            <p className="m-0 text-text-secondary">No answer returned from Gemini.</p>
          )}
        </div>
      </div>
    )
  }

  const renderSources = () => {
    if (!result) return null

    if (!result.sources || result.sources.length === 0) {
      return <div className="text-sm text-text-secondary">No citations returned for this query.</div>
    }

    return (
      <div className="grid gap-3 md:grid-cols-2">
        {result.sources.map((source, idx) => (
          <div
            key={source.uri || source.title || idx}
            className="rounded-lg border border-border bg-background shadow-soft p-3 flex flex-col gap-2"
          >
            <div className="flex justify-between items-start gap-2">
              <div className="font-semibold text-sm">{source.title || 'Untitled source'}</div>
              {source.uri && (
                <span className="text-xs text-text-secondary break-all">{source.uri}</span>
              )}
            </div>
            {source.snippet && (
              <p className="text-sm text-text-secondary m-0">{source.snippet}</p>
            )}
          </div>
        ))}
      </div>
    )
  }

  const noProjectSelected = !resolvedProjectId

  return (
    <LayoutFrame title="Search" variant="full">
      <div className="flex flex-col gap-4 h-full min-h-[70vh]">
        <form onSubmit={handleSubmit} className="flex gap-3 items-center w-full">
          <input
            className="flex-1 px-3 py-2 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            type="search"
            placeholder="Ask Gemini about your project's documents..."
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
          />
          <button type="submit" className="px-4 py-2 bg-primary text-white rounded-md hover:opacity-90 transition-opacity">
            Search
          </button>
        </form>

        {noProjectSelected && (
          <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-0 flex items-center gap-3 justify-between">
            <span>Select a project to search its Gemini File Search store.</span>
            <button
              type="button"
              className="px-2 py-1 text-sm border border-yellow-600 text-yellow-700 rounded hover:bg-yellow-600 hover:text-white transition-colors"
              onClick={() => navigate('/projects')}
            >
              Go to Projects
            </button>
          </div>
        )}

        {!queryParam.trim() && !loading && !error && (
          <div className="text-sm text-text-secondary">
            Enter a query to search your indexed documents. Results use the active project context.
          </div>
        )}

        {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-0">{error}</div>}

        {loading && (
          <div className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status" aria-label="Searching">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm text-text-secondary">Searching Gemini...</span>
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-3">
            {renderAnswer()}
            <div className="rounded-lg border border-border bg-surface shadow-soft p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold">Sources</div>
                <div className="text-xs text-text-secondary">
                  Grounded from {result.sources?.length || 0} document{result.sources?.length === 1 ? '' : 's'}
                </div>
              </div>
              {renderSources()}
            </div>
          </div>
        )}

        {!loading && !error && queryParam.trim() && resolvedProjectId && !result && (
          <div className="text-sm text-text-secondary">No results yet for this query.</div>
        )}
      </div>
    </LayoutFrame>
  )
}

export default SearchPage
