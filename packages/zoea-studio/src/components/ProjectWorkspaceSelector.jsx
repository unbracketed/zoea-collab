/**
 * Project and Workspace Selector Component
 *
 * Dropdown selectors for switching between projects and workspaces.
 * Updates URL parameters to maintain context across page navigation.
 */

import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FolderKanban, Briefcase } from 'lucide-react';
import { useWorkspaceStore } from '../stores';

function ProjectWorkspaceSelector() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Workspace store state
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const projects = useWorkspaceStore((state) => state.projects);
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const loading = useWorkspaceStore((state) => state.loading);

  // Workspace store actions
  const loadProjects = useWorkspaceStore((state) => state.loadProjects);
  const loadWorkspaces = useWorkspaceStore((state) => state.loadWorkspaces);
  const switchProject = useWorkspaceStore((state) => state.switchProject);
  const setCurrentWorkspace = useWorkspaceStore((state) => state.setCurrentWorkspace);
  const initializeFromUrl = useWorkspaceStore((state) => state.initializeFromUrl);

  // Initialize from URL on mount
  useEffect(() => {
    const projectIdParam = searchParams.get('project');
    const workspaceIdParam = searchParams.get('workspace');

    // Initialize store from URL parameters
    initializeFromUrl(projectIdParam, workspaceIdParam);
  }, []); // Only run on mount

  // Update URL when project/workspace changes
  const updateUrlParams = (projectId, workspaceId) => {
    const params = new URLSearchParams(searchParams);

    if (projectId) {
      params.set('project', projectId.toString());
    } else {
      params.delete('project');
    }

    if (workspaceId) {
      params.set('workspace', workspaceId.toString());
    } else {
      params.delete('workspace');
    }

    // Update URL with new params
    navigate(`?${params.toString()}`, { replace: true });
  };

  // Handle project change
  const handleProjectChange = async (e) => {
    const newProjectId = parseInt(e.target.value, 10);

    // Switch project in store (this will also load workspaces)
    await switchProject(newProjectId);

    // Update URL - workspace will be auto-selected by store
    updateUrlParams(newProjectId, null);
  };

  // Handle workspace change
  const handleWorkspaceChange = (e) => {
    const newWorkspaceId = parseInt(e.target.value, 10);

    // Update workspace in store
    setCurrentWorkspace(newWorkspaceId);

    // Update URL
    updateUrlParams(currentProjectId, newWorkspaceId);
  };

  // Update URL when store updates workspace (after auto-selection)
  useEffect(() => {
    if (currentProjectId && currentWorkspaceId) {
      updateUrlParams(currentProjectId, currentWorkspaceId);
    }
  }, [currentWorkspaceId]); // Update URL when workspace is auto-selected

  return (
    <div className="project-workspace-selector">
      {/* Project Selector */}
      <div className="selector-group">
        <label htmlFor="project-select" className="selector-label">
          <FolderKanban size={16} />
          <span>Project</span>
        </label>
        <select
          id="project-select"
          className="selector-dropdown"
          value={currentProjectId || ''}
          onChange={handleProjectChange}
          disabled={loading || projects.length === 0}
        >
          {projects.length === 0 ? (
            <option value="">No projects</option>
          ) : (
            projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))
          )}
        </select>
      </div>

      {/* Workspace Selector */}
      <div className="selector-group">
        <label htmlFor="workspace-select" className="selector-label">
          <Briefcase size={16} />
          <span>Workspace</span>
        </label>
        <select
          id="workspace-select"
          className="selector-dropdown"
          value={currentWorkspaceId || ''}
          onChange={handleWorkspaceChange}
          disabled={loading || workspaces.length === 0 || !currentProjectId}
        >
          {workspaces.length === 0 ? (
            <option value="">No workspaces</option>
          ) : (
            workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {'  '.repeat(workspace.level)}{workspace.name}
              </option>
            ))
          )}
        </select>
      </div>
    </div>
  );
}

export default ProjectWorkspaceSelector;
