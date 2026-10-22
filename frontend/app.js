/**
 * DevFix AI — Application Main Entrypoint
 * 
 * Orchestrates views, forms, validation, sessions, results rendering, and API checks.
 */

import { navigation, VIEWS } from './modules/navigation.js';
import { SUPPORTED_LANGUAGES, SAMPLE_CASES } from './modules/language-config.js';
import { debugSession, WORKFLOW_STEPS, VERIFICATION_STATUS } from './modules/debug-session.js';
import { history } from './modules/history.js';
import { renderDiagnosis, renderProposedFix, renderVerification } from './modules/results.js';
import { api } from './modules/api.js';

class DevFixApp {
  constructor() {
    this.selectedLanguage = 'python';
    this.currentLoadedSampleId = null;
    this.sampleIndex = 0;
  }

  async init() {
    // 1. Initialize Navigation
    navigation.init();

    // 2. Render Language Selector Cards
    this.renderLanguageSelector();

    // 3. Render Language Roadmap on Dashboard
    this.renderLanguageRoadmap();

    // 4. Setup Form Controls & Editor Line Numbers
    this.setupEditorControls();

    // 5. Setup Action Buttons (Dashboard, Header, Form)
    this.setupActionButtons();

    // 6. Setup History Controls (Search & Filters)
    this.setupHistoryControls();

    // 7. Setup Settings View & Ping Backend
    this.setupSettingsView();

    // 8. Subscribe to Session and History Changes
    this.setupStateSubscriptions();

    // 9. Initial Load of Dashboard Metrics & History
    this.refreshDashboard();
    this.refreshHistory();

    // 10. Check backend health honestly upon load
    this.checkBackendConnection();

    console.log('DevFix AI initialized successfully.');
  }

