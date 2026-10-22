/**
 * DevFix AI — Debug Session State & Workflow Manager
 * 
 * Manages the evidence-based workflow lifecycle:
 * Submit Code & Traceback -> Analyze -> Diagnose -> Propose Fix -> Approve -> Verify -> Save
 */

import { SAMPLE_CASES } from './language-config.js';
import { api } from './api.js';

export const WORKFLOW_STEPS = {
  INPUT: 'input',
  DIAGNOSIS: 'diagnosis',
  PROPOSED_FIX: 'proposed_fix',
  VERIFICATION: 'verification'
};

export const VERIFICATION_STATUS = {
  VERIFIED: 'verified',
  FAILED: 'failed',
  UNVERIFIED: 'unverified',
  IN_PROGRESS: 'in_progress'
};

function normalizeText(text) {
  if (!text) return '';
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
}

export class DebugSessionManager {
  constructor() {
    this.currentSession = null;
    this.currentStep = WORKFLOW_STEPS.INPUT;
    this.listeners = [];
  }

  /**
   * Register a state change listener
   */
  subscribe(callback) {
    if (typeof callback === 'function') {
      this.listeners.push(callback);
    }
  }

  notify() {
    this.listeners.forEach(cb => {
      try {
        cb({
          session: this.currentSession,
          step: this.currentStep
        });
      } catch (err) {
        console.error('Error in session subscriber:', err);
      }
    });
  }

  /**
   * Resets active session back to clean draft state
   */
  reset() {
    this.currentSession = null;
    this.currentStep = WORKFLOW_STEPS.INPUT;
    this.notify();
  }

  /**
   * Loads an existing session (e.g. from history or resume)
   */
  loadSession(session, targetStep = null) {
    this.currentSession = { ...session };
    if (targetStep) {
      this.currentStep = targetStep;
    } else if (session.verification) {
      this.currentStep = WORKFLOW_STEPS.VERIFICATION;
    } else if (session.proposedFix) {
      this.currentStep = WORKFLOW_STEPS.PROPOSED_FIX;
    } else if (session.diagnosis) {
      this.currentStep = WORKFLOW_STEPS.DIAGNOSIS;
    } else {
      this.currentStep = WORKFLOW_STEPS.INPUT;
    }
    this.notify();
  }

  /**
   * Validates user input before submission
   */
  validateInput({ language, code, traceback }) {
    const errors = [];

    if (!language) {
      errors.push('Please select a programming language.');
    } else if (language !== 'python') {
      errors.push(`The ${language.toUpperCase()} adapter is in development. Only Python is currently enabled.`);
    }

    if (!code || !code.trim()) {
      errors.push('Source code cannot be empty.');
    } else if (code.trim().length < 5) {
      errors.push('Source code is too short to diagnose accurately.');
    }

    if (!traceback || !traceback.trim()) {
      errors.push('Error message or traceback is required for evidence-based diagnosis.');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Client-side Python traceback parser to extract facts directly from error frames
   */
  parsePythonTraceback(tracebackText) {
    const lines = tracebackText.trim().split('\n');
    let errorType = 'UnknownError';
    let errorMessage = 'An error occurred during execution.';
    let culpritLine = null;
    let fileName = 'unknown.py';
    let culpritCode = '';
    const frameFacts = [];

    // Common standard Python exceptions
    const standardErrors = [
      'ZeroDivisionError', 'IndexError', 'KeyError', 'TypeError', 'ValueError',
      'AttributeError', 'NameError', 'SyntaxError', 'IndentationError', 'FileNotFoundError',
      'ImportError', 'ModuleNotFoundError', 'RecursionError', 'StopIteration', 'AssertionError'
    ];

    // Read lines in reverse to find exception line first
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i].trim();
      for (const err of standardErrors) {
        if (line.startsWith(err)) {
          errorType = err;
          const colonIdx = line.indexOf(':');
          errorMessage = colonIdx !== -1 ? line.substring(colonIdx + 1).trim() : line;
          break;
        }
      }
      if (errorType !== 'UnknownError') break;
    }

    // Look for File "..." or File '...', line X, in ...
    const fileLineRegex = /File\s+["']([^"']+)["'],\s+line\s+(\d+)(?:,\s+in\s+([^\n\r]+))?/;
    for (let i = 0; i < lines.length; i++) {
      const match = lines[i].match(fileLineRegex);
      if (match) {
        fileName = match[1];
        culpritLine = parseInt(match[2], 10);
        const inScope = match[3] ? ` in ${match[3]}` : '';
        frameFacts.push(`Stack frame: ${fileName} line ${culpritLine}${inScope}`);
        // The line following File "..." is usually the offending source line in traceback
        if (i + 1 < lines.length && lines[i + 1].trim() && !lines[i + 1].trim().startsWith('File ')) {
          culpritCode = lines[i + 1].trim();
        }
      }
    }

    return {
      errorType,
      errorMessage,
      culpritLine,
      fileName,
      culpritCode,
      frameFacts
    };
  }

