#!/usr/bin/env python3
import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "ada-dev",
    "--env-file",
    ".env.dev",
    "-f",
    "docker-compose.dev-full.yml",
]


def write_section(title: str) -> None:
    print("")
    print(f"=== {title} ===")


def run_step(title: str, cmd: list[str]) -> None:
    write_section(title)
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {title}")


def has_tests(path: Path) -> bool:
    if not path.exists():
        return False
    patterns = ("test*.py", "*_test.py", "*_tests.py")
    for pattern in patterns:
        if any(path.rglob(pattern)):
            return True
    return False


def resolve_sim_date(value: str) -> str:
    if value:
        return value
    target = date.today() - timedelta(days=1)
    if target.weekday() == 5:
        target -= timedelta(days=1)
    if target.weekday() == 6:
        target -= timedelta(days=2)
    return target.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ada test runner")
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "unit", "suites", "integration", "e2e"],
        default="quick",
    )
    parser.add_argument("--simulation-date", default="", help="YYYY-MM-DD")
    parser.add_argument("--skip-backtest", action="store_true")
    args = parser.parse_args()

    run_unit = args.mode in ("quick", "full", "unit")
    run_suites = args.mode in ("full", "suites")
    run_integration = args.mode in ("full", "integration")
    run_e2e = args.mode in ("full", "e2e")

    if run_unit:
        write_section("Unit Tests")

        if has_tests(ROOT / "services" / "shared" / "tests"):
            run_step("Shared Libs", COMPOSE + ["exec", "-T", "data-service", "pytest", "/libs/shared/tests"])
        else:
            print("Skipping shared libs (no tests found)")

        if has_tests(ROOT / "services" / "data-service" / "tests"):
            run_step("Data Service", COMPOSE + ["exec", "-T", "data-service", "pytest", "/app/tests"])
        else:
            print("Skipping data-service pytest (no tests found)")

        if has_tests(ROOT / "services" / "indicator-service" / "tests"):
            run_step("Indicator Service", COMPOSE + ["exec", "-T", "indicator-service", "pytest", "/app/tests"])

        if has_tests(ROOT / "services" / "scanner-service" / "tests"):
            run_step("Scanner Service", COMPOSE + ["exec", "-T", "scanner-service", "pytest", "/app/tests"])

        if has_tests(ROOT / "services" / "alert-service" / "tests"):
            run_step("Alert Service", COMPOSE + ["exec", "-T", "alert-service", "pytest", "/app/tests"])

        if not args.skip_backtest and has_tests(ROOT / "services" / "backtest-service" / "tests"):
            run_step("Backtest Service", COMPOSE + ["exec", "-T", "backtest-service", "pytest", "/app/tests"])
        elif args.skip_backtest:
            print("Skipping backtest tests (skip-backtest enabled)")

        if has_tests(ROOT / "services" / "scheduler-service" / "tests"):
            run_step("Scheduler Service", COMPOSE + ["exec", "-T", "scheduler-service", "pytest", "/app/tests"])

    if run_suites:
        write_section("Service Test Suites")
        run_step("Data Service Suite", COMPOSE + ["exec", "-T", "data-service", "python", "scripts/test_suite.py"])
        run_step("Indicator Service Suite", COMPOSE + ["exec", "-T", "indicator-service", "python", "scripts/test_suite.py"])
        if not args.skip_backtest:
            run_step("Backtest Service Suite", COMPOSE + ["exec", "-T", "backtest-service", "python", "scripts/test_suite.py"])

    if run_integration:
        write_section("Integration Tests")
        run_step(
            "Integration Suite",
            COMPOSE + ["exec", "-T", "backtest-service", "pytest", "/ada/tests/integration_test_suite.py", "-v"],
        )

    if run_e2e:
        write_section("End-to-End Simulation")
        sim_date = resolve_sim_date(args.simulation_date)
        run_step(
            f"Simulated Daily Flow (target_date={sim_date})",
            COMPOSE
            + [
                "exec",
                "-T",
                "backtest-service",
                "/bin/sh",
                "-c",
                f"RUN_SIMULATION=1 SIMULATION_DATE={sim_date} python /ada/tests/integration_test_suite.py",
            ],
        )

    write_section("Done")
    print(f"Mode: {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
