from abc import ABC, abstractmethod

class BaseLanguageAdapter(ABC):
    @property
    @abstractmethod
    def language_id(self) -> str:
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        pass

    @abstractmethod
    def parse_traceback(self, traceback_text: str) -> dict:
        """Extracts facts from runtime traceback/error messages."""
        pass

    @abstractmethod
    def analyze_source(self, code: str) -> dict:
        """Parses AST or syntax tree to check validity and node metadata."""
        pass

    @abstractmethod
    def run_tests(self, code: str, tests: list, timeout_seconds: int = 5) -> dict:
        """Executes controlled test runner in isolated environment."""
        pass
