"""
Pitchside Test Runner — discovers and runs tests with pytest when available,
or fallback runner with automatic fixture resolution (db, bot).

Usage:
    python -m tests.run_all
    pytest tests/ -v
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    try:
        import pytest
        return pytest.main([str(HERE), "-v", "--durations=5"])
    except ImportError:
        # Fallback runner for zero-dependency environments with fixture support
        import importlib
        import inspect
        import traceback
        from src.database import Database
        from src.telegram_bot import PitchsideTelegramBot
        from src.champions_league import seed_champions_league_clubs

        modules = sorted(p.stem for p in HERE.glob("test_*.py"))
        passed = failed = 0
        failures = []

        shared_db = Database()
        seed_champions_league_clubs(shared_db)
        shared_bot = PitchsideTelegramBot(token="dummy", db=shared_db)

        for mod_name in modules:
            mod = importlib.import_module(f"tests.{mod_name}")
            tests = [n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
            for t in tests:
                fn = getattr(mod, t)
                sig = inspect.signature(fn)
                kwargs = {}
                for param in sig.parameters.values():
                    if param.name == "db":
                        kwargs["db"] = shared_db
                    elif param.name == "bot":
                        kwargs["bot"] = shared_bot
                name = f"{mod_name}.{t}"
                try:
                    fn(**kwargs)
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
