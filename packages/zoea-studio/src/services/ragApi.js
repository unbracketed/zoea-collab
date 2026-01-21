/**
 * RAG API Client Service
 *
 * API client for Document RAG endpoints.
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
      if (cookie.substring(0, name.length + 1) === name + '=') {
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
    credentials: 'include',
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

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // If response isn't JSON, use status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * RAG API methods
 */
const ragApi = {
  /**
   * Create a new RAG session.
   *
   * @param {Object} payload - Session creation parameters
   * @param {string} payload.context_type - Type: 'single', 'folder', 'clipboard', 'collection'
   * @param {number} payload.context_id - ID of the context item
   * @param {number} payload.project_id - Project ID
   * @param {number} payload.workspace_id - Workspace ID
   * @returns {Promise<Object>} Created session
   */
  createSession: async (payload) => {
    return apiRequest('/api/rag/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Get session details with messages.
   *
   * @param {string} sessionId - Session UUID
   * @returns {Promise<Object>} Session details with messages
   */
  getSession: async (sessionId) => {
    return apiRequest(`/api/rag/sessions/${sessionId}`);
  },

  /**
   * Send a message to the RAG agent.
   *
   * @param {string} sessionId - Session UUID
   * @param {Object} payload - Chat parameters
   * @param {string} payload.message - User's message
   * @param {boolean} [payload.include_sources=true] - Include sources in response
   * @returns {Promise<Object>} Agent response
   */
  chat: async (sessionId, payload) => {
    return apiRequest(`/api/rag/sessions/${sessionId}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Close a RAG session.
   *
   * @param {string} sessionId - Session UUID
   * @returns {Promise<Object>} Closure confirmation
   */
  closeSession: async (sessionId) => {
    return apiRequest(`/api/rag/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  },
};

export default ragApi;
