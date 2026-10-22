import unittest
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app import create_app
from backend.database.db import DB_PATH

class DevFixApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        """GET /api/health returns 200 and accurate AI provider information"""
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('ai_provider', data)
        self.assertIn('environment', data)
        # Verify it honestly reports whether models are installed
        self.assertIn('available', data['ai_provider'])

    def test_languages_endpoint(self):
        """GET /api/languages returns Python enabled and others disabled"""
        res = self.client.get('/api/languages')
        self.assertEqual(res.status_code, 200)
        langs = res.get_json()
        self.assertEqual(len(langs), 5)
        py = next(l for l in langs if l['id'] == 'python')
        self.assertTrue(py['enabled'])
        for l in langs:
            if l['id'] != 'python':
                self.assertFalse(l['enabled'])

    def test_diagnose_endpoint_valid(self):
        """POST /api/diagnose parses traceback facts and separates from AI hypothesis"""
        payload = {
            'language': 'python',
            'code': 'def divide(a, b):\n    return a / b\n\ndivide(10, 0)',
            'traceback': 'Traceback (most recent call last):\n  File "math.py", line 2, in divide\n    return a / b\nZeroDivisionError: division by zero',
            'context': 'Should return None on zero denominator'
        }
        res = self.client.post('/api/diagnose', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        diag = data.get('diagnosis')
        self.assertEqual(diag.get('errorType'), 'ZeroDivisionError')
        self.assertEqual(diag.get('culpritLine'), 2)
        self.assertIn('tracebackFacts', diag)
        self.assertTrue(len(diag['tracebackFacts']) > 0)
        self.assertIn('hypothesis', diag)
        self.assertIn('proposedFix', data)

    def test_diagnose_endpoint_empty_code(self):
        """POST /api/diagnose rejects empty code with 400"""
        payload = {'language': 'python', 'code': '', 'traceback': 'Traceback...'}
        res = self.client.post('/api/diagnose', json=payload)
        self.assertEqual(res.status_code, 400)

    def test_verify_endpoint_real_passing_test(self):
        """POST /api/verify executes real tests and returns verified status"""
        payload = {
            'language': 'python',
            'originalCode': 'def add(a, b):\n    return a - b',
            'proposedCode': 'def add(a, b):\n    return a + b',
            'tests': [
                {'name': 'test_positive_numbers', 'input': 'assert add(2, 3) == 5', 'expected': '5'},
                {'name': 'test_zeros', 'input': 'assert add(0, 0) == 0', 'expected': '0'}
            ]
        }
        res = self.client.post('/api/verify', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        v = data.get('verification')
        self.assertEqual(v.get('status'), 'verified')
        self.assertEqual(v.get('testsExecuted'), 2)
        self.assertEqual(v.get('testsPassed'), 2)
        self.assertEqual(v.get('testsFailed'), 0)

    def test_verify_endpoint_real_failing_test(self):
        """POST /api/verify executes real tests and correctly marks failing code as failed"""
        payload = {
            'language': 'python',
            'originalCode': 'def add(a, b):\n    return a - b',
            'proposedCode': 'def add(a, b):\n    return a - b', # Bug not fixed
            'tests': [
                {'name': 'test_positive_numbers', 'input': 'assert add(2, 3) == 5', 'expected': '5'}
            ]
        }
        res = self.client.post('/api/verify', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        v = data.get('verification')
        self.assertEqual(v.get('status'), 'failed')
        self.assertEqual(v.get('testsFailed'), 1)

    def test_verify_clean_execution_passing(self):
        """POST /api/verify with tests=[] runs test_clean_execution and passes on clean code"""
        payload = {
            'language': 'python',
            'originalCode': 'def double(x): return x * 2\nprint(double(4))',
            'proposedCode': 'def double(x): return x * 2\nprint(double(4))',
            'tests': []
        }
        res = self.client.post('/api/verify', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        v = data.get('verification')
        self.assertEqual(v.get('status'), 'verified')
        self.assertEqual(v.get('testsPassed'), 1)
        self.assertEqual(v.get('testsFailed'), 0)
        self.assertEqual(v['testCases'][0]['name'], 'test_clean_execution')
        self.assertEqual(v['testCases'][0]['status'], 'passed')

    def test_verify_clean_execution_failing(self):
        """POST /api/verify with tests=[] runs test_clean_execution and fails on broken code"""
        payload = {
            'language': 'python',
            'originalCode': 'a = 1 / 0',
            'proposedCode': 'a = 1 / 0',
            'tests': []
        }
        res = self.client.post('/api/verify', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        v = data.get('verification')
        self.assertEqual(v.get('status'), 'failed')
        self.assertEqual(v.get('testsPassed'), 0)
        self.assertEqual(v.get('testsFailed'), 1)
        self.assertEqual(v['testCases'][0]['name'], 'test_clean_execution')
        self.assertEqual(v['testCases'][0]['status'], 'failed')
        self.assertIn('ZeroDivisionError', v.get('stderr', ''))

    def test_sessions_crud(self):
        """Full SQLite session CRUD flow"""
        session_id = 'test_session_12345'
        # 1. Create session
        new_session = {
            'id': session_id,
            'title': 'Test IndexError',
            'language': 'python',
            'code': 'a = [1]; print(a[5])',
            'traceback': 'IndexError: list index out of range',
            'workflowStatus': 'diagnosis',
            'verificationStatus': 'in_progress'
        }
        create_res = self.client.post('/api/sessions', json=new_session)
        self.assertEqual(create_res.status_code, 201)

        # 2. Get session
        get_res = self.client.get(f'/api/sessions/{session_id}')
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.get_json()['id'], session_id)

        # 3. List sessions
        list_res = self.client.get('/api/sessions')
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(s['id'] == session_id for s in list_res.get_json()))

        # 4. Delete session
        del_res = self.client.delete(f'/api/sessions/{session_id}')
        self.assertEqual(del_res.status_code, 200)

        # 5. Verify deleted
        get_after_del = self.client.get(f'/api/sessions/{session_id}')
        self.assertEqual(get_after_del.status_code, 404)

if __name__ == '__main__':
    unittest.main()
