import unittest
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.ai_service import AIService
from backend.services.verifier_service import VerifierService
from backend.app import create_app

class DevFixFinalEvaluationSuite(unittest.TestCase):
    """
    Comprehensive regression suite validating the 12 criteria for external evaluation:
    1. Undefined variable calculates discount fix without try/except
    2. Rejection of unchanged buggy AI response
    3. Rejection of empty or malformed AI response
    4. Code with exit code 0 but mismatching expected output is Failed
    5. SyntaxError handling
    6. NameError handling
    7. TypeError handling
    8. IndexError handling
    9. ZeroDivisionError handling
    10. Hand-off of manually edited code to verifier
    11. Ollama availability check
    12. End-to-end diagnosis to verification flow
    """

    def setUp(self):
        self.ai_service = AIService()
        self.verifier = VerifierService()
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    # 1. Undefined variable example produces a correct fix, not a try/except wrapper
    def test_calculate_discount_undefined_variable_no_try_except(self):
        code = (
            "def calculate_discount(price, discount):\n"
            "    discount_amount = price * discount / 100\n"
            "    final_price = price - discount_amnt\n"
            "    return final_price\n\n"
            "print(calculate_discount(1000, 20))\n"
        )
        traceback = (
            'Traceback (most recent call last):\n'
            '  File "main.py", line 6, in <module>\n'
            '    print(calculate_discount(1000, 20))\n'
            '  File "main.py", line 3, in calculate_discount\n'
            '    final_price = price - discount_amnt\n'
            "NameError: name 'discount_amnt' is not defined\n"
        )
        diagnosis = self.ai_service.diagnose_error('python', code, traceback)
        self.assertEqual(diagnosis['errorType'], 'NameError')
        
        # Test generic synthesizer directly to ensure fallback never adds try/except
        patch_result = self.ai_service._generate_generic_patch(code, diagnosis)
        self.assertTrue(patch_result['canSynthesize'])
        self.assertNotIn("try:", patch_result['fullFixedCode'])
        self.assertNotIn("except NameError:", patch_result['fullFixedCode'])
        self.assertIn("discount_amount", patch_result['fullFixedCode'])
        self.assertNotIn("discount_amnt", patch_result['fullFixedCode'])

        # Verify that the fixed code actually runs and outputs 800.0
        exec_res = self.verifier.verify_code('python', patch_result['fullFixedCode'], expected_output='800.0')
        self.assertEqual(exec_res['status'], 'verified')
        self.assertTrue(exec_res['passed'])

    # 2. AI response that returns the exact unchanged buggy code is rejected
    def test_ai_response_unchanged_code_rejected(self):
        code = "x = 10\nprint(x + '5')\n"
        diagnosis = {'errorType': 'TypeError', 'culpritLine': 2, 'summary': 'TypeError'}
        
        # Mock Ollama returning the exact same code
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': json.dumps({
                'summary': 'Fake fix',
                'explanation': 'Unchanged',
                'affectedLines': 'Line 2',
                'originalSnippet': "print(x + '5')",
                'fixedSnippet': "print(x + '5')",
                'fullFixedCode': code
            })
        }
        
        with patch('requests.post', return_value=mock_response):
            fix = self.ai_service._call_ollama_for_fix(code, "traceback", diagnosis)
            self.assertIsNone(fix, "AI response returning unchanged buggy code must be rejected")

    # 3. AI response that is empty or malformed is rejected
    def test_ai_response_empty_or_malformed_rejected(self):
        code = "a = 1"
        diagnosis = {'errorType': 'TypeError', 'culpritLine': 1, 'summary': 'TypeError'}

        # Case A: Empty response
        mock_res1 = MagicMock()
        mock_res1.status_code = 200
        mock_res1.json.return_value = {'response': ''}
        with patch('requests.post', return_value=mock_res1):
            self.assertIsNone(self.ai_service._call_ollama_for_fix(code, "", diagnosis))

        # Case B: Malformed JSON
        mock_res2 = MagicMock()
        mock_res2.status_code = 200
        mock_res2.json.return_value = {'response': 'not valid json {{{'}
        with patch('requests.post', return_value=mock_res2):
            self.assertIsNone(self.ai_service._call_ollama_for_fix(code, "", diagnosis))

        # Case C: Syntax error in proposed fullFixedCode
        mock_res3 = MagicMock()
        mock_res3.status_code = 200
        mock_res3.json.return_value = {
            'response': json.dumps({
                'fullFixedCode': 'def broken(:\n    pass'
            })
        }
        with patch('requests.post', return_value=mock_res3):
            self.assertIsNone(self.ai_service._call_ollama_for_fix(code, "", diagnosis))

    # 4. Code that completes with exit code 0 but incorrect output is marked Failed
    def test_clean_exit_with_incorrect_output_marked_failed(self):
        code = "print('Hello World')\n"
        res = self.verifier.verify_code('python', code, expected_output='Goodbye World')
        self.assertEqual(res['status'], 'failed')
        self.assertFalse(res['passed'])
        self.assertEqual(res['exitCode'], 0)
        self.assertFalse(res['assertionsPassed'])
        self.assertEqual(res['actualOutput'], 'Hello World')

    # 5. SyntaxError handling
    def test_syntax_error_handling(self):
        code = "print('Unclosed parenthesis'\n"
        traceback = (
            '  File "main.py", line 1\n'
            "    print('Unclosed parenthesis'\n"
            "                                ^\n"
            "SyntaxError: '(' was never closed\n"
        )
        diag = self.ai_service.diagnose_error('python', code, traceback)
        self.assertEqual(diag['errorType'], 'SyntaxError')
        patch_res = self.ai_service._generate_generic_patch(code, diag)
        self.assertNotIn("try:", patch_res['fullFixedCode'])
        if patch_res['canSynthesize']:
            # Must be valid python
            import ast
            ast.parse(patch_res['fullFixedCode'])
        else:
            self.assertTrue(patch_res['isUnmodified'])
            self.assertTrue(patch_res['noFixGenerated'])

    # 6. NameError handling
    def test_name_error_handling(self):
        code = "num = 42\nprint(nmu)\n"
        traceback = (
            '  File "main.py", line 2, in <module>\n'
            "    print(nmu)\n"
            "NameError: name 'nmu' is not defined. Did you mean: 'num'?\n"
        )
        diag = self.ai_service.diagnose_error('python', code, traceback)
        patch_res = self.ai_service._generate_generic_patch(code, diag)
        self.assertTrue(patch_res['canSynthesize'])
        self.assertIn("print(num)", patch_res['fullFixedCode'])
        self.assertNotIn("try:", patch_res['fullFixedCode'])

    # 7. TypeError handling
    def test_type_error_handling(self):
        code = "def concat(a, b):\n    return a + b\nprint(concat('result: ', 100))\n"
        traceback = (
            '  File "main.py", line 3, in <module>\n'
            "    print(concat('result: ', 100))\n"
            '  File "main.py", line 2, in concat\n'
            "    return a + b\n"
            "TypeError: can only concatenate str (not \"int\") to str\n"
        )
        diag = self.ai_service.diagnose_error('python', code, traceback)
        patch_res = self.ai_service._generate_generic_patch(code, diag)
        self.assertTrue(patch_res['canSynthesize'])
        v_res = self.verifier.verify_code('python', patch_res['fullFixedCode'])
        self.assertEqual(v_res['status'], 'verified')
        self.assertTrue(v_res['passed'])

    # 8. IndexError handling
    def test_index_error_handling(self):
        code = "items = [1, 2]\nval = items[5]\nprint(val)\n"
        traceback = (
            '  File "main.py", line 2, in <module>\n'
            "    val = items[5]\n"
            "IndexError: list index out of range\n"
        )
        diag = self.ai_service.diagnose_error('python', code, traceback)
        patch_res = self.ai_service._generate_generic_patch(code, diag)
        self.assertTrue(patch_res['canSynthesize'])
        v_res = self.verifier.verify_code('python', patch_res['fullFixedCode'])
        self.assertEqual(v_res['status'], 'verified')
        self.assertTrue(v_res['passed'])

    # 9. ZeroDivisionError handling
    def test_zero_division_error_handling(self):
        code = "def avg(nums):\n    return sum(nums) / len(nums)\nprint(avg([]))\n"
        traceback = (
            '  File "main.py", line 3, in <module>\n'
            "    print(avg([]))\n"
            '  File "main.py", line 2, in avg\n'
            "    return sum(nums) / len(nums)\n"
            "ZeroDivisionError: division by zero\n"
        )
        diag = self.ai_service.diagnose_error('python', code, traceback)
        patch_res = self.ai_service._generate_generic_patch(code, diag)
        self.assertTrue(patch_res['canSynthesize'])
        v_res = self.verifier.verify_code('python', patch_res['fullFixedCode'])
        self.assertEqual(v_res['status'], 'verified')
        self.assertTrue(v_res['passed'])

    # 10. Hand-off of manually edited code to the verifier
    def test_manual_edit_handoff_to_verifier(self):
        # User manually fixed code
        user_edited_code = "total = 10 + 20\nprint(f'Total is {total}')\n"
        res = self.verifier.verify_code('python', user_edited_code, expected_output='Total is 30')
        self.assertEqual(res['status'], 'verified')
        self.assertTrue(res['passed'])
        self.assertEqual(res['actualOutput'], 'Total is 30')

    # 11. Ollama availability check
    def test_ollama_availability_check(self):
        # When unreachable:
        with patch('requests.get', side_effect=Exception('Connection refused')):
            status = self.ai_service.get_status(force_refresh=True)
            self.assertFalse(status['available'])
            self.assertEqual(status['status'], 'offline')

        # When reachable:
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {'models': [{'name': 'qwen2.5:0.5b:latest'}]}
        with patch('requests.get', return_value=mock_get):
            status = self.ai_service.get_status(force_refresh=True)
            self.assertTrue(status['available'])
            self.assertEqual(status['status'], 'ready')

    # 12. Full end-to-end API workflow from diagnosis to verification
    def test_full_api_workflow(self):
        code = (
            "def calculate_discount(price, discount):\n"
            "    discount_amount = price * discount / 100\n"
            "    final_price = price - discount_amnt\n"
            "    return final_price\n\n"
            "print(calculate_discount(1000, 20))\n"
        )
        traceback = (
            'Traceback (most recent call last):\n'
            '  File "main.py", line 6, in <module>\n'
            '    print(calculate_discount(1000, 20))\n'
            '  File "main.py", line 3, in calculate_discount\n'
            '    final_price = price - discount_amnt\n'
            "NameError: name 'discount_amnt' is not defined\n"
        )

        # Step 1: Diagnose
        diag_resp = self.client.post('/api/diagnose', json={
            'language': 'python',
            'code': code,
            'traceback': traceback
        })
        self.assertEqual(diag_resp.status_code, 200)
        diag_json = diag_resp.get_json()
        self.assertTrue(diag_json['success'])
        diag_data = diag_json['diagnosis']
        self.assertEqual(diag_data['errorType'], 'NameError')

        # Step 2: Propose patch
        patch_resp = self.client.post('/api/propose-fix', json={
            'language': 'python',
            'code': code,
            'traceback': traceback,
            'diagnosis': diag_data
        })
        self.assertEqual(patch_resp.status_code, 200)
        patch_json = patch_resp.get_json()
        patch_data = patch_json.get('proposedFix', {})
        self.assertTrue(patch_data.get('canSynthesize', False) or patch_data.get('aiGenerated', False))
        fixed_code = patch_data.get('fullFixedCode')
        self.assertIsNotNone(fixed_code)

        # Step 3: Verify approved code
        verify_resp = self.client.post('/api/verify', json={
            'language': 'python',
            'approvedCode': fixed_code,
            'expectedOutput': '800.0'
        })
        self.assertEqual(verify_resp.status_code, 200)
        verify_json = verify_resp.get_json()
        verify_data = verify_json.get('verification', {})
        self.assertEqual(verify_data['status'], 'verified')
        self.assertTrue(verify_data['passed'])

if __name__ == '__main__':
    unittest.main()
