/**
 * DevFix AI — Language Configuration & Adapters Matrix
 * 
 * Manages language availability, roadmap metadata, and curated debugging scenarios.
 * Strictly enforces that Python is the ONLY active language in initial release.
 */

export const SUPPORTED_LANGUAGES = [
  {
    id: 'python',
    name: 'Python',
    icon: '🐍',
    enabled: true,
    fileExtension: '.py',
    runtime: 'CPython 3.10+',
    statusText: 'Active',
    badgeClass: 'status-active',
    description: 'Full AST parsing, traceback frame analysis, and isolated test verification.'
  },
  {
    id: 'java',
    name: 'Java',
    icon: '☕',
    enabled: false,
    fileExtension: '.java',
    runtime: 'OpenJDK 17/21',
    statusText: 'Coming Soon',
    badgeClass: 'status-soon',
    description: 'StackTrace analysis and JUnit test execution currently in development.'
  },
  {
    id: 'c',
    name: 'C',
    icon: '⚙️',
    enabled: false,
    fileExtension: '.c',
    runtime: 'GCC / Clang',
    statusText: 'Coming Soon',
    badgeClass: 'status-soon',
    description: 'GCC diagnostic parsing and Valgrind memory verification in development.'
  },
  {
    id: 'cpp',
    name: 'C++',
    icon: '⚡',
    enabled: false,
    fileExtension: '.cpp',
    runtime: 'G++ 13+ / LLVM',
    statusText: 'Coming Soon',
    badgeClass: 'status-soon',
    description: 'Template error demangling and GoogleTest runner in development.'
  },
  {
    id: 'javascript',
    name: 'JavaScript',
    icon: '🟨',
    enabled: false,
    fileExtension: '.js',
    runtime: 'Node.js 20+ LTS',
    statusText: 'Coming Soon',
    badgeClass: 'status-soon',
    description: 'V8 stack parser and Jest isolated verification in development.'
  }
];

/**
 * Curated realistic Python bug cases for reliable demonstration & verification.
 * These cases reflect real developer bugs with realistic tracebacks and controlled tests.
 */