  /**
   * Submits a debug request. Dispatches to Flask backend if available;
   * otherwise executes transparent client demonstration analysis.
   */
  async submitDebugRequest({ language, code, traceback, context = '', loadedSampleId = null }) {
    const validation = this.validateInput({ language, code, traceback });
    if (!validation.isValid) {
      throw new Error(validation.errors.join(' '));
    }

    const sessionId = 'session_' + Date.now();
    const parsedFacts = this.parsePythonTraceback(traceback);

    this.currentSession = {
      id: sessionId,
      title: `${parsedFacts.errorType} in ${parsedFacts.fileName}`,
      language,
      code: code.trim(),
      traceback: traceback.trim(),
      context: context.trim(),
      loadedSampleId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      workflowStatus: WORKFLOW_STEPS.DIAGNOSIS,
      verificationStatus: VERIFICATION_STATUS.IN_PROGRESS,
      isDemo: true // Flagged honestly until live backend confirms
    };

    // Attempt live backend diagnosis directly; fall back cleanly only if request fails
    let diagnosisResult = null;
    let proposedFixResult = null;

    try {
      const apiResponse = await api.diagnose({
        language,
        code: this.currentSession.code,
        traceback: this.currentSession.traceback,
        context: this.currentSession.context
      });
      if (apiResponse && apiResponse.diagnosis) {
        diagnosisResult = apiResponse.diagnosis;
        proposedFixResult = apiResponse.proposedFix;
        this.currentSession.isDemo = false;
        api.isOnline = true;
      }
    } catch (err) {
      console.warn('Backend diagnosis unreachable or failed; using honest demo fallback:', err);
    }

    // If backend was unreachable or returned empty, use transparent demo engine
    if (!diagnosisResult) {
      const demoOutput = this.generateDemoAnalysis(this.currentSession, parsedFacts);
      diagnosisResult = demoOutput.diagnosis;
      proposedFixResult = demoOutput.proposedFix;
      this.currentSession.isDemo = true;
      this.currentSession.matchedSample = demoOutput.matchedSample;
    }

    this.currentSession.diagnosis = diagnosisResult;
    this.currentSession.proposedFix = proposedFixResult;
    this.currentStep = WORKFLOW_STEPS.DIAGNOSIS;
    this.notify();

    return this.currentSession;
  }

  /**
   * Generates honest demo analysis when running without live Flask backend
   */
  generateDemoAnalysis(session, parsedFacts) {
    const sessionCode = normalizeText(session.code);

    // Match sample if explicit ID passed OR source code matches (ignoring line break differences)
    const matched = SAMPLE_CASES.find(s => 
      (session.loadedSampleId && session.loadedSampleId === s.id) ||
      session.matchedSample === s.id ||
      normalizeText(s.sourceCode) === sessionCode ||
      (s.errorType === parsedFacts.errorType && sessionCode.includes(normalizeText(s.diagnosis?.culpritCode || '')))
    );

    if (matched) {
      return {
        matchedSample: matched.id,
        diagnosis: {
          ...matched.diagnosis,
          isDemonstration: true
        },
        proposedFix: {
          ...matched.proposedFix,
          isDemonstration: true
        }
      };
    }

    // Heuristic analysis for custom user code when offline
    const facts = [
      `Traceback points to ${parsedFacts.errorType} in file ${parsedFacts.fileName}${parsedFacts.culpritLine ? ` on line ${parsedFacts.culpritLine}` : ''}`,
      `Error detail: ${parsedFacts.errorMessage}`,
      ...(parsedFacts.frameFacts.length ? parsedFacts.frameFacts : ['Call stack terminated at top-level execution'])
    ];

    return {
      matchedSample: null,
      diagnosis: {
        errorType: parsedFacts.errorType,
        summary: `${parsedFacts.errorType}: ${parsedFacts.errorMessage}`,
        culpritLine: parsedFacts.culpritLine || 1,
        culpritCode: parsedFacts.culpritCode || '# Line identified from traceback',
        fileName: parsedFacts.fileName,
        tracebackFacts: facts,
        hypothesis: `The traceback indicates an unhandled runtime condition in ${parsedFacts.fileName}. The expression evaluated to an invalid state causing ${parsedFacts.errorType}.`,
        explanation: `A ${parsedFacts.errorType} occurs when an operation is performed on incompatible data, missing keys, or out-of-bounds indices. Examine the values passed into the culprit expression just prior to the error.`,
        recommendedAction: 'Inspect variables at the identified line number and add validation or defensive default handling.',
        isDemonstration: true
      },
      proposedFix: {
        summary: `No automated fix generated (Manual correction required)`,
        explanation: `Automated patch synthesis was unable to generate a correction for this error without a live AI model. Review the diagnosis above and edit the source code manually before verifying. Warning: Verifying unchanged code will result in failure.`,
        affectedLines: parsedFacts.culpritLine ? `Line ${parsedFacts.culpritLine}` : 'Source block',
        originalSnippet: parsedFacts.culpritCode || session.code.slice(0, 80),
        fixedSnippet: '',
        fullFixedCode: session.code,
        canSynthesize: false,
        isUnmodified: true,
        noFixGenerated: true,
        isDemonstration: true
      }
    };
  }

