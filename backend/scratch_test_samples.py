import sys
sys.path.insert(0, '.')

from backend.services.ai_service import ai_service
from backend.services.verifier_service import verifier_service

sample1_code = """def calculate_average_score(scores):
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

sample1_tb = """Traceback (most recent call last):
  File "grade_analytics.py", line 12, in <module>
    results = calculate_average_score([])
  File "grade_analytics.py", line 8, in calculate_average_score
    average = total / count
ZeroDivisionError: division by zero"""

sample2_code = """def find_peaks(readings):
    \"\"\"
    Detects index positions where reading is greater than immediate neighbors.
    \"\"\"
    peaks = []
    # Loop boundary bug: accesses i+1 on the last element
    for i in range(1, len(readings)):
        if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
            peaks.append(i)
    return peaks

data = [10, 25, 18, 40, 30]
print("Detected peaks:", find_peaks(data))"""

sample2_tb = """Traceback (most recent call last):
  File "sensor_processor.py", line 12, in <module>
    print("Detected peaks:", find_peaks(data))
  File "sensor_processor.py", line 8, in find_peaks
    if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
IndexError: list index out of range"""

sample3_code = """def build_user_badge(user_profile):
    \"\"\"
    Constructs a formatted display badge like: "Dr. Jane Doe [ID: 42]"
    \"\"\"
    title = user_profile.get("title")  # may be None
    first = user_profile["first_name"]
    last = user_profile["last_name"]
    uid = user_profile["id"]

    # Crashes if title is None
    badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"
    return badge

user = {"first_name": "Alan", "last_name": "Turing", "id": 101, "title": None}
print(build_user_badge(user))"""

sample3_tb = """Traceback (most recent call last):
  File "user_service.py", line 14, in <module>
    print(build_user_badge(user))
  File "user_service.py", line 11, in build_user_badge
    badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"
TypeError: can only concatenate str (not "NoneType") to str"""

for idx, (code, tb) in enumerate([(sample1_code, sample1_tb), (sample2_code, sample2_tb), (sample3_code, sample3_tb)], 1):
    print(f"\n=================== SAMPLE {idx} ===================")
    diag = ai_service.generate_diagnosis('python', code, tb)
    fix = ai_service.generate_proposed_fix('python', code, tb, diag)
    proposed_code = fix.get('fullFixedCode', '')
    print("PROPOSED CODE:\n", proposed_code)
    
    # Run verification with tests=[] as the frontend sends
    v = verifier_service.verify_fix('python', code, proposed_code, tests=[])
    print("VERIFICATION STATUS:", v.get('status'))
    print("TEST CASES:", v.get('testCases'))
    if v.get('stderr'):
        print("STDERR:\n", v.get('stderr'))