  /**
   * Renders the language cards in the debug submission form
   */
  renderLanguageSelector() {
    const grid = document.getElementById('languageSelectorGrid');
    if (!grid) return;

    grid.innerHTML = SUPPORTED_LANGUAGES.map(lang => {
      const isSelected = lang.id === this.selectedLanguage;
      return `
        <div class="lang-card ${lang.enabled ? 'enabled' : 'disabled'} ${isSelected ? 'selected' : ''}" 
             data-lang-id="${lang.id}" 
             tabindex="${lang.enabled ? '0' : '-1'}"
             role="button"
             aria-pressed="${isSelected}">
          <span class="lang-icon">${lang.icon}</span>
          <span class="lang-name">${lang.name}</span>
          <span class="lang-status-pill ${lang.badgeClass}">${lang.statusText}</span>
        </div>
      `;
    }).join('');

    // Attach click events
    grid.querySelectorAll('.lang-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const langId = card.getAttribute('data-lang-id');
        const langConfig = SUPPORTED_LANGUAGES.find(l => l.id === langId);

        if (!langConfig.enabled) {
          navigation.showToast(`${langConfig.name} adapter is currently in development. Only Python is enabled for this release.`, 'warning', 4000);
          return;
        }

        this.selectedLanguage = langId;
        grid.querySelectorAll('.lang-card').forEach(c => {
          const isSel = c.getAttribute('data-lang-id') === langId;
          c.classList.toggle('selected', isSel);
          c.setAttribute('aria-pressed', isSel);
        });
      });
    });
  }

  /**
   * Renders the language roadmap list on the Dashboard
   */
  renderLanguageRoadmap() {
    const list = document.getElementById('languageRoadmapList');
    if (!list) return;

    list.innerHTML = SUPPORTED_LANGUAGES.map(lang => `
      <li class="roadmap-item">
        <div class="roadmap-lang">
          <span class="roadmap-lang-icon">${lang.icon}</span>
          <span>${lang.name}</span>
        </div>
        <span class="roadmap-badge ${lang.enabled ? 'badge-active' : 'badge-coming-soon'}">
          ${lang.statusText}
        </span>
      </li>
    `).join('');
  }

  /**
   * Line numbers and line counter sync for source code textarea
   */
  setupEditorControls() {
    const codeInput = document.getElementById('sourceCodeInput');
    const lineNumbersEl = document.getElementById('codeLineNumbers');
    const counterEl = document.getElementById('codeLineCounter');

    if (codeInput && lineNumbersEl) {
      const updateLines = () => {
        const lines = codeInput.value.split('\n').length;
        if (counterEl) {
          counterEl.textContent = `${lines} ${lines === 1 ? 'line' : 'lines'}`;
        }
        let numsHtml = '';
        for (let i = 1; i <= Math.max(lines, 1); i++) {
          numsHtml += `${i}<br>`;
        }
        lineNumbersEl.innerHTML = numsHtml;
      };

      codeInput.addEventListener('input', updateLines);
      codeInput.addEventListener('scroll', () => {
        lineNumbersEl.scrollTop = codeInput.scrollTop;
      });

      // Initial count
      updateLines();
    }
  }

  /**
   * Setup UI action buttons and form submission
   */
  setupActionButtons() {
    // Start debug buttons
    const startBtns = [
      document.getElementById('headerStartBtn'),
      document.getElementById('dashStartDebugBtn'),
      document.getElementById('emptyStateStartBtn')
    ];
    startBtns.forEach(btn => {
      if (btn) btn.addEventListener('click', () => navigation.navigateTo(VIEWS.NEW_SESSION));
    });

    // Load sample buttons - directly populates sample into form on click
    const loadSampleBtns = [
      document.getElementById('dashLoadSampleBtn'),
      document.getElementById('loadSampleCaseBtn'),
      document.getElementById('alertLoadSampleBtn')
    ];
    loadSampleBtns.forEach(btn => {
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          this.loadNextSampleCase();
        });
      }
    });

    // Reset Form button
    const resetFormBtn = document.getElementById('resetFormBtn');
    if (resetFormBtn) {
      resetFormBtn.addEventListener('click', () => {
        this.resetForm();
        debugSession.reset();
        navigation.showToast('Form cleared', 'info');
      });
    }

    // View all history button
    const viewAllHistBtn = document.getElementById('dashViewAllHistoryBtn');
    if (viewAllHistBtn) {
      viewAllHistBtn.addEventListener('click', () => navigation.navigateTo(VIEWS.HISTORY));
    }

    // Resume active session button in sidebar
    const resumeBtn = document.getElementById('resumeActiveSessionBtn');
    if (resumeBtn) {
      resumeBtn.addEventListener('click', () => {
        if (debugSession.currentSession) {
          this.navigateToCurrentStep(debugSession.currentStep);
        }
      });
    }

    // Validation alert close
    const closeAlertBtn = document.getElementById('closeValidationAlertBtn');
    if (closeAlertBtn) {
      closeAlertBtn.addEventListener('click', () => {
        const alert = document.getElementById('formValidationAlert');
        if (alert) alert.style.display = 'none';
      });
    }

    // Direct event listener on Analyze Error button
    const analyzeBtn = document.getElementById('analyzeErrorBtn');
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleFormSubmit(e);
      });
    }

    // Also listen to form submit event (e.g. if Enter is pressed)
    const form = document.getElementById('debugSessionForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleFormSubmit(e);
      });
    }
  }

  /**
   * Directly loads the next curated sample bug into the form
   */
  loadNextSampleCase() {
    const sample = SAMPLE_CASES[this.sampleIndex % SAMPLE_CASES.length];
    this.sampleIndex++;
    this.loadSampleIntoForm(sample);
    navigation.navigateTo(VIEWS.NEW_SESSION);
    navigation.showToast(`Loaded sample (${sample.errorType}): ${sample.title}`, 'success', 4000);
  }

  /**
   * Loads a sample case into the debugging form
   */
  loadSampleIntoForm(sample) {
    if (!sample) return;

    this.currentLoadedSampleId = sample.id;

    const codeInput = document.getElementById('sourceCodeInput');
    const tbInput = document.getElementById('tracebackInput');
    const ctxInput = document.getElementById('expectedBehaviorInput');

    if (codeInput) {
      codeInput.value = sample.sourceCode;
      codeInput.dispatchEvent(new Event('input'));
    }
    if (tbInput) {
      tbInput.value = sample.traceback;
      tbInput.dispatchEvent(new Event('input'));
    }
    if (ctxInput) {
      ctxInput.value = sample.expectedBehavior || '';
    }

    // Ensure Python is selected
    this.selectedLanguage = sample.language || 'python';
    const grid = document.getElementById('languageSelectorGrid');
    if (grid) {
      grid.querySelectorAll('.lang-card').forEach(c => {
        const isSel = c.getAttribute('data-lang-id') === this.selectedLanguage;
        c.classList.toggle('selected', isSel);
      });
    }

    const alert = document.getElementById('formValidationAlert');
    if (alert) alert.style.display = 'none';
  }

  /**
   * Resets the form fields
   */
  resetForm() {
    this.currentLoadedSampleId = null;

    const codeInput = document.getElementById('sourceCodeInput');
    const tbInput = document.getElementById('tracebackInput');
    const ctxInput = document.getElementById('expectedBehaviorInput');
    const alert = document.getElementById('formValidationAlert');

    if (codeInput) {
      codeInput.value = '';
      codeInput.dispatchEvent(new Event('input'));
    }
    if (tbInput) {
      tbInput.value = '';
      tbInput.dispatchEvent(new Event('input'));
    }
    if (ctxInput) ctxInput.value = '';
    if (alert) alert.style.display = 'none';
  }

  /**
   * Handles debug session form submission with loading state & validation
   */
  async handleFormSubmit(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    const codeInput = document.getElementById('sourceCodeInput');
    const tbInput = document.getElementById('tracebackInput');
    const ctxInput = document.getElementById('expectedBehaviorInput');
    const alert = document.getElementById('formValidationAlert');
    const alertMsg = document.getElementById('formValidationMessage');
    const submitBtn = document.getElementById('analyzeErrorBtn');
    const spinner = document.getElementById('analyzeSpinner');
    const btnText = document.getElementById('analyzeBtnText');

    const code = codeInput ? codeInput.value : '';
    const traceback = tbInput ? tbInput.value : '';
    const context = ctxInput ? ctxInput.value : '';

    // Validate
    const validation = debugSession.validateInput({
      language: this.selectedLanguage,
      code,
      traceback
    });

    if (!validation.isValid) {
      if (alert && alertMsg) {
        alertMsg.innerHTML = validation.errors.map(err => `<div>• ${err}</div>`).join('');
        alert.style.display = 'flex';
        alert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      navigation.showToast(validation.errors[0], 'warning', 4500);
      return;
    }

    if (alert) alert.style.display = 'none';

    // Set loading state (prevent double submit)
    if (submitBtn) submitBtn.disabled = true;
    if (spinner) spinner.style.display = 'inline-block';
    if (btnText) btnText.textContent = 'Analyzing Traceback...';

    try {
      // Execute diagnosis
      const session = await debugSession.submitDebugRequest({
        language: this.selectedLanguage,
        code,
        traceback,
        context,
        loadedSampleId: this.currentLoadedSampleId
      });

      // Save initial draft session to history
      history.saveSession(session);

      // Render diagnosis view
      this.renderCurrentDiagnosis();
      navigation.navigateTo(VIEWS.DIAGNOSIS);
      navigation.showToast('Error diagnosis completed', 'success');

    } catch (err) {
      console.error('Submission error:', err);
      if (alert && alertMsg) {
        alertMsg.textContent = err.message || 'An error occurred during analysis.';
        alert.style.display = 'flex';
        alert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      navigation.showToast('Analysis failed: ' + (err.message || 'Unknown error'), 'danger');
    } finally {
      if (submitBtn) submitBtn.disabled = false;
      if (spinner) spinner.style.display = 'none';
      if (btnText) btnText.textContent = 'Analyze Error →';
    }
  }

  /**
   * Renders the diagnosis view using results.js
   */
  renderCurrentDiagnosis() {
    const container = document.getElementById('diagnosisContent');
    if (!container) return;

    renderDiagnosis(container, debugSession.currentSession, {
      onReturnToInput: () => {
        debugSession.returnToInput();
        navigation.navigateTo(VIEWS.NEW_SESSION);
      },
      onProceedToFix: () => {
        try {
          debugSession.proceedToProposedFix();
          history.saveSession(debugSession.currentSession);
          this.renderCurrentProposedFix();
          navigation.navigateTo(VIEWS.PROPOSED_FIX);
        } catch (err) {
          navigation.showToast(err.message, 'warning');
        }
      }
    });
  }

  /**
   * Renders the proposed fix view
   */
  renderCurrentProposedFix() {
    const container = document.getElementById('proposedFixContent');
    if (!container) return;

    renderProposedFix(container, debugSession.currentSession, {
      onReturnToDiagnosis: () => {
        navigation.navigateTo(VIEWS.DIAGNOSIS);
      },
      onRejectFix: () => {
        navigation.showConfirmModal({
          title: 'Reject Proposed Fix?',
          message: 'Rejecting this proposed patch will keep your original source code intact. You can return to editing or submit another request.',
          confirmText: 'Reject & Return to Edit',
          onConfirm: () => {
            debugSession.rejectFix();
            history.saveSession(debugSession.currentSession);
            navigation.navigateTo(VIEWS.NEW_SESSION);
            navigation.showToast('Proposed fix was rejected', 'info');
          }
        });
      },
      onApproveFix: async (editedCode) => {
        try {
          navigation.showToast('Fix approved. Running controlled verification tests...', 'info');
          await debugSession.approveFixAndVerify(editedCode);
          history.saveSession(debugSession.currentSession);
          this.renderCurrentVerification();
          navigation.navigateTo(VIEWS.VERIFICATION);

          const status = debugSession.currentSession.verificationStatus;
          if (status === VERIFICATION_STATUS.VERIFIED) {
            navigation.showToast('All controlled tests passed! Fix verified.', 'success');
          } else if (status === VERIFICATION_STATUS.FAILED) {
            navigation.showToast('Verification failed: tests broke.', 'danger');
          } else {
            navigation.showToast('Verification complete: marked Unverified (sandbox offline).', 'warning');
          }
        } catch (err) {
          console.error('Verification error:', err);
          navigation.showToast('Verification failed: ' + err.message, 'danger');
        }
      }
    });
  }

  /**
   * Renders the verification view
   */
  renderCurrentVerification() {
    const container = document.getElementById('verificationContent');
    if (!container) return;

    renderVerification(container, debugSession.currentSession, {
      onReturnToFix: () => {
        navigation.navigateTo(VIEWS.PROPOSED_FIX);
      },
      onViewHistory: () => {
        navigation.navigateTo(VIEWS.HISTORY);
      },
      onStartNewSession: () => {
        this.resetForm();
        debugSession.reset();
        navigation.navigateTo(VIEWS.NEW_SESSION);
      }
    });
  }

  /**
   * Setup History search, filtering, and delete handlers
   */
  setupHistoryControls() {
    const searchInput = document.getElementById('historySearchInput');
    const filterContainer = document.getElementById('historyStatusFilters');
    const clearAllBtn = document.getElementById('clearAllHistoryBtn');

    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        history.searchQuery = e.target.value;
        this.refreshHistory();
      });
    }

    if (filterContainer) {
      filterContainer.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
          filterContainer.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          history.currentFilter = chip.getAttribute('data-filter') || 'all';
          this.refreshHistory();
        });
      });
    }

    if (clearAllBtn) {
      clearAllBtn.addEventListener('click', () => {
        if (history.sessions.length === 0) {
          navigation.showToast('History is already empty', 'info');
          return;
        }

        history.promptClearAll();
        navigation.showConfirmModal({
          title: 'Clear All Debugging History?',
          message: `Are you sure you want to delete all ${history.sessions.length} saved debugging sessions? This action cannot be undone.`,
          confirmText: 'Delete All',
          onConfirm: () => {
            history.confirmDeletion();
            this.refreshHistory();
            this.refreshDashboard();
            navigation.showToast('All debugging history cleared', 'success');
          }
        });
      });
    }
  }

  /**
   * Refreshes the History view items
   */
  refreshHistory() {
    const container = document.getElementById('historyItemsContainer');
    if (!container) return;

    history.renderHistoryView(container, {
      onStartNew: () => {
        this.resetForm();
        debugSession.reset();
        navigation.navigateTo(VIEWS.NEW_SESSION);
      },
      onOpenSession: (id) => {
        this.openSessionFromHistory(id);
      },
      onDeleteSession: (id) => {
        const session = history.promptDeleteSession(id);
        if (!session) return;

        navigation.showConfirmModal({
          title: 'Delete Session?',
          message: `Are you sure you want to delete session "${session.title}"?`,
          confirmText: 'Delete',
          onConfirm: () => {
            history.confirmDeletion();
            this.refreshHistory();
            this.refreshDashboard();
            navigation.showToast('Session deleted', 'info');
          }
        });
      }
    });

    // Update history badge in sidebar
    const badge = document.getElementById('historyCountBadge');
    if (badge) {
      badge.textContent = history.sessions.length;
    }
  }

  /**
   * Opens an existing session from history into the workspace
   */
  openSessionFromHistory(id) {
    const session = history.getSession(id);
    if (!session) return;

    debugSession.loadSession(session);

    // Populate inputs
    const codeInput = document.getElementById('sourceCodeInput');
    const tbInput = document.getElementById('tracebackInput');
    const ctxInput = document.getElementById('expectedBehaviorInput');

    if (codeInput) {
      codeInput.value = session.code;
      codeInput.dispatchEvent(new Event('input'));
    }
    if (tbInput) tbInput.value = session.traceback;
    if (ctxInput) ctxInput.value = session.context || '';

    // Route to appropriate step
    this.navigateToCurrentStep(debugSession.currentStep);
    navigation.showToast(`Opened session: ${session.title}`, 'info');
  }

  navigateToCurrentStep(step) {
    if (step === WORKFLOW_STEPS.VERIFICATION) {
      this.renderCurrentVerification();
      navigation.navigateTo(VIEWS.VERIFICATION);
    } else if (step === WORKFLOW_STEPS.PROPOSED_FIX) {
      this.renderCurrentProposedFix();
      navigation.navigateTo(VIEWS.PROPOSED_FIX);
    } else if (step === WORKFLOW_STEPS.DIAGNOSIS) {
      this.renderCurrentDiagnosis();
      navigation.navigateTo(VIEWS.DIAGNOSIS);
    } else {
      navigation.navigateTo(VIEWS.NEW_SESSION);
    }
  }

  /**
   * Refreshes dashboard statistics and recent list
   */
  refreshDashboard() {
    const stats = history.getStats();

    const elTotal = document.getElementById('statTotalSessions');
    const elVer = document.getElementById('statVerified');
    const elFail = document.getElementById('statFailed');
    const elUnver = document.getElementById('statUnverified');

    if (elTotal) elTotal.textContent = stats.total;
    if (elVer) elVer.textContent = stats.verified;
    if (elFail) elFail.textContent = stats.failed;
    if (elUnver) elUnver.textContent = stats.unverified;

    // Render recent sessions list
    const recentList = document.getElementById('recentSessionsList');
    if (recentList) {
      history.renderRecentDashboard(recentList, {
        onStartNew: () => navigation.navigateTo(VIEWS.NEW_SESSION),
        onOpenSession: (id) => this.openSessionFromHistory(id)
      });
    }
  }

  /**
   * Settings view controls and ping backend
   */
  setupSettingsView() {
    const pingBtn = document.getElementById('pingBackendBtn');
    const saveUrlBtn = document.getElementById('saveBackendUrlBtn');
    const urlInput = document.getElementById('backendUrlConfigInput');

    if (urlInput) {
      urlInput.value = api.getBaseUrl();
    }

    if (saveUrlBtn && urlInput) {
      saveUrlBtn.addEventListener('click', () => {
        api.setBaseUrl(urlInput.value);
        navigation.showToast(`Backend URL set to: ${api.getBaseUrl()}`, 'info');
        this.checkBackendConnection();
      });
    }

    if (pingBtn) {
      pingBtn.addEventListener('click', async () => {
        navigation.showToast('Pinging Flask backend...', 'info');
        await this.checkBackendConnection();
      });
    }
  }

  /**
   * Transparent backend health check
   */
  async checkBackendConnection() {
    const health = await api.checkHealth();

    const sidebarLabel = document.getElementById('sidebarBackendLabel');
    const sidebarDot = document.getElementById('sidebarBackendStatus')?.querySelector('.status-dot');
    const demoBadge = document.getElementById('demoModeBadge');

    const settingsDot = document.getElementById('settingsStatusDot');
    const settingsText = document.getElementById('settingsConnectionText');
    const settingsDesc = document.getElementById('settingsConnectionDesc');
    const aiStatus = document.getElementById('settingsAiStatus');

    if (health.online) {
      if (sidebarLabel) sidebarLabel.textContent = `Online (${health.latencyMs}ms)`;
      if (sidebarDot) {
        sidebarDot.className = 'status-dot dot-online';
      }
      if (demoBadge) {
        demoBadge.style.display = 'none';
      }
      if (settingsDot) settingsDot.className = 'status-dot dot-online';
      if (settingsText) settingsText.textContent = `Connected (Flask API active, ${health.latencyMs}ms)`;
      if (settingsDesc) settingsDesc.textContent = 'Flask backend is connected and healthy. Dynamic AST traceback extraction and test verification are available.';
      if (aiStatus) {
        aiStatus.textContent = 'Ready (Model Reachable)';
        aiStatus.className = 'info-val badge-active';
      }
    } else {
      if (sidebarLabel) sidebarLabel.textContent = 'Not Connected';
      if (sidebarDot) {
        sidebarDot.className = 'status-dot dot-offline';
      }
      if (demoBadge) {
        demoBadge.style.display = 'flex';
      }
      if (settingsDot) settingsDot.className = 'status-dot dot-offline';
      if (settingsText) settingsText.textContent = 'Not Connected (Flask Backend Offline)';
      if (settingsDesc) settingsDesc.textContent = `The frontend is currently operating in Demonstration Mode. Could not reach ${api.getBaseUrl()} (${health.error}). Start Flask on port 5000 to enable live execution.`;
      if (aiStatus) {
        aiStatus.textContent = 'Backend Disconnected';
        aiStatus.className = 'info-val badge-warning';
      }
    }
  }

  /**
   * Subscribes to session and history updates to keep sidebar widget and counters synchronized
   */
  setupStateSubscriptions() {
    const sessionWidget = document.getElementById('activeSessionWidget');
    const sessionStep = document.getElementById('activeSessionStep');
    const sessionTitle = document.getElementById('activeSessionTitle');

    debugSession.subscribe(({ session, step }) => {
      if (session) {
        if (sessionWidget) sessionWidget.style.display = 'block';
        if (sessionStep) sessionStep.textContent = step.toUpperCase();
        if (sessionTitle) sessionTitle.textContent = session.title || 'Session';
      } else {
        if (sessionWidget) sessionWidget.style.display = 'none';
      }
    });

    history.subscribe(() => {
      this.refreshDashboard();
      this.refreshHistory();
    });
  }
}

// Start app once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new DevFixApp();
  app.init();
});
