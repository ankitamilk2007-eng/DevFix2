"""
DevFix AI — General Python Pipeline Regression Suite
Tests:
1. General Python Error Classes:
   - SyntaxError (missing colons, brackets, malformed syntax)
   - NameError (typos with suggestions, undeclared variables)
   - AttributeError (typos with suggestions, NoneType access)
   - ZeroDivisionError (empty sequences, zero denominators)
   - IndexError (off-by-one loop boundaries, out-of-range indexing)
   - TypeError (incompatible operand concatenation, invalid types)
2. Negative Tests:
   - Broken fixes fail verification (never falsely report success)
   - Clean execution without crash is NOT sufficient if expected outputs mismatch
   - Unfixable code honestly reports noFixGenerated=True and isUnmodified=True
3. Arbitrary unseen code structures, variables, and inputs.
"""

import unittest
from backend.services.ai_service import AIService
from backend.services.verifier_service import VerifierService
from backend.language_adapters.python_adapter import PythonAdapter

class TestGeneralPythonPipeline(unittest.TestCase):
    def setUp(self):
        self.ai = AIService()
        self.adapter = PythonAdapter()
        self.verifier = VerifierService()

    # =========================================================================
    # 1. SyntaxError General Tests
    # =========================================================================
    def test_syntax_error_missing_colon_on_def_fixed_and_verified(self):
        """SyntaxError with missing colon on def header is repaired and verified."""
        code = "def compute_magnitude(vector)\n    return sum(x*x for x in vector)\n\nprint(compute_magnitude([3, 4]))"
        tb = """  File "geometry.py", line 1
    def compute_magnitude(vector)
                                 ^
SyntaxError: expected ':'"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'SyntaxError')
        
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertFalse(fix['isUnmodified'])
        self.assertIn("def compute_magnitude(vector):", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')
        self.assertEqual(res['testsPassed'], 1)

    def test_syntax_error_missing_colon_on_if_fixed_and_verified(self):
        """SyntaxError with missing colon on if statement is repaired and verified."""
        code = "def validate_age(user_age):\n    if user_age >= 18\n        return True\n    return False\n\nprint(validate_age(20))"
        tb = """  File "auth.py", line 2
    if user_age >= 18
                     ^
SyntaxError: expected ':'"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertIn("if user_age >= 18:", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')

    def test_syntax_error_unclosed_parenthesis_fixed_and_verified(self):
        """SyntaxError with unclosed parenthesis is repaired and verified."""
        code = "total = sum([1, 2, 3, 4\nprint(total)"
        tb = """  File "calc.py", line 1
    total = sum([1, 2, 3, 4
           ^
SyntaxError: '(' was never closed"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        if fix['canSynthesize']:
            res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
            self.assertEqual(res['status'], 'verified')

    def test_syntax_error_unfixable_reports_no_fix_honestly(self):
        """Completely broken syntax that cannot be safely deduced reports noFixGenerated honestly."""
        code = "def %$#@ invalid syntax !!!"
        tb = """  File "broken.py", line 1
    def %$#@ invalid syntax !!!
        ^
SyntaxError: invalid syntax"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertFalse(fix['canSynthesize'])
        self.assertTrue(fix['isUnmodified'])
        self.assertTrue(fix.get('noFixGenerated'))
        # And running verification on this unchanged code MUST fail
        res = self.verifier.verify_fix('python', original_code=code, proposed_code=code)
        self.assertEqual(res['status'], 'failed')

    # =========================================================================
    # 2. NameError General Tests
    # =========================================================================
    def test_name_error_with_typo_suggestion_fixed_and_verified(self):
        """NameError with suggestion (e.g. qty -> quantity) is corrected and verified."""
        code = "def calc_cost(unit_price, quantity):\n    return unit_price * qty\n\nprint(calc_cost(15, 4))"
        tb = """Traceback (most recent call last):
  File "invoice.py", line 2, in calc_cost
    return unit_price * qty
NameError: name 'qty' is not defined. Did you mean: 'quantity'?"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'NameError')
        
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertIn("unit_price * quantity", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')
        self.assertIn("60", res['stdout'])

    def test_name_error_negative_test_fails_without_correction(self):
        """NameError without fix fails verification."""
        code = "print(completely_nonexistent_symbol_12345)"
        res = self.verifier.verify_fix('python', original_code=code, proposed_code=code)
        self.assertEqual(res['status'], 'failed')
        self.assertIn('NameError', res['stderr'])

    # =========================================================================
    # 3. AttributeError General Tests
    # =========================================================================
    def test_attribute_error_typo_suggestion_fixed_and_verified(self):
        """AttributeError with suggestion (e.g. append_elem -> append) is corrected and verified."""
        code = "def push_all(items, val):\n    items.append_elem(val)\n    return items\n\nprint(push_all([10], 20))"
        tb = """Traceback (most recent call last):
  File "collections.py", line 2, in push_all
    items.append_elem(val)
