/**
 * Frontend Logic & State Verification Test Suite
 * Validates module behavior, state transitions, validation rules, and honest demo labeling.
 */

import { SUPPORTED_LANGUAGES, SAMPLE_CASES } from '../modules/language-config.js';
import { DebugSessionManager, WORKFLOW_STEPS, VERIFICATION_STATUS } from '../modules/debug-session.js';
import { HistoryManager } from '../modules/history.js';
import { api, DEFAULT_BACKEND_URL } from '../modules/api.js';

let passedTests = 0;
let totalTests = 0;

function assert(condition, testName) {
  totalTests++;
  if (condition) {
    console.log(`  ✓ PASS: ${testName}`);
    passedTests++;
  } else {
    console.error(`  ✕ FAIL: ${testName}`);
    throw new Error(`Assertion failed: ${testName}`);
  }
}

console.log('====================================================');
console.log('Running DevFix AI Frontend Logic Tests');
console.log('====================================================');

// Test 1: Language Matrix
console.log('\n[1] Testing Language Support Matrix:');
assert(SUPPORTED_LANGUAGES.length === 5, 'Exactly 5 languages configured in matrix');
const python = SUPPORTED_LANGUAGES.find(l => l.id === 'python');
assert(python && python.enabled === true, 'Python is enabled in initial release');
const unsupported = SUPPORTED_LANGUAGES.filter(l => l.id !== 'python');
assert(unsupported.every(l => l.enabled === false), 'All non-Python languages are disabled');
assert(unsupported.every(l => l.statusText === 'Coming Soon'), 'Non-Python languages marked Coming Soon');

// Test 2: Curated Samples
console.log('\n[2] Testing Curated Python Bug Samples:');
assert(SAMPLE_CASES.length >= 3, 'At least 3 curated Python bug samples defined');
const sample1 = SAMPLE_CASES[0];
assert(sample1.errorType === 'ZeroDivisionError', 'Sample 1 is ZeroDivisionError');
assert(sample1.diagnosis && sample1.diagnosis.culpritLine === 8, 'Sample 1 culprit line is 8');
assert(sample1.proposedFix && sample1.proposedFix.fullFixedCode.includes('if not scores:'), 'Sample 1 proposed fix adds guard clause');
assert(sample1.verification && sample1.verification.status === 'verified', 'Sample 1 has verified test results');

// Test 3: Traceback Parser & Validation
console.log('\n[3] Testing Traceback Parsing & Validation:');
const sessionMgr = new DebugSessionManager();

// Empty validation test
const emptyValidation = sessionMgr.validateInput({ language: 'python', code: '', traceback: '' });
assert(emptyValidation.isValid === false, 'Rejects empty submission');
assert(emptyValidation.errors.length >= 2, 'Returns clear errors for empty code and traceback');

// Unsupported language test
const javaValidation = sessionMgr.validateInput({ language: 'java', code: 'class Test {}', traceback: 'Exception' });
assert(javaValidation.isValid === false, 'Rejects unsupported language submission');
assert(javaValidation.errors[0].includes('JAVA adapter is in development'), 'Identifies adapter in development');

// Python traceback parser test
const sampleTb = `Traceback (most recent call last):
  File "data_analytics.py", line 42, in process_items
    result = compute(values[idx])
IndexError: list index out of range`;

const parsed = sessionMgr.parsePythonTraceback(sampleTb);
assert(parsed.errorType === 'IndexError', 'Extracts IndexError exception type');
assert(parsed.fileName === 'data_analytics.py', 'Extracts filename data_analytics.py');
assert(parsed.culpritLine === 42, 'Extracts culprit line 42');
assert(parsed.errorMessage === 'list index out of range', 'Extracts error message');

