/**
 * API Client for DreamPath Backend with Supabase Auth
 *
 * This version includes Supabase JWT authentication
 */

import { createClient } from '@supabase/supabase-js';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

const supabase = createClient(supabaseUrl, supabaseAnonKey);

class APIClient {
  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.agent = 'dreampath-agent';
  }

  /**
   * Get authorization headers with Supabase JWT
   */
  async getAuthHeaders() {
    const { data: { session } } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error('Not authenticated');
    }

    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
    };
  }

  /**
   * Get current user ID from Supabase session
   */
  async getUserId() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.user?.id;
  }

  /**
   * Get service metadata
   */
  async getInfo() {
    const response = await fetch(`${this.baseUrl}/info`);
    if (!response.ok) {
      throw new Error('Failed to fetch service info');
    }
    return response.json();
  }

  /**
   * Send a message to the agent and get a complete response
   */
  async invoke({ message, threadId = null, model = null }) {
    const headers = await this.getAuthHeaders();
    const userId = await this.getUserId();

    const payload = {
      message,
      user_id: userId,
      thread_id: threadId,
      model: model,
    };

    const response = await fetch(`${this.baseUrl}/${this.agent}/invoke`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Invoke failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Stream messages from the agent
   * Returns an async generator that yields messages
   */
  async* stream({ message, threadId = null, model = null, streamTokens = true }) {
    const headers = await this.getAuthHeaders();
    const userId = await this.getUserId();

    const payload = {
      message,
      user_id: userId,
      thread_id: threadId,
      model: model,
      stream_tokens: streamTokens,
    };

    const response = await fetch(`${this.baseUrl}/${this.agent}/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Stream failed: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);

          if (data === '[DONE]') {
            return;
          }

          try {
            const parsed = JSON.parse(data);

            if (parsed.type === 'token') {
              yield parsed.content;
            } else if (parsed.type === 'message') {
              yield parsed.content;
            } else if (parsed.type === 'error') {
              throw new Error(parsed.content);
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e);
          }
        }
      }
    }
  }

  /**
   * Get chat history for a thread
   */
  async getHistory(threadId) {
    const headers = await this.getAuthHeaders();

    const response = await fetch(`${this.baseUrl}/history`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ thread_id: threadId }),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch history');
    }

    return response.json();
  }

  /**
   * Submit feedback for a run
   */
  async createFeedback({ runId, key, score, kwargs = {} }) {
    const headers = await this.getAuthHeaders();

    const response = await fetch(`${this.baseUrl}/feedback`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        run_id: runId,
        key,
        score,
        kwargs,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to submit feedback');
    }

    return response.json();
  }

  /**
   * Get user profile from local PostgreSQL
   */
  async getProfile() {
    const headers = await this.getAuthHeaders();
    const userId = await this.getUserId();

    const response = await fetch(`${this.baseUrl}/profile/${userId}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      throw new Error('Failed to fetch profile');
    }

    return response.json();
  }

  /**
   * Update user profile in local PostgreSQL
   */
  async updateProfile(profileData) {
    const headers = await this.getAuthHeaders();
    const userId = await this.getUserId();

    const response = await fetch(`${this.baseUrl}/profile/${userId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(profileData),
    });

    if (!response.ok) {
      throw new Error('Failed to update profile');
    }

    return response.json();
  }
}

// Singleton instance
export const apiClient = new APIClient();

export default APIClient;
