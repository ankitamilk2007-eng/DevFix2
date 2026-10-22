/**
 * DevFix AI — History & Persistence Manager
 * 
 * Manages local storage session history, search, filtering, and dashboard statistics.
 * Connects with confirmation modals for safe session deletion.
 */

import { escapeHtml, formatTimestamp } from './utils.js';

const STORAGE_KEY_SESSIONS = 'devfix_sessions';

export class HistoryManager {
  constructor() {
    this.sessions = this.loadFromStorage();
    this.currentFilter = 'all';
    this.searchQuery = '';
    this.pendingDeleteId = null;
    this.pendingClearAll = false;
    this.listeners = [];
  }

  loadFromStorage() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY_SESSIONS);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.warn('Failed to parse sessions from localStorage:', err);
      return [];
    }
  }

  saveToStorage() {
    if (typeof localStorage === 'undefined') {
      this.notify();
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY_SESSIONS, JSON.stringify(this.sessions));
      this.notify();
    } catch (err) {
      console.error('Failed to save sessions to localStorage:', err);
    }
  }

  subscribe(callback) {
    if (typeof callback === 'function') {
      this.listeners.push(callback);
    }
  }

  notify() {
    this.listeners.forEach(cb => {
      try {
        cb(this.getStats());
      } catch (err) {
        console.error('Error in history listener:', err);
      }
    });
  }

  /**
   * Saves or updates a session in history
   */
  saveSession(session) {
    if (!session || !session.id) return;

    const existingIndex = this.sessions.findIndex(s => s.id === session.id);
    const sessionRecord = {
      ...session,
      updatedAt: new Date().toISOString()
    };

    if (existingIndex >= 0) {
      this.sessions[existingIndex] = sessionRecord;
    } else {
      this.sessions.unshift(sessionRecord);
    }

    this.saveToStorage();
    return sessionRecord;
  }

  /**
   * Retrieves a session by ID
   */
  getSession(id) {
    return this.sessions.find(s => s.id === id) || null;
  }

  /**
   * Prepares deletion confirmation
   */
  promptDeleteSession(id) {
    const session = this.getSession(id);
    if (!session) return null;
    this.pendingDeleteId = id;
    this.pendingClearAll = false;
    return session;
  }

  /**
   * Prepares clear all confirmation
   */
  promptClearAll() {
    this.pendingDeleteId = null;
    this.pendingClearAll = true;
  }

  /**
   * Executes confirmed deletion
   */
  confirmDeletion() {
    if (this.pendingClearAll) {
      this.sessions = [];
      this.pendingClearAll = false;
      this.saveToStorage();
      return { success: true, clearedAll: true };
    } else if (this.pendingDeleteId) {
      const id = this.pendingDeleteId;
      this.sessions = this.sessions.filter(s => s.id !== id);
      this.pendingDeleteId = null;
      this.saveToStorage();
      return { success: true, deletedId: id };
    }
    return { success: false };
  }

  cancelDeletion() {
    this.pendingDeleteId = null;
    this.pendingClearAll = false;
  }

  /**
   * Calculates honest statistics from actual session records
   */
  getStats() {
    const total = this.sessions.length;
    let verified = 0;
    let failed = 0;
    let unverified = 0;

    this.sessions.forEach(s => {
      const status = s.verificationStatus || (s.verification ? s.verification.status : 'unverified');
      if (status === 'verified') verified++;
      else if (status === 'failed') failed++;
      else unverified++;
    });

    return {
      total,
      verified,
      failed,
      unverified
    };
  }

  /**
   * Returns filtered and searched sessions list
   */
  getFilteredSessions() {
    const query = this.searchQuery.trim().toLowerCase();

    return this.sessions.filter(s => {
      // Status filter
      const vStatus = s.verificationStatus || (s.verification ? s.verification.status : 'unverified');
      if (this.currentFilter !== 'all' && vStatus !== this.currentFilter) {
        return false;
      }

      // Search query filter
      if (query) {
        const titleMatch = (s.title || '').toLowerCase().includes(query);
        const errTypeMatch = (s.diagnosis?.errorType || '').toLowerCase().includes(query);
        const fileMatch = (s.diagnosis?.fileName || '').toLowerCase().includes(query);
        const langMatch = (s.language || '').toLowerCase().includes(query);
        return titleMatch || errTypeMatch || fileMatch || langMatch;
      }

      return true;
    });
  }

  /**
   * Renders the History list view
   */
  renderHistoryView(container, callbacks) {
    const filtered = this.getFilteredSessions();
    const stats = this.getStats();

    // Update filter counts
    const countAllEl = document.getElementById('filterCountAll');
    const countVerEl = document.getElementById('filterCountVerified');
    const countFailEl = document.getElementById('filterCountFailed');
    const countUnverEl = document.getElementById('filterCountUnverified');
    if (countAllEl) countAllEl.textContent = stats.total;
    if (countVerEl) countVerEl.textContent = stats.verified;
    if (countFailEl) countFailEl.textContent = stats.failed;
    if (countUnverEl) countUnverEl.textContent = stats.unverified;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <p class="empty-state-title">No matching debugging sessions found</p>
          <p class="empty-state-desc">
            ${this.sessions.length === 0 
              ? 'You have not conducted any debugging sessions yet.' 
              : 'Try clearing your search query or choosing a different status filter.'}
          </p>
          ${this.sessions.length === 0 ? `
            <button class="btn btn-primary btn-sm" id="historyEmptyStartBtn">+ Start Debugging</button>
          ` : ''}
        </div>
      `;
      const startBtn = container.querySelector('#historyEmptyStartBtn');
      if (startBtn && callbacks.onStartNew) {
        startBtn.addEventListener('click', callbacks.onStartNew);
      }
      return;
    }

    container.innerHTML = filtered.map(session => {
      const vStatus = session.verificationStatus || (session.verification ? session.verification.status : 'unverified');
      let pillClass = 'pill-unverified';
      let pillText = 'Unverified';

      if (vStatus === 'verified') {
        pillClass = 'pill-verified';
        pillText = '✓ Verified';
      } else if (vStatus === 'failed') {
        pillClass = 'pill-failed';
        pillText = '✕ Failed';
      }

      return `
        <div class="history-row" data-id="${session.id}">
          <div class="history-title-group">
            <span class="history-item-title">${escapeHtml(session.title || 'Python Session')}</span>
            <span class="history-item-summary">${escapeHtml(session.diagnosis?.summary || 'Traceback analysis')}</span>
          </div>
          <div>
            <span class="badge-neutral" style="font-family: var(--font-mono); font-size: 0.75rem;">
              ${escapeHtml((session.language || 'python').toUpperCase())}
            </span>
          </div>
          <div class="col-date" style="color: var(--text-muted); font-size: 0.8125rem;">
            ${formatTimestamp(session.createdAt)}
          </div>
          <div class="col-status">
            <span class="status-pill ${pillClass}">
              ${pillText}
            </span>
          </div>
          <div class="history-actions-cell">
            <button class="btn btn-xs btn-secondary btn-open-session" data-id="${session.id}">
              Open →
            </button>
            <button class="btn btn-xs btn-ghost btn-delete-session" data-id="${session.id}" title="Delete session" style="color: var(--color-danger);">
              🗑
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Attach row button events
    container.querySelectorAll('.btn-open-session').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        if (callbacks.onOpenSession) callbacks.onOpenSession(id);
      });
    });

    container.querySelectorAll('.btn-delete-session').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        if (callbacks.onDeleteSession) callbacks.onDeleteSession(id);
      });
    });
  }

  /**
   * Renders the recent sessions on Dashboard
   */
  renderRecentDashboard(container, callbacks) {
    const recent = this.sessions.slice(0, 5);

    if (recent.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <p class="empty-state-title">No debugging sessions recorded yet</p>
          <p class="empty-state-desc">Submit your first Python traceback to begin evidence-based diagnosis.</p>
          <button class="btn btn-sm btn-primary" id="dashEmptyStartBtn">Start First Session</button>
        </div>
      `;
      const btn = container.querySelector('#dashEmptyStartBtn');
      if (btn && callbacks.onStartNew) {
        btn.addEventListener('click', callbacks.onStartNew);
      }
      return;
    }

    container.innerHTML = recent.map(session => {
      const vStatus = session.verificationStatus || (session.verification ? session.verification.status : 'unverified');
      let pillClass = 'pill-unverified';
      let pillText = 'Unverified';

      if (vStatus === 'verified') {
        pillClass = 'pill-verified';
        pillText = '✓ Verified';
      } else if (vStatus === 'failed') {
        pillClass = 'pill-failed';
        pillText = '✕ Failed';
      }

      return `
        <div class="recent-item" data-id="${session.id}">
          <div class="recent-info">
            <span class="recent-title">${escapeHtml(session.title || 'Python Session')}</span>
            <span class="recent-meta">${escapeHtml(session.diagnosis?.summary || 'Analysis')} • ${formatTimestamp(session.createdAt)}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span class="status-pill ${pillClass}">${pillText}</span>
            <button class="btn btn-xs btn-outline btn-open-recent" data-id="${session.id}">Open</button>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.btn-open-recent').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        if (callbacks.onOpenSession) callbacks.onOpenSession(id);
      });
    });
  }
}

export const history = new HistoryManager();
