# DevFix AI — AI-Powered Debugging & Verification Platform

> **Tagline:** Diagnose. Explain. Fix. Verify.

DevFix AI is an evidence-based developer debugging platform that helps programmers diagnose runtime exceptions, review minimal code modifications, and transparently verify proposed patches against controlled tests.

---

## 1. Product Overview

Unlike conventional AI code generators that generate plausible-looking code without testing it, DevFix AI focuses on an honest, structured workflow:
1. **Language Selection**: Choose from supported language runtimes (Python enabled in initial release; Java, C, C++, JavaScript roadmap status).
2. **Error Submission**: Submit source code, error traceback, and optional expected behavior.
3. **Structured Diagnosis**: Separate confirmed facts extracted directly from the call stack from AI hypotheses and root cause analysis.
4. **Minimal Patch Review**: Review unified code diffs showing before/after changes with affected line numbers.
5. **Approval Workflow**: Accepting a proposed fix queues it for test execution (it is never marked verified until tests actually pass).
6. **Controlled Verification**: Display transparent verification reports (`Verified`, `Failed`, or `Unverified`) with test pass/fail counts, execution stdout/stderr logs, and environment details.
7. **Session History**: Revisit saved sessions, filter by verification status, search by error type, and track debugging metrics.

---

## 2. Features Implemented vs Placeholders

| Feature Area | Status | Implementation Details |
| :--- | :--- | :--- |
| **Frontend UI/UX** | **Complete** | Dark IDE theme, responsive layout, sidebar navigation, breadcrumbs, toasts, confirmation modals. |
| **Language Matrix** | **Complete** | Python active; Java, C, C++, and JavaScript disabled with "Coming Soon" badges. |
| **Session State Machine** | **Complete** | Full state transitions across Input $\rightarrow$ Diagnosis $\rightarrow$ Proposed Fix $\rightarrow$ Verification $\rightarrow$ History. |
| **Traceback Parser** | **Complete** | Extracts exception type, filename, line number, culprit code, and frame facts. |
| **Sample Bug Library** | **Complete** | 3 curated Python bug scenarios (`ZeroDivisionError`, `IndexError`, `TypeError`) with pytests. |
| **Diff Viewer** | **Complete** | Line-by-line diff with addition (`+`) and deletion (`−`) line markers and affected line badges. |
| **Verification Engine** | **Demo Engine / Planned Flask Sandbox** | Live browser demo verifier for curated cases; uncurated arbitrary code is marked `Unverified` until Flask isolated sandbox is connected. |
| **Debugging History** | **Complete** | Browser `localStorage` persistence, search, status filtering, session restoration, and deletion. |
| **Backend Integration** | **Contract Ready** | Centralized API client (`modules/api.js`) ready for Flask endpoints; honest connection status. |
| **Flask REST Backend** | **Planned (Stage 2)** | Endpoints: `/api/health`, `/api/languages`, `/api/diagnose`, `/api/propose-fix`, `/api/verify`, `/api/sessions`. |
| **AI Model Provider** | **Planned (Stage 3)** | Pluggable interface for local Ollama (`llama3`, `deepseek-coder`) or compatible hosted APIs. |

---

## 3. Technology Stack

- **Frontend**: HTML5, CSS3 custom properties, Vanilla JavaScript (ES Modules).
- **Icons & Styling**: Handcrafted SVG icons, Inter UI typography, Fira Code monospace font.
- **Backend (Planned)**: Python 3.10+, Flask 3.1, SQLite, `pytest`.
- **AI Integration (Planned)**: Local Ollama / compatible LLM provider with structured JSON outputs.

---

## 4. Project Structure

```
DevFix-AI/
├── frontend/
│   ├── index.html              # Main HTML5 application container
│   ├── styles.css              # Dark IDE theme & responsive styles
│   ├── app.js                  # Main orchestrator & UI action handlers
│   ├── modules/
│   │   ├── navigation.js       # View switcher, modals, and toasts
│   │   ├── language-config.js  # Language matrix & curated Python bug samples
│   │   ├── debug-session.js    # State machine, traceback parser & demo engine
│   │   ├── results.js          # Diagnosis, diff viewer & verification renderer
│   │   ├── history.js          # Session persistence, search, filter & metrics
│   │   ├── api.js              # Centralized HTTP client with offline detection
│   │   └── utils.js            # HTML escaping & date formatting helpers
│   └── tests/
│       ├── test-frontend-logic.js # Unit test suite (40 assertions)
│       └── browser-diagnose.js    # Headless Chrome CDP end-to-end verification
├── backend/                    # Scaffolding for Flask backend (Stage 2)
│   ├── app.py
│   ├── requirements.txt
│   ├── routes/
│   ├── services/
│   ├── language_adapters/
│   ├── database/
│   └── tests/
├── .env.example
├── .gitignore
└── README.md
```

---

## 5. How to Run the Frontend Locally

### Option A: Using Python's built-in HTTP server
```bash
# Navigate to the frontend directory
cd DevFix-AI/frontend

# Start HTTP server on port 8080
python -m http.server 8080
```
Open your browser at `http://localhost:8080/`.

### Option B: Using Node http-server or live-server
```bash
npx http-server DevFix-AI/frontend -p 8080
```

---

## 6. How to Run Automated Frontend Tests

To run the 40 unit test assertions:
```bash
cd DevFix-AI
node frontend/tests/test-frontend-logic.js
```

To run the live headless Chrome end-to-end interaction test:
```bash
cd DevFix-AI
node frontend/tests/browser-diagnose.js
```

---

## 7. Connecting the Flask Backend (Next Steps for Stage 2)

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   ```
2. Install requirements:
   ```bash
   pip install flask flask-cors pytest python-dotenv
   ```
3. Run the Flask API server:
   ```bash
   python backend/app.py
   ```
4. In the DevFix AI frontend, visit **Settings** $\rightarrow$ Click **Ping Backend**. The status dot will turn green and switch from **Demo Mode** to **Live Backend Mode**.
