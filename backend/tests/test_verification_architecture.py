"""
DevFix AI — Verification Architecture & Data Handoff Regression Test Suite
Validates:
1. Verifier executes the exact approved code, preserving originalCode.
2. General regression tests: TypeError, IndexError, ZeroDivisionError, SyntaxError, Correct Program, Wrong Output Program.
3. Explicit test case assertions comparing actual vs expected outputs.
4. Subprocess execution isolation & timeouts.
5. Verification status contract: 'verified' ONLY when all tests pass, 'failed' on failure, 'unverified' when runner cannot execute.
"""

import sys
import unittest
from backend.language_adapters.python_adapter import PythonAdapter
from backend.services.verifier_service import VerifierService
from backend.services.ai_service import ai_service

class TestVerificationArchitecture(unittest.TestCase):
    def setUp(self):
        self.adapter = PythonAdapter()
        self.verifier = VerifierService()

    # -------------------------------------------------------------------------
    # 1. TypeError Handling (e.g. int + str)
    # -------------------------------------------------------------------------
    def test_type_error_broken_code_fails_verification(self):
        """Unfixed TypeError must fail verification with clear failure details."""
        code = "total = 42 + 'items'\nprint(total)"
        result = self.verifier.verify_fix('python', original_code=code, proposed_code=code, tests=[])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testsFailed'], 1)
        self.assertEqual(result['testsPassed'], 0)
        self.assertIn('TypeError', result['stderr'])
        self.assertEqual(result['originalCode'], code)
        self.assertEqual(result['verifiedCode'], code)

    def test_type_error_approved_fixed_code_passes_verification(self):
        """Fixed TypeError (e.g. with str coercion) must execute cleanly and pass."""
        original = "total = 42 + 'items'\nprint(total)"
        fixed = "total = str(42) + 'items'\nprint(total)"
        result = self.verifier.verify_fix('python', original_code=original, proposed_code=fixed, tests=[])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)
        self.assertEqual(result['testsFailed'], 0)
        self.assertEqual(result['testCases'][0]['status'], 'passed')
        self.assertEqual(result['originalCode'], original)
        self.assertEqual(result['verifiedCode'], fixed)

    # -------------------------------------------------------------------------
    # 2. IndexError Handling
    # -------------------------------------------------------------------------
    def test_index_error_broken_code_fails(self):
        """Index out of bounds must fail verification."""
        code = "items = [1, 2, 3]\nprint(items[5])"
        result = self.verifier.verify_fix('python', original_code=code, proposed_code=code, tests=[])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testsFailed'], 1)
        self.assertIn('IndexError', result['stderr'])

    def test_index_error_fixed_code_passes(self):
        """Fixed IndexError with bounds check passes clean execution."""
        original = "items = [1, 2, 3]\nprint(items[5])"
        fixed = "items = [1, 2, 3]\nidx = 5\nprint(items[idx] if idx < len(items) else None)"
        result = self.verifier.verify_fix('python', original_code=original, proposed_code=fixed, tests=[])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)

    # -------------------------------------------------------------------------
    # 3. ZeroDivisionError Handling
    # -------------------------------------------------------------------------
    def test_zerodivision_broken_code_fails(self):
        """Division by zero must fail verification."""
        code = "a = 100\nb = 0\nprint(a / b)"
        result = self.verifier.verify_fix('python', original_code=code, proposed_code=code, tests=[])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testsFailed'], 1)
        self.assertIn('ZeroDivisionError', result['stderr'])

    def test_zerodivision_fixed_code_passes(self):
        """Fixed ZeroDivisionError with guard passes verification."""
        original = "a = 100\nb = 0\nprint(a / b)"
        fixed = "a = 100\nb = 0\nprint(a / b if b != 0 else 0.0)"
        result = self.verifier.verify_fix('python', original_code=original, proposed_code=fixed, tests=[])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)

    # -------------------------------------------------------------------------
    # 4. SyntaxError Handling
    # -------------------------------------------------------------------------
    def test_syntax_error_fails_immediately(self):
        """Invalid Python syntax must be caught by AST parser and reported as failed."""
        bad_syntax_code = "def broken(\n  return 42"
        result = self.verifier.verify_fix('python', original_code="pass", proposed_code=bad_syntax_code, tests=[])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testsFailed'], 1)
        self.assertEqual(result['testCases'][0]['name'], 'SyntaxCheck')
        self.assertIn('SyntaxError', result['stderr'])

    # -------------------------------------------------------------------------
    # 5. Clean Correct Program
    # -------------------------------------------------------------------------
    def test_correct_program_clean_execution(self):
        """A valid Python script with no runtime errors passes test_clean_execution."""
        valid_code = "names = ['Alice', 'Bob']\nfor n in names:\n    print(f'Hello {n}')"
        result = self.verifier.verify_fix('python', original_code=valid_code, proposed_code=valid_code, tests=[])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)
        self.assertEqual(result['testCases'][0]['name'], 'test_clean_execution')
        self.assertEqual(result['testCases'][0]['status'], 'passed')

    # -------------------------------------------------------------------------
    # 6. Explicit Test Cases (Expected vs. Actual Output)
    # -------------------------------------------------------------------------
    def test_explicit_test_wrong_output_fails(self):
        """A function returning wrong output must fail the expected output assertion."""
        # Function returns sum instead of product
        buggy_func = "def multiply(a, b):\n    return a + b\n"
        tests = [
            {'name': 'test_multiply', 'input': 'multiply(3, 4)', 'expected': '12'}
        ]
        result = self.verifier.verify_fix('python', original_code=buggy_func, proposed_code=buggy_func, tests=tests)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testsFailed'], 1)
        self.assertEqual(result['testCases'][0]['name'], 'test_multiply')
        self.assertEqual(result['testCases'][0]['status'], 'failed')
        self.assertEqual(result['testCases'][0]['expected'], '12')

    def test_explicit_test_correct_output_passes(self):
        """A function returning the correct expected output passes verification."""
        fixed_func = "def multiply(a, b):\n    return a * b\n"
        tests = [
            {'name': 'test_multiply', 'input': 'multiply(3, 4)', 'expected': '12'}
        ]
        result = self.verifier.verify_fix('python', original_code="...", proposed_code=fixed_func, tests=tests)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)
        self.assertEqual(result['testCases'][0]['name'], 'test_multiply')
        self.assertEqual(result['testCases'][0]['status'], 'passed')
        self.assertEqual(result['testCases'][0]['expected'], '12')

    def test_explicit_test_list_output_comparison(self):
        """Verifies structured output (like list) compares correctly."""
        filter_func = "def filter_evens(nums):\n    return [n for n in nums if n % 2 == 0]\n"
        tests = [
            {'name': 'test_evens', 'input': 'filter_evens([1, 2, 3, 4, 5, 6])', 'expected': '[2, 4, 6]'}
        ]
        result = self.verifier.verify_fix('python', original_code="...", proposed_code=filter_func, tests=tests)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['testsPassed'], 1)
        self.assertEqual(result['testCases'][0]['status'], 'passed')

    # -------------------------------------------------------------------------
    # 7. Pipeline Data Handoff & Approved Code Integrity
    # -------------------------------------------------------------------------
    def test_handoff_executes_exact_approved_code(self):
        """
        Confirms original source is preserved and approved patch is what actually executes.
        If original code is buggy and proposed is fixed, verifier must report VERIFIED.
        If original code is fixed and proposed is buggy, verifier must report FAILED.
        """
        buggy_code = "x = 10 / 0"
        fixed_code = "x = 10 / 2"

        # Case A: buggy original, fixed proposed -> must pass!
        res_a = self.verifier.verify_fix('python', original_code=buggy_code, proposed_code=fixed_code, tests=[])
        self.assertEqual(res_a['status'], 'verified')
        self.assertEqual(res_a['originalCode'], buggy_code)
        self.assertEqual(res_a['verifiedCode'], fixed_code)

        # Case B: fixed original, buggy proposed -> must fail!
        res_b = self.verifier.verify_fix('python', original_code=fixed_code, proposed_code=buggy_code, tests=[])
        self.assertEqual(res_b['status'], 'failed')
        self.assertEqual(res_b['originalCode'], fixed_code)
        self.assertEqual(res_b['verifiedCode'], buggy_code)

    # -------------------------------------------------------------------------
    # 8. Timeout & Isolation Restrictions
    # -------------------------------------------------------------------------
    def test_infinite_loop_timeout_isolation(self):
        """Code with an infinite loop is terminated by subprocess timeout, reporting failed."""
        infinite_loop = "while True:\n    pass"
        result = self.adapter.run_tests(infinite_loop, tests=[], timeout_seconds=1)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['testCases'][0]['name'], 'TimeoutCheck')
        self.assertIn('timed out', result['stderr'].lower())

    # -------------------------------------------------------------------------
    # 9. Unverified State Contract
    # -------------------------------------------------------------------------
    def test_unsupported_language_returns_unverified(self):
        """When an adapter is unavailable, result MUST be 'unverified'."""
        result = self.verifier.verify_fix('rust', original_code="fn main() {}", proposed_code="fn main() {}")
        self.assertEqual(result['status'], 'unverified')
        self.assertEqual(result['testsExecuted'], 0)
        self.assertIn('UNVERIFIED', result['disclaimer'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
