import subprocess
import sys

res = subprocess.run(
    [sys.executable, '-c', 'print("hello world")'],
    capture_output=True,
    text=True,
    env={'PYTHONPATH': '.', 'PYTHONDONTWRITEBYTECODE': '1'}
)
print("RETURNCODE:", res.returncode)
print("STDOUT:", repr(res.stdout))
print("STDERR:", repr(res.stderr))