// Test 4: Offline Fallback & Honest Demo Labeling (When backend is unreachable)
console.log('\n[4] Testing Offline Fallback & Honest Demo Labels:');
await (async () => {
  // Explicitly point to an unreachable port to test genuine request failure fallback
  const realUrl = api.getBaseUrl();
  api.setBaseUrl('http://127.0.0.1:9999');

  const fallbackSessionMgr = new DebugSessionManager();
  const session = await fallbackSessionMgr.submitDebugRequest({
    language: 'python',
    code: sample1.sourceCode,
    traceback: sample1.traceback,
    context: sample1.expectedBehavior
  });

  assert(session.isDemo === true, 'Session is honestly flagged as demo when backend request fails');
  assert(session.diagnosis.isDemonstration === true, 'Diagnosis is explicitly labeled as demonstration');
  assert(session.diagnosis.tracebackFacts.length > 0, 'Extracts facts from traceback in fallback');
  assert(fallbackSessionMgr.currentStep === WORKFLOW_STEPS.DIAGNOSIS, 'Step advances to DIAGNOSIS');

  // Proceed to proposed fix
  fallbackSessionMgr.proceedToProposedFix();
  assert(fallbackSessionMgr.currentStep === WORKFLOW_STEPS.PROPOSED_FIX, 'Step advances to PROPOSED_FIX');
  assert(session.proposedFix.isDemonstration === true, 'Proposed fix is labeled as demonstration');

  // Approve and verify
  const vReport = await fallbackSessionMgr.approveFixAndVerify();
  assert(fallbackSessionMgr.currentStep === WORKFLOW_STEPS.VERIFICATION, 'Step advances to VERIFICATION');
  assert(vReport.status === VERIFICATION_STATUS.VERIFIED, 'Verification status is verified for curated demo sample');
  assert(vReport.disclaimer.includes('DEMO MODE'), 'Verification report includes prominent honest demo disclaimer');
  assert(vReport.testsExecuted === 3 && vReport.testsPassed === 3, 'Test count matches defined test suite');

  // Restore URL
  api.setBaseUrl(realUrl);
})();

// Test 5: Fallback & Demo Mode Unmodified Code Safety (Never Fakes Fixes)
console.log('\n[5] Testing Fallback Handling for Custom Code (noFixGenerated flag):');
await (async () => {
  const realUrl = api.getBaseUrl();
  api.setBaseUrl('http://127.0.0.1:9999'); // force offline fallback

  const customSessionMgr = new DebugSessionManager();
  const arbitraryCode = 'def foo(x):\n    return x + 10';
  const arbitraryTb = 'Traceback:\n  File "foo.py", line 2, in foo\nTypeError: unsupported operand';
  
  const customSession = await customSessionMgr.submitDebugRequest({
    language: 'python',
    code: arbitraryCode,
    traceback: arbitraryTb
  });

  customSessionMgr.proceedToProposedFix();
  const fix = customSession.proposedFix;

  // Verify that unchanged fallback code is NEVER represented as an automated fix
  assert(fix.noFixGenerated === true, 'Proposal explicitly flags noFixGenerated: true');
  assert(fix.isUnmodified === true, 'Proposal explicitly flags isUnmodified: true');
  assert(fix.canSynthesize === false, 'Proposal explicitly flags canSynthesize: false');
  assert(fix.summary.includes('No automated fix generated'), 'Summary clearly indicates manual correction required');
  assert(fix.fullFixedCode === arbitraryCode, 'Fix holds unedited code awaiting user correction');

  // Attempting verification without backend yields unverified notice
  const customVerify = await customSessionMgr.approveFixAndVerify();
  assert(customVerify.status === VERIFICATION_STATUS.UNVERIFIED, 
    'Arbitrary uncurated code without live backend runner MUST be marked UNVERIFIED (Never fakes verification)');
  assert(customVerify.disclaimer.includes('CRITICAL HONESTY NOTICE'), 
    'Explicitly warns that fix has not been tested');

  api.setBaseUrl(realUrl);
})();

// Test 6: History Persistence, Search, Filtering & Statistics
console.log('\n[6] Testing History & Statistics:');
// Mock localStorage in node environment for history test
const storage = {};
global.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, val) => { storage[key] = val; },
  removeItem: (key) => { delete storage[key]; }
};

const historyMgr = new HistoryManager();
const s1 = historyMgr.saveSession({
  id: 'test_1',
  title: 'ZeroDivisionError in metrics.py',
  language: 'python',
  verificationStatus: 'verified',
  diagnosis: { errorType: 'ZeroDivisionError', fileName: 'metrics.py' }
});

