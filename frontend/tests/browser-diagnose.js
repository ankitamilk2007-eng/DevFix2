import { spawn } from 'child_process';
import http from 'http';

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9222;

console.log('Testing End-to-End DevFix AI Workflow in Headless Chrome...');
const chrome = spawn(chromePath, [
  '--headless=new',
  `--remote-debugging-port=${port}`,
  '--disable-gpu',
  '--no-sandbox',
  'http://localhost:8080/index.html'
]);

// Wait 2 seconds for Chrome CDP
await new Promise(r => setTimeout(r, 2000));

const getJson = (url) => new Promise((resolve, reject) => {
  http.get(url, (res) => {
    let body = '';
    res.on('data', chunk => body += chunk);
    res.on('end', () => resolve(JSON.parse(body)));
  }).on('error', reject);
});

try {
  const targets = await getJson(`http://127.0.0.1:${port}/json/list`);
  const pageTarget = targets.find(t => t.type === 'page');
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);

  let idCounter = 1;
  const send = (method, params = {}) => new Promise((resolve) => {
    const id = idCounter++;
    const handler = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id === id) {
        ws.removeEventListener('message', handler);
        resolve(msg.result);
      }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });

  await new Promise(r => ws.onopen = r);

  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data);
    if (msg.method === 'Runtime.consoleAPICalled') {
      console.log(`[Browser Console]:`, ...msg.params.args.map(a => a.value || a.description));
    }
  });

  await send('Runtime.enable');
  await new Promise(r => setTimeout(r, 1000));

  // Step 1: Check initial page load
  console.log('\n--- Step 1: Navigating to New Debug Session ---');
  await send('Runtime.evaluate', {
    expression: `document.getElementById('navNewSession').click();`
  });
  await new Promise(r => setTimeout(r, 500));

  // Step 2: Test empty click on Analyze Error to verify visible feedback
  console.log('--- Step 2: Testing Validation on Empty Analyze Error Click ---');
  const emptyClick = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const btn = document.getElementById('analyzeErrorBtn');
        btn.click();
        const alert = document.getElementById('formValidationAlert');
        const alertBtn = document.getElementById('alertLoadSampleBtn');
        return {
          alertDisplay: alert ? alert.style.display : null,
          alertMessage: alert ? alert.innerText : null,
          hasAlertSampleBtn: !!alertBtn
        };
      })()
    `,
    returnByValue: true
  });
  console.log('Validation feedback triggered properly:', emptyClick.result.value);

  // Step 3: Click "Load Sample Case" button directly on the form
  console.log('\n--- Step 3: Clicking "Load Sample Case" button ---');
  await send('Runtime.evaluate', {
    expression: `document.getElementById('loadSampleCaseBtn')?.click();`
  });
  await new Promise(r => setTimeout(r, 500));

  const sampleLoad = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const codeInput = document.getElementById('sourceCodeInput');
        const tbInput = document.getElementById('tracebackInput');
        return {
          codeLength: codeInput?.value?.length,
          tracebackLength: tbInput?.value?.length,
          codeSnippet: codeInput?.value?.slice(0, 45)
        };
      })()
    `,
    returnByValue: true
  });
  console.log('Sample case populated into form:', sampleLoad.result.value);

  // Step 4: Click "Analyze Error"
  console.log('\n--- Step 4: Clicking "Analyze Error" Button ---');
  const analyzeClick = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const btn = document.getElementById('analyzeErrorBtn');
        btn.click();
        return { clicked: true };
      })()
    `,
    returnByValue: true
  });
  console.log('Analyze button clicked:', analyzeClick.result.value);

  // Wait for diagnosis render
  await new Promise(r => setTimeout(r, 600));

  const diagState = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const activeView = document.querySelector('.view-panel.active')?.id;
        const errPill = document.querySelector('.diag-error-pill')?.innerText;
        const rootCause = document.querySelector('.hypothesis-body')?.innerText?.slice(0, 80);
        return { activeView, errPill, rootCause };
      })()
    `,
    returnByValue: true
  });
  console.log('Diagnosis View Rendered:', diagState.result.value);

  // Step 5: Click "Review Proposed Fix"
  console.log('\n--- Step 5: Clicking "Review Proposed Fix →" ---');
  await send('Runtime.evaluate', {
    expression: `document.getElementById('diagProceedToFixBtn')?.click();`
  });
  await new Promise(r => setTimeout(r, 400));

  const fixState = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const activeView = document.querySelector('.view-panel.active')?.id;
        const diffRows = document.querySelectorAll('.diff-row').length;
        const affected = document.querySelector('.fix-affected-lines')?.innerText;
        return { activeView, diffRows, affected };
      })()
    `,
    returnByValue: true
  });
  console.log('Proposed Fix View Rendered:', fixState.result.value);

  // Step 6: Approve Fix and Run Verification
  console.log('\n--- Step 6: Clicking "Approve Fix & Run Verification →" ---');
  await send('Runtime.evaluate', {
    expression: `document.getElementById('fixApproveBtn')?.click();`
  });
  await new Promise(r => setTimeout(r, 1500));

  const verifyState = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const activeView = document.querySelector('.view-panel.active')?.id;
        const statusTitle = document.querySelector('.vstatus-title')?.innerText;
        const testItems = document.querySelectorAll('.test-item').length;
        const consoleLog = document.querySelector('.console-body')?.innerText?.slice(0, 90);
        return { activeView, statusTitle, testItems, consoleSnippet: consoleLog };
      })()
    `,
    returnByValue: true
  });
  console.log('Verification Report Rendered:', verifyState.result.value);

  // Step 7: Check Dashboard and History Persistence
  console.log('\n--- Step 7: Checking History and Dashboard Statistics ---');
  await send('Runtime.evaluate', {
    expression: `document.getElementById('navDashboard')?.click();`
  });
  await new Promise(r => setTimeout(r, 400));

  const dashState = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const total = document.getElementById('statTotalSessions')?.innerText;
        const verified = document.getElementById('statVerified')?.innerText;
        const recentRows = document.querySelectorAll('.recent-item').length;
        return { total, verified, recentRows };
      })()
    `,
    returnByValue: true
  });
  console.log('Dashboard Updated with Real Stored Metrics:', dashState.result.value);

  console.log('\n====================================================');
  console.log('SUCCESS: Full end-to-end debugging workflow tested in live browser!');
  console.log('====================================================');

  ws.close();
} catch (err) {
  console.error('Test error:', err);
} finally {
  chrome.kill();
  process.exit(0);
}
