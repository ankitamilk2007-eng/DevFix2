from ..language_adapters.python_adapter import PythonAdapter

class VerifierService:
    def __init__(self):
        self.adapters = {
            'python': PythonAdapter()
        }

    def verify_fix(self, language: str, original_code: str, proposed_code: str, tests: list = None, expected_output: str = None) -> dict:
        """
        Executes real test verification in an isolated subprocess.
        Strictly follows:
        - Verified: all checks actually ran and passed with returncode 0.
        - Failed: one or more checks failed.
        - Unverified: checks could not run or syntax error.
        """
        if language not in self.adapters:
            return {
                'status': 'unverified',
                'testsExecuted': 0,
                'testsPassed': 0,
                'testsFailed': 0,
                'scope': f"Verification runner for '{language}' is in development.",
                'testCases': [],
                'stdout': '',
                'stderr': f"Unsupported language '{language}' cannot be executed.",
                'disclaimer': 'UNVERIFIED: No execution runner exists for this language.'
            }

        adapter = self.adapters[language]
        
        # Execute tests on proposed code (delegates to test_clean_execution if tests is empty)
        result = adapter.run_tests(proposed_code, tests or [], expected_output=expected_output)
        result['isDemonstration'] = False
        result['originalCode'] = original_code
        result['verifiedCode'] = proposed_code
        return result

    def verify_code(self, language: str, code: str, tests: list = None, expected_output: str = None) -> dict:
        """Convenience method to verify execution of a single code snippet."""
        return self.verify_fix(language, original_code=code, proposed_code=code, tests=tests, expected_output=expected_output)

verifier_service = VerifierService()