AttributeError: 'list' object has no attribute 'append_elem'. Did you mean: 'append'?"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'AttributeError')

        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertIn("items.append(val)", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')
        self.assertIn("[10, 20]", res['stdout'])

    def test_attribute_error_on_none_defensive_guard_verified(self):
        """AttributeError on NoneType is wrapped with defensive guard and passes clean execution."""
        code = "def fetch_title(record):\n    return record.title\n\nprint(fetch_title(None))"
        tb = """Traceback (most recent call last):
  File "db.py", line 2, in fetch_title
    return record.title
AttributeError: 'NoneType' object has no attribute 'title'"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')

    # =========================================================================
    # 4. ZeroDivisionError General Tests
    # =========================================================================
    def test_zero_division_unseen_variable_names_guarded(self):
        """ZeroDivisionError with completely custom names (measurements, total_sum, count_items)."""
        code = "def compute_stats(measurements):\n    count_items = len(measurements)\n    total_sum = sum(measurements)\n    return total_sum / count_items\n\nprint(compute_stats([]))"
        tb = """Traceback (most recent call last):
  File "telemetry.py", line 4, in compute_stats
    return total_sum / count_items
ZeroDivisionError: division by zero"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'ZeroDivisionError')

        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertIn("if not measurements:", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')
        self.assertIn("0.0", res['stdout'])

    # =========================================================================
    # 5. IndexError General Tests
    # =========================================================================
    def test_index_error_unseen_variable_names_loop_boundary_fixed(self):
        """IndexError with custom variable names (waveforms, sample_idx) loop boundary corrected."""
        code = "def find_transitions(waveforms):\n    transitions = []\n    for sample_idx in range(1, len(waveforms)):\n        if waveforms[sample_idx] != waveforms[sample_idx + 1]:\n            transitions.append(sample_idx)\n    return transitions\n\nprint(find_transitions([0, 1, 1, 0]))"
        tb = """Traceback (most recent call last):
  File "dsp.py", line 4, in find_transitions
    if waveforms[sample_idx] != waveforms[sample_idx + 1]:
IndexError: list index out of range"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'IndexError')

        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])
        self.assertIn("len(waveforms) - 1", fix['fullFixedCode'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')
        self.assertIn("[2]", res['stdout'])

    # =========================================================================
    # 6. TypeError General Tests
    # =========================================================================
    def test_type_error_unseen_variables_fixed_and_verified(self):
        """TypeError with string and integer concatenation across custom variables."""
        code = "def make_label(metric_name, metric_value):\n    return metric_name + ': ' + metric_value\n\nprint(make_label('CPU_LOAD', 98))"
        tb = """Traceback (most recent call last):
  File "monitor.py", line 2, in make_label
    return metric_name + ': ' + metric_value
TypeError: can only concatenate str (not "int") to str"""
        diag = self.ai.generate_diagnosis('python', code, tb)
        self.assertEqual(diag['errorType'], 'TypeError')

        fix = self.ai.generate_proposed_fix('python', code, tb, diag)
        self.assertTrue(fix['canSynthesize'])

        res = self.verifier.verify_fix('python', original_code=code, proposed_code=fix['fullFixedCode'])
        self.assertEqual(res['status'], 'verified')

    # =========================================================================
    # 7. Verification Honesty & Output Assertion Tests (Negative Tests)
    # =========================================================================
    def test_clean_start_does_not_pass_when_explicit_test_assertion_fails(self):
        """
        Critical Requirement: Never report success solely because code starts without crashing.
        If a program exits with code 0 but returns 10 instead of expected 25, verification MUST FAIL.
        """
        code = "def calculate_power(base, exp):\n    return base + exp  # Buggy implementation returning sum instead of power\n"
        tests = [
            {'name': 'test_power_of_two', 'input': 'calculate_power(5, 2)', 'expected': '25'}
        ]
        res = self.verifier.verify_fix('python', original_code=code, proposed_code=code, tests=tests)
        self.assertEqual(res['status'], 'failed', "Must NOT pass just because code executed without crash")
        self.assertEqual(res['testsFailed'], 1)
        self.assertEqual(res['testsPassed'], 0)
        self.assertEqual(res['testCases'][0]['status'], 'failed')

    def test_broken_fix_never_marked_verified(self):
        """If a proposed patch still raises an exception, verifier must mark it failed."""
        broken_patch = "def divide(a, b):\n    return a / b\nprint(divide(10, 0))"
        res = self.verifier.verify_fix('python', original_code="...", proposed_code=broken_patch)
        self.assertEqual(res['status'], 'failed')
        self.assertEqual(res['testsFailed'], 1)
        self.assertEqual(res['testsPassed'], 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
