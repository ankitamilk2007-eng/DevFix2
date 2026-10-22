import ast
import os
import re
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from .base_adapter import BaseLanguageAdapter

class PythonAdapter(BaseLanguageAdapter):
    @property
    def language_id(self) -> str:
        return 'python'

    @property
    def language_name(self) -> str:
        return 'Python'

    @property
    def is_enabled(self) -> bool:
        return True

    def parse_traceback(self, traceback_text: str) -> dict:
        """
        Extracts concrete facts from standard Python tracebacks.
        Separates call stack facts from diagnostic inference.
        """
        lines = [line.strip() for line in (traceback_text or '').strip().split('\n') if line.strip()]
        error_type = 'UnknownError'
        error_message = 'An unhandled exception occurred.'
        culprit_line = None
        file_name = 'unknown.py'
        culprit_code = ''
        stack_frames = []

        standard_errors = [
            'ZeroDivisionError', 'IndexError', 'KeyError', 'TypeError', 'ValueError',
            'AttributeError', 'NameError', 'SyntaxError', 'IndentationError', 'FileNotFoundError',
            'ImportError', 'ModuleNotFoundError', 'RecursionError', 'StopIteration', 'AssertionError',
            'UnboundLocalError', 'MemoryError', 'OverflowError', 'RuntimeError'
        ]

        # Scan for exception line (usually at end of traceback)
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            for err in standard_errors:
                if line.startswith(err):
                    error_type = err
                    colon_idx = line.find(':')
                    error_message = line[colon_idx + 1:].strip() if colon_idx != -1 else line
                    break
            if error_type != 'UnknownError':
                break

        # Scan for File "..." or File '...', line X, in ...
        file_line_pattern = re.compile(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n\r]+))?')
        for i, line in enumerate(lines):
            match = file_line_pattern.search(line)
            if match:
                file_name = match.group(1)
                culprit_line = int(match.group(2))
                scope = f" in {match.group(3)}" if match.group(3) else ''
                stack_frames.append(f"Stack frame: {file_name} line {culprit_line}{scope}")
                
                # Check next line for culprit code
                if i + 1 < len(lines) and not lines[i + 1].startswith('File '):
                    culprit_code = lines[i + 1]

        traceback_facts = [
            f"Exception: {error_type}",
            f"Error message: {error_message}",
            f"Culprit location: {file_name} on line {culprit_line if culprit_line else 'unknown'}"
        ]
        if stack_frames:
            traceback_facts.extend(stack_frames)

        return {
            'errorType': error_type,
            'errorMessage': error_message,
            'culpritLine': culprit_line,
            'fileName': file_name,
            'culpritCode': culprit_code,
            'tracebackFacts': traceback_facts
        }

    def analyze_source(self, code: str) -> dict:
        """
        Parses source code into AST to detect syntax errors and structure.
        """
        try:
            tree = ast.parse(code)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            return {
                'valid_syntax': True,
                'functions': functions,
                'classes': classes,
                'error': None
            }
        except SyntaxError as e:
            return {
                'valid_syntax': False,
                'functions': [],
                'classes': [],
                'error': {
                    'message': str(e.msg),
                    'line': e.lineno,
                    'offset': e.offset
                }
            }

    def run_tests(self, code: str, tests: list = None, expected_output: str = None, timeout_seconds: int = 5) -> dict:
        """
        Executes real test runner in an isolated Python subprocess with a strict timeout.
        Never marks a fix as verified unless tests actually execute and pass with exit code 0.
        If expected_output is provided, validates that program stdout matches expected_output.
        """
        start_time = time.perf_counter()
        tests = tests or []

        # Check syntax first
        ast_check = self.analyze_source(code)
        if not ast_check['valid_syntax']:
            return {
                'status': 'failed',
                'testsExecuted': 0,
                'testsPassed': 0,
                'testsFailed': 1,
                'scope': 'Python Syntax Check',
                'testCases': [{
                    'name': 'SyntaxCheck',
                    'input': 'Source code AST parse',
                    'expected': 'Valid Python syntax',
                    'actual': f"SyntaxError: {ast_check['error']['message']} on line {ast_check['error']['line']}",
                    'status': 'failed'
                }],
                'stdout': '',
                'stderr': f"SyntaxError: {ast_check['error']['message']} at line {ast_check['error']['line']}",
                'executionTimeMs': int((time.perf_counter() - start_time) * 1000),
                'actualOutput': '',
                'expectedOutput': expected_output,
                'exitCode': 1,
                'passed': False,
                'assertionsPassed': False
            }

        # Build isolated test script
        test_script_content = self._build_test_script(code, tests)

        # Use ignore_cleanup_errors to prevent Windows lock conflicts on temp folder removal
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir) / 'test_runner.py'
            temp_path.write_text(test_script_content, encoding='utf-8')

            try:
                # Inherit environment so Windows DLLs, SYSTEMROOT, PATH, and temp dirs are preserved
                run_env = os.environ.copy()
                run_env['PYTHONPATH'] = temp_dir
                run_env['PYTHONDONTWRITEBYTECODE'] = '1'

                result = subprocess.run(
                    [sys.executable, str(temp_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=temp_dir,
                    env=run_env
                )
                
                execution_time = int((time.perf_counter() - start_time) * 1000)
                stdout = result.stdout or ''
                stderr = result.stderr or ''

                # Parse unittest execution output
                parsed_results = self._parse_test_output(result.returncode, stdout, stderr, tests, expected_output=expected_output)
                parsed_results['executionTimeMs'] = execution_time
                return parsed_results

            except subprocess.TimeoutExpired:
                return {
                    'status': 'failed',
                    'testsExecuted': len(tests) if tests else 1,
                    'testsPassed': 0,
                    'testsFailed': 1,
                    'scope': f"Subprocess timed out after {timeout_seconds}s limit",
                    'testCases': [{
                        'name': 'TimeoutCheck',
                        'input': f"Execution exceeded {timeout_seconds}s",
                        'expected': 'Completion within time limit',
                        'actual': 'Timed out (possible infinite loop)',
                        'status': 'failed'
                    }],
                    'stdout': '',
                    'stderr': f"Process timed out after {timeout_seconds} seconds.",
                    'executionTimeMs': int((time.perf_counter() - start_time) * 1000)
                }
            except Exception as e:
                return {
                    'status': 'unverified',
                    'testsExecuted': 0,
                    'testsPassed': 0,
                    'testsFailed': 0,
                    'scope': 'Execution environment error',
                    'testCases': [],
                    'stdout': '',
                    'stderr': f"Failed to launch test runner: {str(e)}",
                    'executionTimeMs': int((time.perf_counter() - start_time) * 1000)
                }

    def _build_test_script(self, code: str, tests: list) -> str:
        """
        Creates an executable test suite combining source code with unit test assertions.
        Supports:
        - Clean runtime execution checks (when tests is empty)
        - Direct assertions ('assert ...')
        - Expected vs. actual output comparisons ('input' + 'expected')
        """
        if not tests:
            # If no explicit unit tests provided, verify source code executes cleanly in a real unittest
            return f"""import unittest
import sys
import traceback

class DevFixExecutionSuite(unittest.TestCase):
    def test_clean_execution(self):
        \"\"\"Verifies source code executes cleanly without uncaught runtime exceptions.\"\"\"
        code_str = {repr(code)}
        exec_globals = {{'__name__': '__main__', '__file__': 'test_runner.py'}}
        try:
            exec(compile(code_str, 'test_runner.py', 'exec'), exec_globals)
        except Exception as e:
            self.fail(f"Runtime exception {{type(e).__name__}}: {{e}}\\n{{traceback.format_exc()}}")

if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DevFixExecutionSuite)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
"""

        # Generate unittest suite for explicit test cases
        test_methods = []
        for i, t in enumerate(tests):
            raw_name = t.get('name', f"test_case_{i+1}")
            t_name = re.sub(r'\W|^(?=\d)', '_', raw_name)
            t_assert = t.get('assertion', '')
            t_input = t.get('input', '')
            t_expected = t.get('expected', None)

            if t_assert:
                test_body = f"        {t_assert}"
            elif t_input and t_input.strip().startswith('assert '):
                test_body = f"        {t_input.strip()}"
            elif t_input and t_expected is not None:
                lines = [l for l in t_input.strip().split('\n') if l.strip()]
                if len(lines) == 1 and not lines[0].strip().startswith(('import ', 'from ', 'def ', 'class ')):
                    test_body = f"""        import ast
        expected_raw = {repr(str(t_expected))}
        try:
            expected_val = ast.literal_eval(expected_raw)
        except Exception:
            expected_val = expected_raw
        actual = ({lines[0].strip()})
        if actual != expected_val and str(actual) != str(expected_raw):
            self.assertEqual(actual, expected_val)"""
                else:
                    prefix = '\n        '.join(lines[:-1])
                    last_line = lines[-1].strip()
                    test_body = f"""        import ast
        expected_raw = {repr(str(t_expected))}
        try:
            expected_val = ast.literal_eval(expected_raw)
        except Exception:
            expected_val = expected_raw
        {prefix}
        actual = ({last_line})
        if actual != expected_val and str(actual) != str(expected_raw):
            self.assertEqual(actual, expected_val)"""
            elif t_input:
                indented = '\n        '.join(t_input.strip().split('\n'))
                test_body = f"        {indented}"
            else:
                test_body = "        pass"

            test_methods.append(f"""
    def {t_name}(self):
{test_body}
""")

        return f"""import unittest
import sys
import traceback

# Injected Tested Source Code
{code}

class DevFixTestSuite(unittest.TestCase):
{''.join(test_methods)}

if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DevFixTestSuite)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
"""

    def _parse_test_output(self, returncode: int, stdout: str, stderr: str, original_tests: list, expected_output: str = None) -> dict:
        total_tests = max(len(original_tests), 1)
        test_cases = []

        if original_tests:
            for i, t in enumerate(original_tests):
                raw_name = t.get('name', f"test_case_{i+1}")
                method_name = re.sub(r'\W|^(?=\d)', '_', raw_name)
                
                # Check for unittest result in stderr
                passed = bool(re.search(rf'{re.escape(method_name)}.*?\.\.\. ok', stderr))
                expected_str = str(t.get('expected', 'Passes without error'))

                if passed and returncode == 0:
                    status = 'passed'
                    actual = expected_str if t.get('expected') is not None else 'Passed'
                else:
                    status = 'failed'
                    # Extract failure snippet from stderr if available
                    fail_match = re.search(rf'(?:FAIL|ERROR):\s+{re.escape(method_name)}[\s\S]*?(?:AssertionError:\s*(.*?)|(TypeError:.*?)|(ZeroDivisionError:.*?)|(IndexError:.*?)|(Exception:.*?))(?=\n-|\n=|\Z)', stderr)
                    if fail_match:
                        matched_msg = next((m for m in fail_match.groups() if m), None)
                        actual = matched_msg.strip() if matched_msg else 'Assertion failed'
                    else:
                        actual = 'Test assertion failed or runtime exception occurred'

                test_cases.append({
                    'name': raw_name,
                    'input': t.get('input', 'Default test execution'),
                    'expected': expected_str,
                    'actual': actual,
                    'status': status
                })

            tests_passed = sum(1 for tc in test_cases if tc['status'] == 'passed')
            tests_failed = sum(1 for tc in test_cases if tc['status'] == 'failed')
            overall_status = 'verified' if (returncode == 0 and tests_failed == 0) else 'failed'
        else:
            if returncode == 0:
                tests_passed = 1
                tests_failed = 0
                overall_status = 'verified'
                test_cases.append({
                    'name': 'test_clean_execution',
                    'input': 'Run source code',
                    'expected': 'Exit code 0 (no runtime exception)',
                    'actual': 'Passed cleanly (exit code 0)',
                    'status': 'passed'
                })
            else:
                tests_passed = 0
                tests_failed = 1
                overall_status = 'failed'
                # Extract exception from stderr
                err_match = re.search(r'Runtime exception ([^\n]+)', stderr)
                actual_err = err_match.group(1) if err_match else f"Process returned exit code {returncode}"
                test_cases.append({
                    'name': 'test_clean_execution',
                    'input': 'Run source code',
                    'expected': 'Exit code 0 (no runtime exception)',
                    'actual': actual_err,
                    'status': 'failed'
                })

        actual_output = stdout.strip()
        passed_flag = (overall_status == 'verified')
        assertions_passed = (tests_failed == 0 and returncode == 0)

        # If expected_output is specified, strictly check stdout
        if expected_output is not None:
            total_tests += 1
            exp_clean = str(expected_output).strip()
            if actual_output == exp_clean and returncode == 0:
                tests_passed += 1
                test_cases.append({
                    'name': 'ExpectedOutputCheck',
                    'input': 'Program stdout',
                    'expected': exp_clean,
                    'actual': actual_output,
                    'status': 'passed'
                })
            else:
                tests_failed += 1
                overall_status = 'failed'
                passed_flag = False
                assertions_passed = False
                test_cases.append({
                    'name': 'ExpectedOutputCheck',
                    'input': 'Program stdout',
                    'expected': exp_clean,
                    'actual': actual_output,
                    'status': 'failed'
                })

        return {
            'status': overall_status,
            'passed': passed_flag,
            'assertionsPassed': assertions_passed,
            'testsExecuted': total_tests,
            'testsPassed': tests_passed,
            'testsFailed': tests_failed,
            'exitCode': returncode,
            'actualOutput': actual_output,
            'expectedOutput': expected_output,
            'scope': f"Controlled Python unittest runner ({total_tests} checks executed)",
            'testCases': test_cases,
            'stdout': stdout,
            'stderr': stderr
        }
