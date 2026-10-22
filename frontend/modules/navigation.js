/**
 * DevFix AI — Navigation & UI Shell Controller
 * 
 * Manages view switching, breadcrumbs, sidebar toggles, toasts, and modal dialogs.
 */

export const VIEWS = {
  DASHBOARD: 'dashboard',
  NEW_SESSION: 'new-session',
  DIAGNOSIS: 'diagnosis',
  PROPOSED_FIX: 'proposed-fix',
  VERIFICATION: 'verification',
  HISTORY: 'history',
  SETTINGS: 'settings'
};

class NavigationManager {
  constructor() {
    this.currentView = VIEWS.DASHBOARD;
    this.viewPanels = {};
    this.navLinks = {};
    this.viewChangeListeners = [];
  }

  init() {
    // Cache view panels
    this.viewPanels[VIEWS.DASHBOARD] = document.getElementById('viewDashboard');
    this.viewPanels[VIEWS.NEW_SESSION] = document.getElementById('viewNewSession');
    this.viewPanels[VIEWS.DIAGNOSIS] = document.getElementById('viewDiagnosis');
    this.viewPanels[VIEWS.PROPOSED_FIX] = document.getElementById('viewProposedFix');
    this.viewPanels[VIEWS.VERIFICATION] = document.getElementById('viewVerification');
    this.viewPanels[VIEWS.HISTORY] = document.getElementById('viewHistory');
    this.viewPanels[VIEWS.SETTINGS] = document.getElementById('viewSettings');

    // Cache sidebar navigation links
    this.navLinks[VIEWS.DASHBOARD] = document.getElementById('navDashboard');
    this.navLinks[VIEWS.NEW_SESSION] = document.getElementById('navNewSession');
    this.navLinks[VIEWS.HISTORY] = document.getElementById('navHistory');
    this.navLinks[VIEWS.SETTINGS] = document.getElementById('navSettings');

    // Attach click handlers to nav links
    Object.keys(this.navLinks).forEach(viewKey => {
      const link = this.navLinks[viewKey];
      if (link) {
        link.addEventListener('click', () => this.navigateTo(viewKey));
      }
    });

    // Mobile sidebar toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    const sidebar = document.getElementById('appSidebar');

    if (mobileMenuBtn && sidebar) {
      mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
      });
    }

    if (sidebarCloseBtn && sidebar) {
      sidebarCloseBtn.addEventListener('click', () => {
        sidebar.classList.remove('open');
      });
    }

    // Modal close buttons
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalCancelBtn = document.getElementById('modalCancelBtn');
    const confirmationModal = document.getElementById('confirmationModal');

    if (modalCloseBtn && confirmationModal) {
      modalCloseBtn.addEventListener('click', () => {
        confirmationModal.style.display = 'none';
      });
    }
    if (modalCancelBtn && confirmationModal) {
      modalCancelBtn.addEventListener('click', () => {
        confirmationModal.style.display = 'none';
      });
    }

    // Sample picker modal close
    const samplePickerCloseBtn = document.getElementById('samplePickerCloseBtn');
    const samplePickerCancelBtn = document.getElementById('samplePickerCancelBtn');
    const samplePickerModal = document.getElementById('samplePickerModal');

    if (samplePickerCloseBtn && samplePickerModal) {
      samplePickerCloseBtn.addEventListener('click', () => {
        samplePickerModal.style.display = 'none';
      });
    }
    if (samplePickerCancelBtn && samplePickerModal) {
      samplePickerCancelBtn.addEventListener('click', () => {
        samplePickerModal.style.display = 'none';
      });
    }
  }

  onViewChange(callback) {
    if (typeof callback === 'function') {
      this.viewChangeListeners.push(callback);
    }
  }

  navigateTo(targetView) {
    if (!this.viewPanels[targetView]) {
      console.warn(`View ${targetView} does not exist`);
      return;
    }

    // Hide all view panels
    Object.values(this.viewPanels).forEach(panel => {
      if (panel) panel.classList.remove('active');
    });

    // Show target view panel
    this.viewPanels[targetView].classList.add('active');

    // Update nav links active state
    Object.keys(this.navLinks).forEach(viewKey => {
      const link = this.navLinks[viewKey];
      if (link) {
        if (viewKey === targetView || 
           (viewKey === VIEWS.NEW_SESSION && [VIEWS.DIAGNOSIS, VIEWS.PROPOSED_FIX, VIEWS.VERIFICATION].includes(targetView))) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      }
    });

    // Update breadcrumbs
    this.updateBreadcrumbs(targetView);

    // Close mobile sidebar if open
    const sidebar = document.getElementById('appSidebar');
    if (sidebar) sidebar.classList.remove('open');

    this.currentView = targetView;

    // Notify listeners
    this.viewChangeListeners.forEach(cb => {
      try {
        cb(targetView);
      } catch (err) {
        console.error('Error in view change listener:', err);
      }
    });

    // Scroll to top of content
    const content = document.querySelector('.content-container');
    if (content) content.scrollTop = 0;
  }

  updateBreadcrumbs(view) {
    const crumbEl = document.getElementById('currentCrumb');
    if (!crumbEl) return;

    const titles = {
      [VIEWS.DASHBOARD]: 'Dashboard',
      [VIEWS.NEW_SESSION]: 'New Debug Session',
      [VIEWS.DIAGNOSIS]: 'Session / Diagnosis',
      [VIEWS.PROPOSED_FIX]: 'Session / Proposed Fix',
      [VIEWS.VERIFICATION]: 'Session / Verification',
      [VIEWS.HISTORY]: 'Debugging History',
      [VIEWS.SETTINGS]: 'Settings'
    };

    crumbEl.textContent = titles[view] || 'Workspace';
  }

  /**
   * Shows a toast notification at bottom right
   */
  showToast(message, type = 'info', durationMs = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    else if (type === 'danger') icon = '⚠️';
    else if (type === 'warning') icon = '⏳';

    toast.innerHTML = `
      <span>${icon}</span>
      <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.2s ease';
      setTimeout(() => toast.remove(), 250);
    }, durationMs);
  }

  /**
   * Opens the confirmation modal dialog
   */
  showConfirmModal({ title, message, confirmText = 'Confirm', onConfirm }) {
    const modal = document.getElementById('confirmationModal');
    const titleEl = document.getElementById('modalTitle');
    const msgEl = document.getElementById('modalMessage');
    const confirmBtn = document.getElementById('modalConfirmBtn');

    if (!modal || !confirmBtn) return;

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    confirmBtn.textContent = confirmText;

    // Replace click handler cleanly
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    newConfirmBtn.addEventListener('click', () => {
      modal.style.display = 'none';
      if (typeof onConfirm === 'function') onConfirm();
    });

    modal.style.display = 'flex';
  }

  /**
   * Opens sample bug picker modal
   */
  showSamplePicker(samples, onSelect) {
    const modal = document.getElementById('samplePickerModal');
    const listEl = document.getElementById('sampleCardsList');
    if (!modal || !listEl) return;

    listEl.innerHTML = samples.map(sample => `
      <div class="sample-pick-card" data-id="${sample.id}">
        <div class="sample-pick-header">
          <span class="sample-pick-title">${sample.title}</span>
          <span class="sample-pick-badge">${sample.errorType}</span>
        </div>
        <div class="sample-pick-desc">${sample.description}</div>
      </div>
    `).join('');

    listEl.querySelectorAll('.sample-pick-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = card.getAttribute('data-id');
        const selected = samples.find(s => s.id === id);
        modal.style.display = 'none';
        if (selected && typeof onSelect === 'function') {
          onSelect(selected);
        }
      });
    });

    modal.style.display = 'flex';
  }
}

export const navigation = new NavigationManager();
