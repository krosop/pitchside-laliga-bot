"""
Tiny test runner — discovers test_*.py modules next to this file and runs
every top-level function starting with `test_`. No dependencies.

Usage:
    python -m tests.run_all

Exit code 0 = all passed, 1 = failures (CI-friendly).
"""
import importlib
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    modules = sorted(p.stem for p in HERE.glob("test_*.py"))
    passed = failed = 0
    failures = []

    for mod_name in modules:
        mod = importlib.import_module(f"tests.{mod_name}")
        tests = [n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
        for t in tests:
            name = f"{mod_name}.{t}"
            try:
                getattr(mod, t)()
                print(f"  PASS {name}")
                passed += 1
            except Exception:
                tb = traceback.format_exc(limit=3)
                failures.append((name, tb))
                print(f"  FAIL {name}")
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    for name, tb in failures:
        print(f"\n--- {name} ---\n{tb}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
