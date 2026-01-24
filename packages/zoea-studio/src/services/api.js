/**
 * API Client Service
 *
 * Centralized API communication with Django backend.
 * Handles CSRF tokens, session cookies, and error responses.
 *
 * TODO: Consider splitting this module into feature-specific clients once
 * scoped filtering and additional endpoints stabilize.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Get CSRF token from cookies
 */
function getCSRFToken() {
  const name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Make an API request with proper headers and error handling
 */
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultOptions = {
    credentials: 'include', // Include session cookies
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken() || '',
    },
  };

  const config = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...options.headers,
    },
  };

  // Let the browser set the multipart boundary when sending FormData
  if (config.body instanceof FormData) {
    const headers = { ...config.headers };
    delete headers['Content-Type'];
    config.headers = headers;
  }

  try {
    const response = await fetch(url, config);

    // Handle non-JSON responses
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.text();
    }

    const data = await response.json();

    if (!response.ok) {
      // Extract error message from Django response
      let errorMessage = data.detail || data.error;

      // Handle Django Ninja field-level validation errors
      if (!errorMessage && typeof data === 'object') {
        // Try to extract field errors (e.g., {workspace_id: ["Required field"]})
        const fieldErrors = Object.entries(data)
          .filter(([key, value]) => Array.isArray(value) || typeof value === 'string')
          .map(([key, value]) => {
            const msg = Array.isArray(value) ? value.join(', ') : value;
            return `${key}: ${msg}`;
          });

        if (fieldErrors.length > 0) {
          errorMessage = fieldErrors.join('; ');
        }
      }

      // Fallback to status text
      if (!errorMessage) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }

      throw new Error(errorMessage);
    }

    return data;
  } catch (error) {
    console.error(`API Request failed: ${endpoint}`, error);
    throw error;
  }
}

/**
 * API Client
 */
