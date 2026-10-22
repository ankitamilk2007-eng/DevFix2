/**
 * DevFix AI — Centralized API Client Module
 * 
 * Handles all HTTP communication with the Flask backend.
 * Provides honest offline detection and error reporting without pretending
 * services are online when they are not.
 */

const STORAGE_KEY_API_URL = 'devfix_api_url';
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:5000';

class ApiService {
  constructor() {
    let stored = typeof localStorage !== 'undefined' 
      ? localStorage.getItem(STORAGE_KEY_API_URL) 
      : null;
    
    // Normalize localhost to 127.0.0.1 for fast, reliable local communication on Windows
    if (stored && stored.includes('localhost:5000')) {
      stored = stored.replace('localhost:5000', '127.0.0.1:5000');
    }

    this.baseUrl = stored || DEFAULT_BACKEND_URL;
    this.isOnline = false;
    this.lastChecked = null;
    this.listeners = [];
  }

  /**
   * Updates the configured backend base URL
   */
  setBaseUrl(url) {
    if (!url || !url.trim()) {
      this.baseUrl = DEFAULT_BACKEND_URL;
    } else {
      let cleaned = url.trim().replace(/\/+$/, '');
      if (cleaned.includes('localhost:5000')) {
        cleaned = cleaned.replace('localhost:5000', '127.0.0.1:5000');
      }
      this.baseUrl = cleaned;
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY_API_URL, this.baseUrl);
    }
    this.notifyStatusChange();
  }

  getBaseUrl() {
    return this.baseUrl;
  }

  /**
   * Register a callback for connection status updates
   */
  onStatusChange(callback) {
    if (typeof callback === 'function') {
      this.listeners.push(callback);
    }
  }

  notifyStatusChange() {
    this.listeners.forEach(cb => {
      try {
        cb({ isOnline: this.isOnline, baseUrl: this.baseUrl, lastChecked: this.lastChecked });
      } catch (err) {
        console.error('Error in status change listener:', err);
      }
    });
  }

  /**
   * Pings the Flask backend health endpoint with a reliable timeout
   * Returns: { online: boolean, status: string, latencyMs: number, error?: string }
   */
  async checkHealth(timeoutMs = 4000) {
    const startTime = performance.now();
    const urlsToTry = [this.baseUrl];
    if (this.baseUrl.includes('127.0.0.1:5000')) {
      urlsToTry.push(this.baseUrl.replace('127.0.0.1:5000', 'localhost:5000'));
    } else if (this.baseUrl.includes('localhost:5000')) {
      urlsToTry.push(this.baseUrl.replace('localhost:5000', '127.0.0.1:5000'));
    }

    let lastError = null;

    for (const targetUrl of urlsToTry) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetch(`${targetUrl}/api/health`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          signal: controller.signal
        });
        clearTimeout(timeoutId);

        const latency = Math.round(performance.now() - startTime);

        if (response.ok) {
          const data = await response.json().catch(() => ({}));
          this.isOnline = true;
          this.baseUrl = targetUrl;
          this.lastChecked = new Date();
          this.notifyStatusChange();
          return {
            online: true,
            status: 'online',
            latencyMs: latency,
            data
          };
        } else {
          lastError = `Backend responded with HTTP ${response.status}`;
        }
      } catch (err) {
        clearTimeout(timeoutId);
        const isTimeout = err.name === 'AbortError';
        lastError = isTimeout ? `Request timed out after ${timeoutMs}ms` : 'Connection refused. Is Flask running?';
      }
    }

    this.isOnline = false;
    this.lastChecked = new Date();
    this.notifyStatusChange();

    return {
      online: false,
      status: lastError?.includes('timed out') ? 'timeout' : 'unreachable',
      error: lastError || 'Connection failed'
    };
  }

  /**
   * Centralized HTTP request helper
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(options.headers || {})
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw {
          status: response.status,
          message: data?.error || data?.message || `Request failed with status ${response.status}`,
          data
        };
      }

      return data;
    } catch (err) {
      if (err.status) {
        throw err;
      }
      throw {
        status: 0,
        message: err.message || 'Network error: could not connect to Flask backend',
        isNetworkError: true
      };
    }
  }

  /**
   * Supported languages from backend
   */
  async getLanguages() {
    return this.request('/api/languages');
  }

  /**
   * Submit code & traceback for diagnosis
   */
  async diagnose({ language, code, traceback, context }) {
    return this.request('/api/diagnose', {
      method: 'POST',
      body: JSON.stringify({ language, code, traceback, context })
    });
  }

  /**
   * Request a minimal code patch for the diagnosed issue
   */
  async proposeFix({ language, code, traceback, diagnosisId, diagnosis }) {
    return this.request('/api/propose-fix', {
      method: 'POST',
      body: JSON.stringify({ language, code, traceback, diagnosisId, diagnosis })
    });
  }

  /**
   * Trigger controlled test verification for an approved fix
   */
  async verify({ language, originalCode, proposedCode, tests }) {
    return this.request('/api/verify', {
      method: 'POST',
      body: JSON.stringify({ language, originalCode, proposedCode, tests })
    });
  }

  /**
   * Fetch saved sessions from backend
   */
  async getSessions() {
    return this.request('/api/sessions');
  }

  /**
   * Fetch single session by ID
   */
  async getSession(id) {
    return this.request(`/api/sessions/${encodeURIComponent(id)}`);
  }

  /**
   * Delete session by ID
   */
  async deleteSession(id) {
    return this.request(`/api/sessions/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    });
  }
}

export const api = new ApiService();