export const SAMPLE_CASES = [
  {
    id: 'sample-zerodivision',
    title: 'ZeroDivisionError in calculate_average_score',
    errorType: 'ZeroDivisionError',
    language: 'python',
    description: 'Unchecked empty list causes division by zero when calculating class averages.',
    sourceCode: `def calculate_average_score(scores):
    """
    Computes arithmetic mean of test scores.
    Returns 0.0 if scores list is empty.
    """
    total = sum(scores)
    count = len(scores)
    average = total / count
    return round(average, 2)

# Calling with empty dataset triggers crash:
results = calculate_average_score([])
print(f"Average: {results}")`,
    traceback: `Traceback (most recent call last):
  File "grade_analytics.py", line 12, in <module>
    results = calculate_average_score([])
  File "grade_analytics.py", line 8, in calculate_average_score
    average = total / count
ZeroDivisionError: division by zero`,
    expectedBehavior: 'Function should return 0.0 when given an empty list of scores without throwing an exception.',
    diagnosis: {
      errorType: 'ZeroDivisionError',
      summary: 'Division by zero encountered when len(scores) evaluates to 0',
      culpritLine: 8,
      culpritCode: 'average = total / count',
      fileName: 'grade_analytics.py',
      tracebackFacts: [
        'Exception ZeroDivisionError raised on line 8 of grade_analytics.py',
        'Denominator variable "count" was 0 because input list "scores" was empty []',
        'Numerator "total" was 0'
      ],
      hypothesis: 'The function assumes "scores" always contains at least one numeric element. When an empty collection is provided, len(scores) is 0, which directly causes the division operator to fail.',
      explanation: 'In Python, dividing any number by 0 raises an immediate ZeroDivisionError at runtime. To handle optional or empty datasets safely, guard checks must inspect whether the list has items before dividing.',
      recommendedAction: 'Add an early guard condition checking `if not scores:` to return a safe baseline value of `0.0`.'
    },
    proposedFix: {
      summary: 'Add guard clause checking for empty scores collection before division',
      explanation: 'Checking `if not scores:` handles empty lists, None values, or zero-length sequences upfront, returning 0.0 safely and avoiding division by zero.',
      affectedLines: 'Lines 5-7',
      originalSnippet: `    total = sum(scores)
    count = len(scores)
    average = total / count
    return round(average, 2)`,
      fixedSnippet: `    if not scores:
        return 0.0

    total = sum(scores)
    count = len(scores)
    average = total / count
    return round(average, 2)`,
      fullFixedCode: `def calculate_average_score(scores):
    """
    Computes arithmetic mean of test scores.
    Returns 0.0 if scores list is empty.
    """
    if not scores:
        return 0.0

    total = sum(scores)
    count = len(scores)
    average = total / count
    return round(average, 2)

# Calling with empty dataset now returns 0.0 safely:
results = calculate_average_score([])
print(f"Average: {results}")`
    },
    verification: {
      status: 'verified', // 'verified' | 'failed' | 'unverified'
      testsExecuted: 3,
      testsPassed: 3,
      testsFailed: 0,
      scope: 'Controlled pytest execution on edge cases (empty list, positive integers, single score)',
      testCases: [
        { name: 'test_calculate_average_empty_list', input: 'scores = []', expected: '0.0', actual: '0.0', status: 'passed' },
        { name: 'test_calculate_average_standard_scores', input: 'scores = [80, 90, 100]', expected: '90.0', actual: '90.0', status: 'passed' },
        { name: 'test_calculate_average_single_element', input: 'scores = [75]', expected: '75.0', actual: '75.0', status: 'passed' }
      ],
      stdout: `============================= test session starts ==============================
platform win32 -- Python 3.10.11, pytest-7.4.0
rootdir: /sandbox/test_workspace
collected 3 items

tests/test_grade_analytics.py::test_calculate_average_empty_list PASSED    [ 33%]
tests/test_grade_analytics.py::test_calculate_average_standard_scores PASSED [ 66%]
tests/test_grade_analytics.py::test_calculate_average_single_element PASSED [100%]

============================== 3 passed in 0.04s ===============================`,
      stderr: ''
    }
  },
  {
    id: 'sample-indexerror',
    title: 'IndexError in find_peaks off-by-one boundary',
    errorType: 'IndexError',
    language: 'python',
    description: 'Sliding window loop accesses readings[i+1] past the end of the array.',
    sourceCode: `def find_peaks(readings):
    """
    Detects index positions where reading is greater than immediate neighbors.
    """
    peaks = []
    # Loop boundary bug: accesses i+1 on the last element
    for i in range(1, len(readings)):
        if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
            peaks.append(i)
    return peaks

data = [10, 25, 18, 40, 30]
print("Detected peaks:", find_peaks(data))`,
    traceback: `Traceback (most recent call last):
  File "sensor_processor.py", line 12, in <module>
    print("Detected peaks:", find_peaks(data))
  File "sensor_processor.py", line 8, in find_peaks
    if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
IndexError: list index out of range`,
    expectedBehavior: 'Algorithm should compare interior elements without reading beyond the list bounds, returning [1, 3] for peaks.',
    diagnosis: {
      errorType: 'IndexError',
      summary: 'List index out of range at the final iteration of loop',
      culpritLine: 8,
      culpritCode: 'if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:',
      fileName: 'sensor_processor.py',
      tracebackFacts: [
        'Exception IndexError: list index out of range on line 8 of sensor_processor.py',
        'Loop ran up to len(readings) - 1, meaning when i is the last valid index, i + 1 is beyond list bounds',
        'Input length was 5 (indices 0 to 4); code tried to access index 5'
      ],
      hypothesis: 'The range stop parameter was set to `len(readings)`, which reaches `len(readings) - 1`. The inner expression `readings[i + 1]` attempts to access `len(readings)`, which does not exist in 0-indexed sequences.',
      explanation: 'A classic off-by-one error. When comparing element `i` against its right neighbor `i + 1`, the loop must terminate at `len(readings) - 1` so that `i + 1` never exceeds the maximum index.',
      recommendedAction: 'Adjust the loop range stop parameter to `range(1, len(readings) - 1)` and ensure edge cases for short arrays (< 3 elements) are guarded.'
    },
    proposedFix: {
      summary: 'Fix loop upper bound to stop at len(readings) - 1',
      explanation: 'Modifies the range upper bound so `i + 1` stays strictly within bounds for all iterations, avoiding IndexError.',
      affectedLines: 'Lines 6-8',
      originalSnippet: `    for i in range(1, len(readings)):
        if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
            peaks.append(i)`,
      fixedSnippet: `    if len(readings) < 3:
        return []

    for i in range(1, len(readings) - 1):
        if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
            peaks.append(i)`,
      fullFixedCode: `def find_peaks(readings):
    """
    Detects index positions where reading is greater than immediate neighbors.
    """
    if len(readings) < 3:
        return []

    peaks = []
    for i in range(1, len(readings) - 1):
        if readings[i] > readings[i - 1] and readings[i] > readings[i + 1]:
            peaks.append(i)
    return peaks

data = [10, 25, 18, 40, 30]
print("Detected peaks:", find_peaks(data))`
    },
    verification: {
      status: 'verified',
      testsExecuted: 3,
      testsPassed: 3,
      testsFailed: 0,
      scope: 'Boundary testing on 5-element array, 2-element array, and strictly ascending array',
      testCases: [
        { name: 'test_find_peaks_standard_array', input: 'readings = [10, 25, 18, 40, 30]', expected: '[1, 3]', actual: '[1, 3]', status: 'passed' },
        { name: 'test_find_peaks_short_array', input: 'readings = [10, 20]', expected: '[]', actual: '[]', status: 'passed' },
        { name: 'test_find_peaks_no_peaks', input: 'readings = [1, 2, 3, 4, 5]', expected: '[]', actual: '[]', status: 'passed' }
      ],
      stdout: `============================= test session starts ==============================
tests/test_sensor.py::test_find_peaks_standard_array PASSED           [ 33%]
tests/test_sensor.py::test_find_peaks_short_array PASSED              [ 66%]
tests/test_sensor.py::test_find_peaks_no_peaks PASSED                 [100%]

============================== 3 passed in 0.03s ===============================`,
      stderr: ''
    }
  },
  {
    id: 'sample-typeerror',
    title: 'TypeError: NoneType concatenation in build_user_badge',
    errorType: 'TypeError',
    language: 'python',
    description: 'String concatenation fails when optional title dictionary key contains None.',
    sourceCode: `def build_user_badge(user_profile):
    """
    Constructs a formatted display badge like: "Dr. Jane Doe [ID: 42]"
    """
    title = user_profile.get("title")  # may be None
    first = user_profile["first_name"]
    last = user_profile["last_name"]
    uid = user_profile["id"]

    # Crashes if title is None
    badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"
    return badge

user = {"first_name": "Alan", "last_name": "Turing", "id": 101, "title": None}
print(build_user_badge(user))`,
    traceback: `Traceback (most recent call last):
  File "user_service.py", line 14, in <module>
    print(build_user_badge(user))
  File "user_service.py", line 11, in build_user_badge
    badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"
TypeError: can only concatenate str (not "NoneType") to str`,
    expectedBehavior: 'If title is None or omitted, the badge should gracefully format as "Alan Turing [ID: 101]".',
    diagnosis: {
      errorType: 'TypeError',
      summary: 'Attempted to concatenate NoneType with string literal',
      culpritLine: 11,
      culpritCode: 'badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"',
      fileName: 'user_service.py',
      tracebackFacts: [
        'Exception TypeError: can only concatenate str (not "NoneType") to str on line 11',
        'Variable "title" evaluated to None because user profile had "title": None',
        'String concatenation operator (+) does not accept NoneType operands'
      ],
      hypothesis: 'The code assumes "title" is always a string. When dictionary key "title" is either None or omitted, `user_profile.get("title")` yields None, causing the `+` operator to raise TypeError.',
      explanation: 'In Python, string concatenation requires both operands to be string types. Optional attributes that may be None need explicit fallback handling or conditional formatting.',
      recommendedAction: 'Format the title conditionally or provide an empty string fallback with `user_profile.get("title") or ""`.'
    },
    proposedFix: {
      summary: 'Use string formatting with clean fallback for optional title',
      explanation: 'Replaces string addition with formatted f-string and strips leading whitespace if title is None or empty.',
      affectedLines: 'Lines 6-12',
      originalSnippet: `    title = user_profile.get("title")  # may be None
    first = user_profile["first_name"]
    last = user_profile["last_name"]
    uid = user_profile["id"]

    badge = title + " " + first + " " + last + " [ID: " + str(uid) + "]"`,
      fixedSnippet: `    title = user_profile.get("title")
    first = user_profile["first_name"]
    last = user_profile["last_name"]
    uid = user_profile["id"]

    name_prefix = f"{title} " if title else ""
    badge = f"{name_prefix}{first} {last} [ID: {uid}]"`,
      fullFixedCode: `def build_user_badge(user_profile):
    """
    Constructs a formatted display badge like: "Dr. Jane Doe [ID: 42]"
    """
    title = user_profile.get("title")
    first = user_profile["first_name"]
    last = user_profile["last_name"]
    uid = user_profile["id"]

    name_prefix = f"{title} " if title else ""
    badge = f"{name_prefix}{first} {last} [ID: {uid}]"
    return badge

user = {"first_name": "Alan", "last_name": "Turing", "id": 101, "title": None}
print(build_user_badge(user))`
    },
    verification: {
      status: 'verified',
      testsExecuted: 3,
      testsPassed: 3,
      testsFailed: 0,
      scope: 'Testing user profile with title=None, user profile with title="Dr.", and profile with title missing',
      testCases: [
        { name: 'test_badge_with_none_title', input: '{"first_name": "Alan", "last_name": "Turing", "id": 101, "title": None}', expected: 'Alan Turing [ID: 101]', actual: 'Alan Turing [ID: 101]', status: 'passed' },
        { name: 'test_badge_with_valid_title', input: '{"first_name": "Ada", "last_name": "Lovelace", "id": 102, "title": "Hon."}', expected: 'Hon. Ada Lovelace [ID: 102]', actual: 'Hon. Ada Lovelace [ID: 102]', status: 'passed' },
        { name: 'test_badge_with_missing_key', input: '{"first_name": "Grace", "last_name": "Hopper", "id": 103}', expected: 'Grace Hopper [ID: 103]', actual: 'Grace Hopper [ID: 103]', status: 'passed' }
      ],
      stdout: `============================= test session starts ==============================
tests/test_user_badge.py::test_badge_with_none_title PASSED             [ 33%]
tests/test_badge.py::test_badge_with_valid_title PASSED                 [ 66%]
tests/test_badge.py::test_badge_with_missing_key PASSED                 [100%]

============================== 3 passed in 0.03s ===============================`,
      stderr: ''
    }
  }
];