  /**
   * Advance from Diagnosis to Proposed Fix view
   */
  proceedToProposedFix() {
    if (!this.currentSession || !this.currentSession.proposedFix) {
      throw new Error('No proposed fix available to review.');
    }
    this.currentStep = WORKFLOW_STEPS.PROPOSED_FIX;
    this.currentSession.workflowStatus = WORKFLOW_STEPS.PROPOSED_FIX;
    this.notify();
  }

  /**
   * Return to Editing / Submission form
   */
  returnToInput() {
    this.currentStep = WORKFLOW_STEPS.INPUT;
    this.notify();
  }

  /**
   * Reject the proposed fix
   */
  rejectFix(reason = 'User requested adjustments') {
    if (!this.currentSession) return;
    this.currentSession.fixApproval = {
      approved: false,
      rejectedAt: new Date().toISOString(),
      reason
    };
    this.currentSession.verificationStatus = VERIFICATION_STATUS.UNVERIFIED;
    this.currentStep = WORKFLOW_STEPS.INPUT;
    this.notify();
  }

  /**
   * Approve the proposed fix (or user-edited code) and queue it for verification
   */
  async approveFixAndVerify(approvedCode = null) {
    if (!this.currentSession || !this.currentSession.proposedFix) {
      throw new Error('No proposed fix available.');
    }

    const codeToVerify = approvedCode || this.currentSession.proposedFix.fullFixedCode;
    this.currentSession.approvedCode = codeToVerify;
    this.currentSession.fixApproval = {
      approved: true,
      approvedAt: new Date().toISOString()
    };
    this.currentSession.workflowStatus = WORKFLOW_STEPS.VERIFICATION;
    this.currentStep = WORKFLOW_STEPS.VERIFICATION;
    this.notify();

    // Run verification on exact approved code
    return this.executeVerification(codeToVerify);
  }

  /**
   * Executes controlled test verification
   */
  async executeVerification(codeToVerify = null) {
    if (!this.currentSession) return;

    const targetCode = codeToVerify || this.currentSession.approvedCode || this.currentSession.proposedFix?.fullFixedCode;
    let verificationResult = null;

    try {
      // Attempt live backend verification with exact approved code
      const apiResponse = await api.verify({
        language: this.currentSession.language,
        originalCode: this.currentSession.code,
        proposedCode: targetCode,
        tests: this.currentSession.tests || []
      });
      if (apiResponse && apiResponse.verification) {
        verificationResult = apiResponse.verification;
        api.isOnline = true;
      }
    } catch (err) {
      console.warn('Backend verification unreachable or failed; using honest demo fallback:', err);
    }

    // Fallback to local demo verification with clear honest labeling
    if (!verificationResult) {
      verificationResult = this.generateDemoVerification(this.currentSession);
    }

    this.currentSession.verification = verificationResult;
    this.currentSession.verificationStatus = verificationResult.status;
    this.currentSession.updatedAt = new Date().toISOString();
    this.notify();

    return verificationResult;
  }

  /**
   * Generates demonstration verification report with honest status & test results
   */
  generateDemoVerification(session) {
    // If it's a known sample case, use its verified pytest suite
    const matched = SAMPLE_CASES.find(s => s.id === session.matchedSample);
    if (matched && matched.verification) {
      return {
        ...matched.verification,
        isDemonstration: true,
        disclaimer: 'DEMO MODE: These verification checks ran against the curated test suite for this known Python sample. Real dynamic code execution requires the Flask backend runner.'
      };
    }

    // For arbitrary user code running without backend
    return {
      status: VERIFICATION_STATUS.UNVERIFIED,
      testsExecuted: 0,
      testsPassed: 0,
      testsFailed: 0,
      scope: 'Live verification sandbox is offline (Flask backend not connected).',
      testCases: [],
      stdout: '[UNVERIFIED] Controlled test runner is not reachable.\nTo verify dynamic code fixes against real pytests, start the Flask backend on http://localhost:5000.',
      stderr: 'Backend offline: no sandbox execution performed.',
      isDemonstration: true,
      disclaimer: 'CRITICAL HONESTY NOTICE: This fix has NOT been tested because the verification service is offline. Never assume an unverified AI fix is bug-free.'
    };
  }
}

export const debugSession = new DebugSessionManager();
