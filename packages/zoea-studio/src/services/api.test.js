import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import api from './api';

// Get the API base URL from the environment (same as the actual API service)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

describe('API Service', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.clearAllMocks();
  });

  describe('fetchConversations', () => {
    it('should fetch conversations successfully', async () => {
      const mockData = {
        conversations: [
          { id: 1, title: 'Test Chat', message_count: 5 },
        ],
        total: 1,
      };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockData,
      });

      const result = await api.fetchConversations();

      expect(result).toEqual(mockData);
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/api/conversations`,
        expect.objectContaining({
          credentials: 'include',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should handle fetch errors', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Server error' }),
      });

      await expect(api.fetchConversations()).rejects.toThrow('Server error');
    });
  });

  describe('fetchConversation', () => {
    it('should fetch a specific conversation with messages', async () => {
      const mockData = {
        id: 1,
        title: 'Test Chat',
        messages: [
          { id: 1, role: 'user', content: 'Hello' },
          { id: 2, role: 'assistant', content: 'Hi!' },
        ],
      };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockData,
      });

      const result = await api.fetchConversation(1);

      expect(result).toEqual(mockData);
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/api/conversations/1`,
        expect.any(Object)
      );
    });
  });

  describe('sendMessage', () => {
    it('should send a message successfully', async () => {
      const mockResponse = {
        response: 'Hello there!',
        agent_name: 'ZoeaAssistant',
        conversation_id: 1,
      };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockResponse,
      });

      const result = await api.sendMessage({
        message: 'Hello',
        agent_name: 'ZoeaAssistant',
      });

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/api/chat`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            message: 'Hello',
            agent_name: 'ZoeaAssistant',
            instructions: 'You are a helpful AI assistant for Zoea Studio.',
            debug: false,
          }),
        })
      );
    });

    it('should include conversation_id when provided', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });

      await api.sendMessage({
        message: 'Hello',
        conversation_id: 42,
      });

      const callArgs = global.fetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);

      expect(body.conversation_id).toBe(42);
    });

    it('should not include conversation_id when null', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });

      await api.sendMessage({
        message: 'Hello',
        conversation_id: null,
      });

      const callArgs = global.fetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);

      expect(body).not.toHaveProperty('conversation_id');
    });
  });

  describe('checkAuth', () => {
    it('should return authentication status', async () => {
      const mockAuth = {
        authenticated: true,
        username: 'testuser',
        organization: { id: 1, name: 'Test Org' },
      };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockAuth,
      });

      const result = await api.checkAuth();

      expect(result).toEqual(mockAuth);
    });

    it('should handle 401 errors gracefully', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'HTTP 401: Unauthorized' }),
      });

      // The checkAuth method catches 401/403 errors and returns a default object
      // The error message must contain '401' or '403' to be caught
      const result = await api.checkAuth();

      expect(result).toEqual({
        authenticated: false,
        username: null,
        organization: null,
      });
    });
  });
});
