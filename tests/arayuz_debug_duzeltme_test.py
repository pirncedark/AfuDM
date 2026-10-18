import subprocess
import sys
import os

if __name__ == "__main__":
    mjs_path = os.path.join(os.path.dirname(__file__), "arayuz_debug_duzeltme_test.mjs")
    res = subprocess.run(["node", mjs_path], text=True, capture_output=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    sys.exit(res.returncode)