const s2 = historyMgr.saveSession({
  id: 'test_2',
  title: 'IndexError in loop.py',
  language: 'python',
  verificationStatus: 'failed',
  diagnosis: { errorType: 'IndexError', fileName: 'loop.py' }
});

const s3 = historyMgr.saveSession({
  id: 'test_3',
  title: 'TypeError in parser.py',
  language: 'python',
  verificationStatus: 'unverified',
  diagnosis: { errorType: 'TypeError', fileName: 'parser.py' }
});

const stats = historyMgr.getStats();
assert(stats.total === 3, 'Total sessions calculated correctly (3)');
assert(stats.verified === 1, 'Verified count is 1');
assert(stats.failed === 1, 'Failed count is 1');
assert(stats.unverified === 1, 'Unverified count is 1');

// Filter tests
historyMgr.currentFilter = 'verified';
let filtered = historyMgr.getFilteredSessions();
assert(filtered.length === 1 && filtered[0].id === 'test_1', 'Filter by verified returns only verified sessions');

historyMgr.currentFilter = 'all';
historyMgr.searchQuery = 'IndexError';
filtered = historyMgr.getFilteredSessions();
assert(filtered.length === 1 && filtered[0].id === 'test_2', 'Search query matches error type');

// Deletion confirmation test
historyMgr.searchQuery = '';
historyMgr.promptDeleteSession('test_2');
historyMgr.confirmDeletion();
assert(historyMgr.sessions.length === 2, 'Session deleted successfully upon confirmation');
assert(historyMgr.getSession('test_2') === null, 'Deleted session is no longer accessible');

// Test 7: Live Backend Integration & Manually Edited Code Verification
console.log('\n[7] Testing Live Backend Health, Direct Diagnosis & Manual Code Handoff:');
await (async () => {
  api.setBaseUrl(DEFAULT_BACKEND_URL);
  const health = await api.checkHealth(4000);
  assert(health.online === true, 'Live backend health probe returns online: true');
  assert(api.isOnline === true, 'api.isOnline is true when live backend is reachable');

  const liveSessionMgr = new DebugSessionManager();
  const brokenCode = 'def calculate(a, b):\n    return a + b\n\nprint(calculate(40, "2"))';
  const brokenTb = `Traceback (most recent call last):
  File "calc.py", line 4, in <module>
    print(calculate(40, "2"))
  File "calc.py", line 2, in calculate
    return a + b
TypeError: unsupported operand type(s) for +: 'int' and 'str'`;

  // Live diagnosis directly calls backend (no premature online gating)
  const session = await liveSessionMgr.submitDebugRequest({
    language: 'python',
    code: brokenCode,
    traceback: brokenTb
  });

  assert(session.isDemo === false, 'Session uses live backend when available');
  assert(session.diagnosis.culpritLine === 2, 'Backend identifies culprit line 2');
  assert(session.diagnosis.errorType === 'TypeError', 'Backend identifies TypeError');

  // Test Verifying Unmodified Broken Code -> Must Fail Honestly
  liveSessionMgr.proceedToProposedFix();
  const failVerify = await liveSessionMgr.approveFixAndVerify(brokenCode);
  assert(failVerify.status === 'failed', 'Unmodified broken code genuinely FAILS verification');
  assert(failVerify.testsFailed === 1, 'Failed test count is 1');
  assert(failVerify.stderr.includes('TypeError'), 'Execution output captures actual TypeError');

  // Test Verifying User Manually Edited Fix -> Must Pass Cleanly
  const manuallyEditedCode = 'def calculate(a, b):\n    return a + int(b)\n\nprint(calculate(40, "2"))';
  const passVerify = await liveSessionMgr.approveFixAndVerify(manuallyEditedCode);
  assert(passVerify.status === 'verified', 'User manually corrected code PASSES live verification');
  assert(passVerify.testsPassed === 1, 'Passed test count is 1');
  assert(passVerify.testsFailed === 0, 'Failed test count is 0');
  assert(passVerify.stdout.includes('42'), 'Stdout contains verified calculation output 42');
  assert(passVerify.verifiedCode === manuallyEditedCode, 'Verifier executes the exact approved user code');
})();

console.log('====================================================');
console.log(`ALL TESTS PASSED! (${passedTests}/${totalTests})`);
console.log('====================================================\n');
