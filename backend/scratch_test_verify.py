import sys
sys.path.insert(0, '.')
from backend.services.ai_service import ai_service
from backend.services.verifier_service import verifier_service
from backend.language_adapters.python_adapter import PythonAdapter

code = """def calculate_average_score(scores):
    \"\"\"
    Computes arithmetic mean of test scores.
    Returns 0.0 if scores list is empty.
    \"\"\"
    total = sum(scores)
    count = len(scores)
    average = total / count
    return round(average, 2)

# Calling with empty dataset triggers crash:
results = calculate_average_score([])
print(f"Average: {results}")"""

tb = """Traceback (most recent call last):
  File "grade_analytics.py", line 12, in <module>
    results = calculate_average_score([])
  File "grade_analytics.py", line 8, in calculate_average_score
    average = total / count
ZeroDivisionError: division by zero"""

diag = ai_service.generate_diagnosis('python', code, tb)
print("DIAGNOSIS:", diag)

fix = ai_service.generate_proposed_fix('python', code, tb, diag)
print("\nFIX FULL CODE:\n", fix.get('fullFixedCode'))

# Test 1: verification with auto-detected tests
v1 = verifier_service.verify_fix('python', code, fix.get('fullFixedCode'), tests=[])
print("\nVERIFICATION 1 (tests=[]):", v1)

# Test 2: verification without auto-detected tests (raw code execution)
adapter = PythonAdapter()
v2 = adapter.run_tests(fix.get('fullFixedCode'), tests=[])
print("\nVERIFICATION 2 (raw adapter tests=[]):", v2)

# Test 3: verification with the original broken code
v3 = adapter.run_tests(code, tests=[])
print("\nVERIFICATION 3 (original broken code tests=[]):", v3)
