/**
 * API Client for DreamPath Backend
 *
 * Replaces Supabase with direct PostgreSQL access via FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class APIClient {
  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.agent = 'dreampath-agent';
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
  async invoke({ message, userId, threadId = null, model = null }) {
    const payload = {
      message,
      user_id: userId,
      thread_id: threadId,
      model: model,
    };

    const response = await fetch(`${this.baseUrl}/${this.agent}/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
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
  async* stream({ message, userId, threadId = null, model = null, streamTokens = true }) {
    const payload = {
      message,
      user_id: userId,
      thread_id: threadId,
      model: model,
      stream_tokens: streamTokens,
    };

    const response = await fetch(`${this.baseUrl}/${this.agent}/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
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
    const response = await fetch(`${this.baseUrl}/history`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
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
    const response = await fetch(`${this.baseUrl}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
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
   * Get user's course path from PostgreSQL
   * Returns full course path data including course_bank
   */
  async getCoursePath(userId) {
    const response = await fetch(`${this.baseUrl}/coursepath/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null; // No course path found
      }
      throw new Error('Failed to fetch course path');
    }

    return response.json();
  }

  /**
   * Get user's course path visualization (text format)
   */
  async getCoursePathVisualization(userId) {
    const response = await fetch(`${this.baseUrl}/coursepath/${userId}/visualization`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error('Failed to fetch course path visualization');
    }

    return response.json();
  }

  /**
   * Delete user's course path
   */
  async deleteCoursePath(userId) {
    const response = await fetch(`${this.baseUrl}/coursepath/${userId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to delete course path');
    }
  }

  /**
   * Get user's profile from PostgreSQL
   */
  async getProfile(userId) {
    const response = await fetch(`${this.baseUrl}/profile/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null; // No profile found
      }
      throw new Error('Failed to fetch profile');
    }

    return response.json();
  }

  /**
   * Update user's profile in PostgreSQL
   */
  async updateProfile(userId, profileData) {
    const response = await fetch(`${this.baseUrl}/profile/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(profileData),
    });

    if (!response.ok) {
      throw new Error('Failed to update profile');
    }

    return response.json();
  }

  /**
   * Thread Management - LocalStorage helpers
   */

  /**
   * Get all threads for a user from localStorage
   */
  getUserThreads(userId) {
    const key = `dreampath_threads_${userId}`;
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : [];
  }

  /**
   * Save threads for a user to localStorage
   */
  saveUserThreads(userId, threads) {
    const key = `dreampath_threads_${userId}`;
    localStorage.setItem(key, JSON.stringify(threads));
  }

  /**
   * Get current thread ID for a user
   */
  getCurrentThreadId(userId) {
    const key = `dreampath_current_thread_${userId}`;
    return localStorage.getItem(key);
  }

  /**
   * Set current thread ID for a user
   */
  setCurrentThreadId(userId, threadId) {
    const key = `dreampath_current_thread_${userId}`;
    localStorage.setItem(key, threadId);
  }

  /**
   * Create a new thread
   */
  createThread(userId, threadId = null) {
    const id = threadId || `thread-${Date.now()}`;
    const threads = this.getUserThreads(userId);
    const label = `Discussion #${threads.length + 1}`;

    const newThread = {
      id,
      label,
      createdAt: new Date().toISOString(),
      lastMessageAt: new Date().toISOString(),
    };

    threads.unshift(newThread); // Add to beginning
    this.saveUserThreads(userId, threads);
    this.setCurrentThreadId(userId, id);

    return newThread;
  }

  /**
   * Update thread's last message timestamp
   */
  updateThreadTimestamp(userId, threadId) {
    const threads = this.getUserThreads(userId);
    const thread = threads.find(t => t.id === threadId);
    if (thread) {
      thread.lastMessageAt = new Date().toISOString();
      this.saveUserThreads(userId, threads);
    }
  }

  /**
   * Switch to a different thread
   */
  switchThread(userId, threadId) {
    this.setCurrentThreadId(userId, threadId);
  }
}

// Singleton instance
export const apiClient = new APIClient();

export default APIClient;