const api = {
  /**
   * Check authentication status
   */
  async checkAuth() {
    try {
      const data = await apiRequest('/api/auth/check');
      return data; // Returns { authenticated, username, organization }
    } catch (error) {
      if (error.message.includes('401') || error.message.includes('403')) {
        return { authenticated: false, username: null, organization: null };
      }
      throw error;
    }
  },

  /**
   * Login user
   * Note: Django doesn't have a built-in JSON login endpoint by default.
   * You'll need to create one in the backend or use django-rest-framework auth.
   * This is a placeholder that assumes you'll add /api/auth/login endpoint.
   */
  async login(username, password) {
    return await apiRequest('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  /**
   * Logout user
   */
  async logout() {
    return await apiRequest('/api/auth/logout', {
      method: 'POST',
    });
  },

  /**
   * Register new user
   * @param {Object} params
   * @param {string} params.username - Username
   * @param {string} params.email - Email address
   * @param {string} params.password1 - Password
   * @param {string} params.password2 - Password confirmation
   * @returns {Promise<{success: boolean, message: string, username: string, email: string}>}
   */
  async signup({ username, email, password1, password2 }) {
    return await apiRequest('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ username, email, password1, password2 }),
    });
  },

  /**
   * Verify email address with confirmation key
   * @param {string} key - Verification key from email
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async verifyEmail(key) {
    return await apiRequest('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ key }),
    });
  },

  /**
   * Resend verification email
   * @param {string} email - Email address to resend verification to
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async resendVerification(email) {
    return await apiRequest('/api/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /**
   * Fetch all conversations for the current user
   *
   * @param {Object} params
   * @param {number} [params.project_id] - Filter by project ID
   * @param {number} [params.workspace_id] - Filter by workspace ID
   */
  async fetchConversations({
    project_id = null,
    workspace_id = null,
  } = {}) {
    const params = new URLSearchParams();

    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }

    if (workspace_id !== null) {
      params.append('workspace_id', workspace_id.toString());
    }

    const queryString = params.toString();
    const endpoint = queryString ? `/api/conversations?${queryString}` : '/api/conversations';
    return await apiRequest(endpoint);
  },

  /**
   * Fetch a specific conversation with all its messages
   *
   * @param {number} conversationId - ID of the conversation to fetch
   */
  async fetchConversation(conversationId) {
    return await apiRequest(`/api/conversations/${conversationId}`);
  },

  /**
   * Delete a conversation
   *
   * @param {number} conversationId - ID of the conversation to delete
   */
  async deleteConversation(conversationId) {
    return await apiRequest(`/api/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Fetch artifacts for a conversation
   *
   * @param {number} conversationId - ID of the conversation
   */
  async fetchConversationArtifacts(conversationId) {
    return await apiRequest(`/api/conversations/${conversationId}/artifacts`);
  },

  /**
   * Fetch artifacts for a workflow run
   *
   * @param {string} runId - UUID of the workflow run
   */
  async fetchWorkflowRunArtifacts(runId) {
    return await apiRequest(`/api/workflows/runs/${runId}/artifacts`);
  },

  /**
   * Send a chat message
   *
   * @param {Object} params
   * @param {string} params.message - The user's message
   * @param {string} [params.agent_name='ZoeaAssistant'] - Agent to use
   * @param {string} [params.instructions] - Custom instructions
   * @param {number} [params.conversation_id] - ID of existing conversation to continue
   * @param {number} [params.project_id] - Project ID (uses default if not provided)
   * @param {number} [params.workspace_id] - Workspace ID (uses default if not provided)
   * @param {string} [params.conversation_history] - Full conversation history for diagram generation
   * @param {boolean} [params.debug=false] - Enable debug mode
   * @param {string} [params.view_type] - Current view type for routing (chat, document_detail, excalidraw)
   * @param {number} [params.document_id] - Document ID for document context
   * @param {Array<number>} [params.document_ids] - Multiple document IDs for multi-doc context
   * @param {number} [params.folder_id] - Folder ID for folder-scoped context
   * @param {number} [params.collection_id] - Collection/notebook ID
   * @param {string} [params.rag_session_id] - Existing RAG session ID
   * @param {Array<string>} [params.requested_capabilities] - Requested capabilities (e.g., 'deep_research')
   */
  async sendMessage({
    message,
    agent_name = 'ZoeaAssistant',
    instructions = 'You are a helpful AI assistant for Zoea Studio.',
    conversation_id = null,
    project_id = null,
    workspace_id = null,
    conversation_history = null,
    clipboard_id = null,
    debug = false,
    // Context parameters for agent routing
    view_type = null,
    document_id = null,
    document_ids = null,
    folder_id = null,
    collection_id = null,
    rag_session_id = null,
    requested_capabilities = null,
  }) {
    const payload = {
      message,
      agent_name,
      instructions,
      debug,
    };

    // Only include conversation_id if provided
    if (conversation_id !== null) {
      payload.conversation_id = conversation_id;
    }

    // Only include project_id if provided
    if (project_id !== null) {
      payload.project_id = project_id;
    }

    // Only include workspace_id if provided
    if (workspace_id !== null) {
      payload.workspace_id = workspace_id;
    }

    // Only include conversation_history if provided
    if (conversation_history !== null) {
      payload.conversation_history = conversation_history;
    }

    if (clipboard_id !== null) {
      payload.clipboard_id = clipboard_id;
    }

    // Context parameters for agent routing
    if (view_type !== null) {
      payload.view_type = view_type;
    }
    if (document_id !== null) {
      payload.document_id = document_id;
    }
    if (document_ids !== null && document_ids.length > 0) {
      payload.document_ids = document_ids;
    }
    if (folder_id !== null) {
      payload.folder_id = folder_id;
    }
    if (collection_id !== null) {
      payload.collection_id = collection_id;
    }
    if (rag_session_id !== null) {
      payload.rag_session_id = rag_session_id;
    }
    if (requested_capabilities !== null && requested_capabilities.length > 0) {
      payload.requested_capabilities = requested_capabilities;
    }

    return await apiRequest('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Send a canvas-aware chat message for generating Excalidraw elements
   *
   * @param {Object} params
   * @param {string} params.message - The user's prompt
   * @param {number} [params.project_id] - Project ID
   * @param {number} [params.workspace_id] - Workspace ID
   * @param {number} [params.document_id] - Excalidraw document ID
   * @param {Object} [params.context] - Canvas context (name, selected elements, etc.)
   */
  async sendCanvasChat({ message, project_id = null, workspace_id = null, document_id = null, context = {} }) {
    const payload = {
      message,
      agent_name: 'CanvasAssistant',
      view_type: 'excalidraw',
      instructions: `You are an AI assistant helping create visual content on an Excalidraw canvas.

When asked to create diagrams, flowcharts, or visual structures:
- Use Mermaid syntax in code blocks (e.g., \`\`\`mermaid)
- For flowcharts, use: flowchart TD or flowchart LR
- For sequence diagrams, use: sequenceDiagram
- For class diagrams, use: classDiagram
- For entity relationships, use: erDiagram

When asked for text content:
- Provide concise, clear text suitable for canvas display
- Use bullet points or numbered lists when appropriate
- Keep individual text blocks under 200 characters

Current canvas: ${context.canvasName || 'Untitled'}`,
    };

    if (project_id !== null) {
      payload.project_id = project_id;
    }

    if (workspace_id !== null) {
      payload.workspace_id = workspace_id;
    }

    if (document_id !== null) {
      payload.document_id = document_id;
    }

    return await apiRequest('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Health check
   */
  async healthCheck() {
    return await apiRequest('/api/health');
  },

  /**
   * Fetch documents for the current user's organization
   *
   * @param {Object} params
   * @param {number} [params.page=1] - Page number
   * @param {number} [params.page_size=20] - Number of items per page
   * @param {string} [params.search] - Search query
   * @param {string} [params.document_type] - Filter by document type
   * @param {number} [params.project_id] - Filter by project ID
   * @param {number} [params.workspace_id] - Filter by workspace ID
   */
  async fetchDocuments({
    page = 1,
    page_size = 20,
    search = null,
    document_type = null,
    project_id = null,
    workspace_id = null,
    folder_id = null,
    include_previews = true,
  } = {}) {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: page_size.toString(),
    });

    if (search) {
      params.append('search', search);
    }

    if (document_type) {
      params.append('document_type', document_type);
    }

    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }

    if (workspace_id !== null) {
      params.append('workspace_id', workspace_id.toString());
    }

    if (folder_id !== null) {
      params.append('folder_id', folder_id.toString());
    }

    if (include_previews) {
      params.append('include_previews', 'true');
    }

    return await apiRequest(`/api/documents?${params.toString()}`);
  },

  /**
   * Query Gemini File Search for a project's indexed documents
   */
  async geminiFileSearch({
    query,
    project_id,
    model_id = null,
    metadata_filter = null,
  }) {
    const payload = { query, project_id };

    if (model_id) {
      payload.model_id = model_id;
    }
    if (metadata_filter) {
      payload.metadata_filter = metadata_filter;
    }

    return await apiRequest('/api/documents/file-search', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch a specific document by ID
   *
   * @param {number} documentId - ID of the document to fetch
   */
  async fetchDocument(documentId, { include_preview = true } = {}) {
    const suffix = include_preview ? '?include_preview=true' : '';
    return await apiRequest(`/api/documents/${documentId}${suffix}`);
  },

  /**
   * Fetch all projects for the current user's organization
   */
  async fetchProjects() {
    return await apiRequest('/api/projects');
  },

  /**
   * Fetch a specific project by ID
   *
   * @param {number} projectId - ID of the project to fetch
   */
  async fetchProject(projectId) {
    return await apiRequest(`/api/projects/${projectId}`);
  },

  /**
   * Create a new project
   *
   * @param {Object} payload - Project data
   * @param {string} payload.name - Project name (required)
   * @param {string} [payload.description] - Project description
   * @param {string} [payload.color_theme] - Color theme name
   */
  async createProject(payload) {
    return await apiRequest('/api/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Update a project's settings
   *
   * @param {number} projectId - ID of the project to update
   * @param {Object} payload - Fields to update
   * @param {string} [payload.name] - Project name
   * @param {string} [payload.description] - Project description
   * @param {string} [payload.color_theme] - Color theme name
   */
  async updateProject(projectId, payload) {
    return await apiRequest(`/api/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Upload a project avatar image
   *
   * @param {number} projectId - ID of the project
   * @param {File} file - The image file to upload
   */
  async uploadProjectAvatar(projectId, file) {
    const formData = new FormData();
    formData.append('avatar', file);

    return await apiRequest(`/api/projects/${projectId}/avatar`, {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * Delete a project's avatar image
   *
   * @param {number} projectId - ID of the project
   */
  async deleteProjectAvatar(projectId) {
    return await apiRequest(`/api/projects/${projectId}/avatar`, {
      method: 'DELETE',
    });
  },

  // =========================================================================
  // LLM Configuration
  // =========================================================================

  /**
   * Fetch available LLM providers
   *
   * @returns {Promise<{providers: Array, default_provider: string|null}>}
   */
  async fetchLLMProviders() {
    return await apiRequest('/api/llm/providers');
  },

  /**
   * Fetch available models for a specific provider
   *
   * @param {string} providerName - Name of the provider (openai, gemini, local)
   * @returns {Promise<{models: Array, provider: string}>}
   */
  async fetchProviderModels(providerName) {
    return await apiRequest(`/api/llm/providers/${providerName}/models`);
  },

  /**
   * Validate LLM provider credentials
   *
   * @param {Object} payload
   * @param {string} payload.provider - Provider name
   * @param {string} payload.api_key - API key to validate
   * @returns {Promise<{valid: boolean, provider: string, error: string|null}>}
   */
  async validateLLMCredentials(payload) {
    return await apiRequest('/api/llm/validate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch project LLM configuration
   *
   * @param {number} projectId - ID of the project
   * @returns {Promise<Object>} Project LLM configuration
   */
  async fetchProjectLLMConfig(projectId) {
    return await apiRequest(`/api/llm/projects/${projectId}/llm-config`);
  },

  /**
   * Update project LLM configuration
   *
   * @param {number} projectId - ID of the project
   * @param {Object} payload - LLM configuration updates
   * @param {string} [payload.llm_provider] - Provider name
   * @param {string} [payload.llm_model_id] - Model ID
   * @param {string} [payload.openai_api_key] - OpenAI API key
   * @param {string} [payload.gemini_api_key] - Gemini API key
   * @param {string} [payload.local_model_endpoint] - Local model endpoint URL
   * @returns {Promise<Object>} Updated project LLM configuration
   */
  async updateProjectLLMConfig(projectId, payload) {
    return await apiRequest(`/api/llm/projects/${projectId}/llm-config`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch workspaces, optionally filtered by project
   *
   * @param {Object} params
   * @param {number} [params.project_id] - Filter by project ID
   */
  async fetchWorkspaces({
    project_id = null,
  } = {}) {
    const params = new URLSearchParams();

    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }

    const queryString = params.toString();
    const endpoint = queryString ? `/api/workspaces?${queryString}` : '/api/workspaces';
    return await apiRequest(endpoint);
  },

  /**
   * Fetch a specific workspace by ID
   *
   * @param {number} workspaceId - ID of the workspace to fetch
   */
  async fetchWorkspace(workspaceId) {
    return await apiRequest(`/api/workspaces/${workspaceId}`);
  },

  /**
   * Create a D2 diagram document
   */
  async createD2Document(payload) {
    return await apiRequest('/api/documents/d2/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create a Mermaid diagram document
   */
  async createMermaidDocument(payload) {
    return await apiRequest('/api/documents/mermaid/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create a Markdown document
   */
  async createMarkdownDocument(payload) {
    return await apiRequest('/api/documents/markdown/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Update a Markdown document
   */
  async updateMarkdownDocument(documentId, payload) {
    return await apiRequest(`/api/documents/markdown/${documentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create an Excalidraw diagram document
   */
  async createExcalidrawDocument(payload) {
    return await apiRequest('/api/documents/excalidraw/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Update an Excalidraw diagram document
   */
  async updateExcalidrawDocument(documentId, payload) {
    return await apiRequest(`/api/documents/excalidraw/${documentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create a Yoopta rich text document
   */
  async createYooptaDocument(payload) {
    return await apiRequest('/api/documents/yoopta/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Update a Yoopta rich text document
   */
  async updateYooptaDocument(documentId, payload) {
    return await apiRequest(`/api/documents/yoopta/${documentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Export a Yoopta document to HTML or Markdown
   * @param {number} documentId - Document ID
   * @param {string} format - Export format: 'html' or 'markdown'
   * @returns {Promise<{content: string, format: string, document_id: number, document_name: string}>}
   */
  async exportYooptaDocument(documentId, format = 'markdown') {
    return await apiRequest(`/api/documents/yoopta/${documentId}/export?format=${format}`, {
      method: 'GET',
    });
  },

  /**
   * Upload an image document
   */
  async createImageDocument({
    name,
    description = '',
    project_id,
    workspace_id,
    folder_id = null,
    file,
  }) {
    if (!file) {
      throw new Error('Image file is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to upload an image');
    }

    const formData = new FormData();
    formData.append('name', name || file.name);
    formData.append('description', description);
    formData.append('project_id', project_id.toString());
    formData.append('workspace_id', workspace_id.toString());
    if (folder_id !== null && folder_id !== undefined) {
      formData.append('folder_id', folder_id.toString());
    }
    formData.append('image_file', file);

    return await apiRequest('/api/documents/images/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async createPdfDocument({
    name,
    description = '',
    project_id,
    workspace_id,
    folder_id = null,
    file,
  }) {
    if (!file) {
      throw new Error('PDF file is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to upload a PDF');
    }

    const formData = new FormData();
    formData.append('name', name || file.name);
    formData.append('description', description);
    formData.append('project_id', project_id.toString());
    formData.append('workspace_id', workspace_id.toString());
    if (folder_id !== null && folder_id !== undefined) {
      formData.append('folder_id', folder_id.toString());
    }
    formData.append('pdf_file', file);

    return await apiRequest('/api/documents/pdfs/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async createDocxDocument({
    name,
    description = '',
    project_id,
    workspace_id,
    folder_id = null,
    file,
  }) {
    if (!file) {
      throw new Error('Word document file is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to upload a Word document');
    }

    const formData = new FormData();
    formData.append('name', name || file.name);
    formData.append('description', description);
    formData.append('project_id', project_id.toString());
    formData.append('workspace_id', workspace_id.toString());
    if (folder_id !== null && folder_id !== undefined) {
      formData.append('folder_id', folder_id.toString());
    }
    formData.append('docx_file', file);

    return await apiRequest('/api/documents/docx/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async getDocxHtml(documentId) {
    return await apiRequest(`/api/documents/docx/${documentId}/html`);
  },

  async createXlsxDocument({
    name,
    description = '',
    project_id,
    workspace_id,
    folder_id = null,
    file,
  }) {
    if (!file) {
      throw new Error('Spreadsheet file is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to upload a spreadsheet');
    }

    const formData = new FormData();
    formData.append('name', name || file.name);
    formData.append('description', description);
    formData.append('project_id', project_id.toString());
    formData.append('workspace_id', workspace_id.toString());
    if (folder_id !== null && folder_id !== undefined) {
      formData.append('folder_id', folder_id.toString());
    }
    formData.append('xlsx_file', file);

    return await apiRequest('/api/documents/xlsx/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async getXlsxHtml(documentId) {
    return await apiRequest(`/api/documents/xlsx/${documentId}/html`);
  },

  /**
   * Import documents from a server-side directory.
   */
  async importDocumentsFromDirectory({
    path,
    project_id,
    workspace_id,
    folder_id = null,
    create_root_folder = true,
    root_folder_name = null,
    on_conflict = 'rename',
    follow_symlinks = false,
  }) {
    if (!path) {
      throw new Error('Directory path is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to import documents');
    }

    const payload = {
      path,
      project_id,
      workspace_id,
      folder_id,
      create_root_folder,
      root_folder_name,
      on_conflict,
      follow_symlinks,
    };

    return await apiRequest('/api/documents/import/directory', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Import documents from an uploaded archive file.
   */
  async importDocumentsFromArchive({
    file,
    project_id,
    workspace_id,
    folder_id = null,
    create_root_folder = true,
    root_folder_name = null,
    on_conflict = 'rename',
  }) {
    if (!file) {
      throw new Error('Archive file is required');
    }
    if (!project_id || !workspace_id) {
      throw new Error('Project and workspace are required to import documents');
    }

    const formData = new FormData();
    formData.append('archive_file', file);
    formData.append('project_id', project_id.toString());
    formData.append('workspace_id', workspace_id.toString());
    formData.append('create_root_folder', create_root_folder ? 'true' : 'false');
    formData.append('on_conflict', on_conflict);
    if (folder_id !== null && folder_id !== undefined) {
      formData.append('folder_id', folder_id.toString());
    }
    if (root_folder_name) {
      formData.append('root_folder_name', root_folder_name);
    }

    return await apiRequest('/api/documents/import/archive', {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * Folder APIs
   */
  async fetchFolders({ workspace_id = null, parent_id = null } = {}) {
    const params = new URLSearchParams();
    if (workspace_id !== null) {
      params.append('workspace_id', workspace_id.toString());
    }
    if (parent_id !== null) {
      params.append('parent_id', parent_id.toString());
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/documents/folders${suffix}`);
  },

  async createFolder(payload) {
    return await apiRequest('/api/documents/folders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async updateFolder(folderId, payload) {
    return await apiRequest(`/api/documents/folders/${folderId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  async deleteFolder(folderId) {
    return await apiRequest(`/api/documents/folders/${folderId}`, {
      method: 'DELETE',
    });
  },

  async fetchFolder(folderId) {
    return await apiRequest(`/api/documents/folders/${folderId}`);
  },

  async moveDocument(documentId, payload) {
    return await apiRequest(`/api/documents/${documentId}/move`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // =========================================================================
  // Document Trash Management
  // =========================================================================

  /**
   * Fetch trashed documents
   *
   * @param {Object} params
   * @param {number} [params.workspace_id] - Filter by workspace ID
   */
  async fetchTrashedDocuments({ workspace_id = null } = {}) {
    const params = new URLSearchParams();
    if (workspace_id !== null) {
      params.append('workspace_id', workspace_id.toString());
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/documents/trash${suffix}`);
  },

  /**
   * Rename a document
   *
   * @param {number} documentId - ID of the document to rename
   * @param {string} name - New name for the document
   */
  async renameDocument(documentId, name) {
    return await apiRequest(`/api/documents/${documentId}/rename?name=${encodeURIComponent(name)}`, {
      method: 'PATCH',
    });
  },

  /**
   * Move a document to trash
   *
   * @param {number} documentId - ID of the document to trash
   */
  async trashDocument(documentId) {
    return await apiRequest(`/api/documents/${documentId}/trash`, {
      method: 'POST',
    });
  },

  /**
   * Restore a document from trash
   *
   * @param {number} documentId - ID of the document to restore
   * @param {number} [folderId] - Optional folder ID to restore to
   */
  async restoreDocument(documentId, folderId = null) {
    const suffix = folderId !== null ? `?folder_id=${folderId}` : '';
    return await apiRequest(`/api/documents/${documentId}/restore${suffix}`, {
      method: 'POST',
    });
  },

  /**
   * Permanently delete a trashed document
   *
   * @param {number} documentId - ID of the document to permanently delete
   */
  async permanentlyDeleteDocument(documentId) {
    return await apiRequest(`/api/documents/${documentId}/permanent`, {
      method: 'DELETE',
    });
  },

  /**
   * Fetch clipboards for a workspace
   */
  async fetchClipboards({ workspace_id, include_recent = false } = {}) {
    if (!workspace_id) {
      throw new Error('workspace_id is required to fetch clipboards');
    }

    const params = new URLSearchParams({
      workspace_id: workspace_id.toString(),
    });

    if (include_recent) {
      params.append('include_recent', 'true');
    }

    return await apiRequest(`/api/clipboards/?${params.toString()}`);
  },

  /**
   * Create and optionally activate a clipboard
   */
  async createClipboard(payload) {
    return await apiRequest('/api/clipboards/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch clipboard detail (optionally including items)
   */
  async fetchClipboard(clipboardId, { include_items = false } = {}) {
    const params = new URLSearchParams();
    if (include_items) {
      params.append('include_items', 'true');
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/clipboards/${clipboardId}${suffix}`);
  },

  /**
   * Activate a clipboard
   */
  async activateClipboard(clipboardId) {
    return await apiRequest(`/api/clipboards/${clipboardId}/activate`, {
      method: 'POST',
    });
  },

  /**
   * Fetch clipboard items
   */
  async fetchClipboardItems(clipboardId) {
    return await apiRequest(`/api/clipboards/${clipboardId}/items`);
  },

  /**
   * Add item to clipboard
   */
  async addClipboardItem(clipboardId, payload) {
    return await apiRequest(`/api/clipboards/${clipboardId}/items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Delete clipboard item
   */
  async deleteClipboardItem(clipboardId, itemId) {
    return await apiRequest(`/api/clipboards/${clipboardId}/items/${itemId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Reorder clipboard items
   */
  async reorderClipboardItems(clipboardId, items) {
    return await apiRequest(`/api/clipboards/${clipboardId}/items/reorder`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    });
  },

  /**
   * Export clipboard to specified format (default: markdown)
   */
  async exportClipboard(clipboardId, { format = 'markdown' } = {}) {
    const params = new URLSearchParams({ format });
    return await apiRequest(`/api/clipboards/${clipboardId}/export?${params.toString()}`);
  },

  /**
   * Fetch notepad draft Yoopta JSON for a clipboard
   */
  async fetchClipboardNotepadDraft(clipboardId) {
    return await apiRequest(`/api/clipboards/${clipboardId}/notepad_draft`);
  },

  /**
   * Create/replace notepad draft Yoopta JSON for a clipboard
   */
  async putClipboardNotepadDraft(clipboardId, payload) {
    return await apiRequest(`/api/clipboards/${clipboardId}/notepad_draft`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Clear the stored notepad draft for a clipboard
   */
  async deleteClipboardNotepadDraft(clipboardId) {
    return await apiRequest(`/api/clipboards/${clipboardId}/notepad_draft`, {
      method: 'DELETE',
    });
  },

  /**
   * Save the clipboard notepad as a shared YooptaDocument
   */
  async saveClipboardAsDocument(clipboardId, payload = {}) {
    return await apiRequest(`/api/clipboards/${clipboardId}/save_as_document`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // =========================================================================
  // Notebooks (DocumentCollection-based - new API)
  // =========================================================================

  /**
   * Fetch notebooks for a workspace
   */
  async fetchNotebooks({ workspace_id, include_recent = false } = {}) {
    if (!workspace_id) {
      throw new Error('workspace_id is required to fetch notebooks');
    }

    const params = new URLSearchParams({
      workspace_id: workspace_id.toString(),
    });

    if (include_recent) {
      params.append('include_recent', 'true');
    }

    return await apiRequest(`/api/notebooks/?${params.toString()}`);
  },

  /**
   * Create and optionally activate a notebook
   */
  async createNotebook(payload) {
    return await apiRequest('/api/notebooks/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch notebook detail (optionally including items)
   */
  async fetchNotebook(notebookId, { include_items = false } = {}) {
    const params = new URLSearchParams();
    if (include_items) {
      params.append('include_items', 'true');
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/notebooks/${notebookId}${suffix}`);
  },

  /**
   * Activate a notebook
   */
  async activateNotebook(notebookId) {
    return await apiRequest(`/api/notebooks/${notebookId}/activate`, {
      method: 'POST',
    });
  },

  /**
   * Fetch notebook items
   */
  async fetchNotebookItems(notebookId) {
    return await apiRequest(`/api/notebooks/${notebookId}/items`);
  },

  /**
   * Add item to notebook
   */
  async addNotebookItem(notebookId, payload) {
    return await apiRequest(`/api/notebooks/${notebookId}/items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Delete notebook item
   */
  async deleteNotebookItem(notebookId, itemId) {
    return await apiRequest(`/api/notebooks/${notebookId}/items/${itemId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Reorder notebook items
   */
  async reorderNotebookItems(notebookId, items) {
    return await apiRequest(`/api/notebooks/${notebookId}/items/reorder`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    });
  },

  /**
   * Export notebook to specified format (default: markdown)
   */
  async exportNotebook(notebookId, { format = 'markdown' } = {}) {
    const params = new URLSearchParams({ format });
    return await apiRequest(`/api/notebooks/${notebookId}/export?${params.toString()}`);
  },

  /**
   * Fetch notepad draft Yoopta JSON for a notebook
   */
  async fetchNotebookNotepadDraft(notebookId) {
    return await apiRequest(`/api/notebooks/${notebookId}/notepad_draft`);
  },

  /**
   * Create/replace notepad draft Yoopta JSON for a notebook
   */
  async putNotebookNotepadDraft(notebookId, payload) {
    return await apiRequest(`/api/notebooks/${notebookId}/notepad_draft`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Clear the stored notepad draft for a notebook
   */
  async deleteNotebookNotepadDraft(notebookId) {
    return await apiRequest(`/api/notebooks/${notebookId}/notepad_draft`, {
      method: 'DELETE',
    });
  },

  /**
   * Save the notebook notepad as a shared YooptaDocument
   */
  async saveNotebookAsDocument(notebookId, payload = {}) {
    return await apiRequest(`/api/notebooks/${notebookId}/save_as_document`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch system settings (public configuration)
   */
  async fetchSystemSettings() {
    return await apiRequest('/api/system/settings');
  },

  // =========================================================================
  // Agent Tools
  // =========================================================================

  /**
   * Fetch all available tools and their status for a project
   *
   * @param {number} projectId - Project ID
   * @returns {Promise<Array>} List of tools with status info
   */
  async fetchProjectTools(projectId) {
    if (!projectId) {
      throw new Error('projectId is required to fetch tools');
    }
    return await apiRequest(`/api/agents/tools?project_id=${projectId}`);
  },

  /**
   * Enable a tool for a project
   *
   * @param {number} projectId - Project ID
   * @param {string} toolName - Tool name to enable
   * @returns {Promise<Object>} Updated tool status
   */
  async enableTool(projectId, toolName) {
    if (!projectId || !toolName) {
      throw new Error('projectId and toolName are required');
    }
    return await apiRequest(`/api/agents/tools/${toolName}/enable?project_id=${projectId}`, {
      method: 'POST',
    });
  },

  /**
   * Disable a tool for a project
   *
   * @param {number} projectId - Project ID
   * @param {string} toolName - Tool name to disable
   * @returns {Promise<Object>} Updated tool status
   */
  async disableTool(projectId, toolName) {
    if (!projectId || !toolName) {
      throw new Error('projectId and toolName are required');
    }
    return await apiRequest(`/api/agents/tools/${toolName}/disable?project_id=${projectId}`, {
      method: 'POST',
    });
  },

  /**
   * Save a tool-generated artifact to the document library
   *
   * @param {Object} params
   * @param {string} params.artifact_type - Type of artifact (image, code, document, diagram)
   * @param {string} params.file_path - Path to the artifact file
   * @param {number} params.workspace_id - Workspace ID to save to
   * @param {string} [params.title] - Optional display title
   * @param {string} [params.mime_type] - Optional MIME type
   * @param {number} [params.folder_id] - Optional folder ID
   * @returns {Promise<Object>} Response with success, document_id, document_type, message
   */
  async saveToolArtifact({
    artifact_type,
    file_path,
    workspace_id,
    title = null,
    mime_type = null,
    folder_id = null,
  }) {
    const payload = {
      artifact_type,
      file_path,
      workspace_id,
    }

    if (title !== null) {
      payload.title = title
    }
    if (mime_type !== null) {
      payload.mime_type = mime_type
    }
    if (folder_id !== null) {
      payload.folder_id = folder_id
    }

    return await apiRequest('/api/documents/from-artifact', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Update tool configuration for a project
   *
   * @param {number} projectId - Project ID
   * @param {string} toolName - Tool name to configure
   * @param {Object} config - Configuration overrides
   * @returns {Promise<Object>} Updated tool status
   */
  async updateToolConfig(projectId, toolName, config) {
    if (!projectId || !toolName) {
      throw new Error('projectId and toolName are required');
    }
    return await apiRequest(`/api/agents/tools/${toolName}/config?project_id=${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify({ config_overrides: config }),
    });
  },

  /**
   * Get agent routing info for a given context
   *
   * @param {Object} context - Agent context
   * @param {number} context.project_id - Project ID
   * @param {number} [context.workspace_id] - Workspace ID
   * @param {string} [context.view_type] - View type
   * @param {number} [context.document_id] - Document ID
   * @param {Array<number>} [context.document_ids] - Multiple document IDs
   * @returns {Promise<Object>} Routing info with agent type and tools
   */
  async getAgentRouteInfo(context) {
    return await apiRequest('/api/agents/chat/route-info', {
      method: 'POST',
      body: JSON.stringify(context),
    });
  },

  // =========================================================================
  // Agent Skills
  // =========================================================================

  /**
   * Fetch registered agent skills
   *
   * @param {Object} params
   * @param {string} [params.context] - Optional context filter (e.g., "chat")
   * @returns {Promise<Object>} Response with skills array
   */
  async fetchRegisteredSkills({ context = null } = {}) {
    const params = new URLSearchParams();
    if (context) {
      params.append('context', context);
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/agents/skills${suffix}`);
  },

  // =========================================================================
  // Webhooks (Platform Connections)
  // =========================================================================

  /**
   * Fetch webhook connections
   *
   * @param {Object} params
   * @param {number} [params.project_id] - Optional project filter
   * @param {boolean} [params.include_secret] - Include webhook secret in response
   * @returns {Promise<Object>} Response with connections array
   */
  async fetchWebhookConnections({ project_id = null, include_secret = false } = {}) {
    const params = new URLSearchParams();
    params.append('platform_type', 'webhook');
    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }
    if (include_secret) {
      params.append('include_secret', 'true');
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/platform/connections${suffix}`);
  },

  /**
   * Create a webhook connection
   *
   * @param {Object} payload
   * @param {string} payload.name - Connection name
   * @param {string} [payload.description] - Optional description
   * @param {number} [payload.project_id] - Optional project ID
   * @param {Object} [payload.config] - Webhook config
   * @returns {Promise<Object>} Created connection
   */
  async createWebhookConnection({ name, description = '', project_id = null, config = {} }) {
    return await apiRequest('/api/platform/connections', {
      method: 'POST',
      body: JSON.stringify({
        platform_type: 'webhook',
        name,
        description,
        project_id,
        config,
      }),
    });
  },

  /**
   * Update a webhook connection
   *
   * @param {number} connectionId - Connection ID
   * @param {Object} payload - Update payload (name, description, status, config)
   * @param {boolean} [include_secret] - Include webhook secret in response
   * @returns {Promise<Object>} Updated connection
   */
  async updateWebhookConnection(connectionId, payload, include_secret = false) {
    if (!connectionId) {
      throw new Error('connectionId is required');
    }
    const suffix = include_secret ? '?include_secret=true' : '';
    return await apiRequest(`/api/platform/connections/${connectionId}${suffix}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Delete a webhook connection
   *
   * @param {number} connectionId - Connection ID
   * @returns {Promise<Object>} Delete response
   */
  async deleteWebhookConnection(connectionId) {
    if (!connectionId) {
      throw new Error('connectionId is required');
    }
    return await apiRequest(`/api/platform/connections/${connectionId}`, {
      method: 'DELETE',
    });
  },

  // =========================================================================
  // Email Thread Attachments
  // =========================================================================

  /**
   * Fetch attachments collection for an email thread
   *
   * @param {number} threadId - ID of the email thread
   * @returns {Promise<Object>} Attachment collection with items
   */
  async fetchEmailThreadAttachments(threadId) {
    return await apiRequest(`/api/email/threads/${threadId}/attachments/`);
  },

  // =========================================================================
  // Flows/Workflows
  // =========================================================================

  /**
   * Fetch all available workflows
   *
   * @returns {Promise<Array>} List of workflow definitions
   */
  async fetchWorkflows() {
    return await apiRequest('/api/flows/workflows');
  },

  /**
   * Fetch workflow runs with optional filters
   *
   * @param {Object} params - Query parameters
   * @param {string} [params.status] - Filter by status (pending, running, completed, failed, cancelled)
   * @param {string} [params.workflow_slug] - Filter by workflow slug
   * @param {number} [params.page] - Page number (1-indexed)
   * @param {number} [params.per_page] - Items per page
   * @returns {Promise<Object>} Paginated list of workflow runs
   */
  async fetchWorkflowRuns(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append('status', params.status);
    if (params.workflow_slug) queryParams.append('workflow_slug', params.workflow_slug);
    if (params.page) queryParams.append('page', params.page);
    if (params.per_page) queryParams.append('per_page', params.per_page);

    const queryString = queryParams.toString();
    const url = queryString ? `/api/flows/runs?${queryString}` : '/api/flows/runs';
    return await apiRequest(url);
  },

  /**
   * Fetch a single workflow run by ID
   *
   * @param {string} runId - The workflow run ID
   * @returns {Promise<Object>} Workflow run details
   */
  async fetchWorkflowRun(runId) {
    return await apiRequest(`/api/flows/runs/${runId}`);
  },

  /**
   * Execute a workflow
   *
   * @param {string} slug - Workflow slug
   * @param {Object} inputs - Workflow inputs
   * @param {Object} options - Execution options
   * @param {boolean} [options.background] - Run in background
   * @param {number} [options.project_id] - Project ID
   * @param {number} [options.workspace_id] - Workspace ID
   * @returns {Promise<Object>} Workflow run response
   */
  async runWorkflow(slug, inputs = {}, options = {}) {
    return await apiRequest(`/api/flows/workflows/${slug}/run`, {
      method: 'POST',
      body: JSON.stringify({
        inputs,
        background: options.background || false,
        project_id: options.project_id,
        workspace_id: options.workspace_id,
      }),
    });
  },

  // =========================================================================
  // Event Triggers
  // =========================================================================

  /**
   * Fetch event triggers with optional filters
   *
   * @param {Object} params
   * @param {string} [params.event_type] - Filter by event type (e.g., 'documents_selected')
   * @param {number} [params.project_id] - Filter by project ID
   * @returns {Promise<Array>} List of event triggers
   */
  async fetchEventTriggers({ event_type = null, project_id = null } = {}) {
    const params = new URLSearchParams();
    if (event_type) {
      params.append('event_type', event_type);
    }
    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/events/triggers${suffix}`);
  },

  /**
   * Fetch available event types
   *
   * @returns {Promise<Object>} Object with event_types array
   */
  async fetchEventTypes() {
    return await apiRequest('/api/events/types');
  },

  /**
   * Manually dispatch an event trigger with document IDs
   *
   * @param {number} triggerId - ID of the trigger to dispatch
   * @param {Object} payload
   * @param {Array<number>} payload.document_ids - Document IDs to process
   * @returns {Promise<Object>} EventTriggerRun response
   */
  async dispatchEventTrigger(triggerId, payload) {
    return await apiRequest(`/api/events/triggers/${triggerId}/dispatch`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch event trigger runs with optional filters
   *
   * @param {Object} params
   * @param {string} [params.status] - Filter by status (pending, running, completed, failed)
   * @param {number} [params.project_id] - Filter by project ID
   * @param {number} [params.limit] - Max number of runs to return (default 50)
   * @returns {Promise<Array>} List of event trigger runs
   */
  async fetchEventTriggerRuns({ status = null, project_id = null, limit = 50 } = {}) {
    const params = new URLSearchParams();
    if (status) {
      params.append('status', status);
    }
    if (project_id !== null) {
      params.append('project_id', project_id.toString());
    }
    if (limit) {
      params.append('limit', limit.toString());
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return await apiRequest(`/api/events/runs${suffix}`);
  },

  /**
   * Fetch a specific event trigger run by run_id
   *
   * @param {string} runId - UUID of the run
   * @returns {Promise<Object>} EventTriggerRun details
   */
  async fetchEventTriggerRun(runId) {
    return await apiRequest(`/api/events/runs/${runId}`);
  },
};

export default api;
