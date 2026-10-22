from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


start = time.time()
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_core.py", top_level_dir=str(ROOT))
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {
    "runner": "python-stdlib-unittest", "tests_run": result.testsRun, "passed": result.testsRun - len(result.failures) - len(result.errors),
    "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "duration_seconds": round(time.time() - start, 3),
}
print("CORE_TEST_SUMMARY=" + json.dumps(summary, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)

