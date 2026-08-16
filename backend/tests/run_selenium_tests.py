#!/usr/bin/env python3
"""
Quick runner script for Selenium UI tests.
Usage: python run_selenium_tests.py [options]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent


def main():
    parser = argparse.ArgumentParser(description="Run Selenium UI tests")
    parser.add_argument("--browser", choices=["chrome", "firefox"], default="chrome",
                        help="Browser to use (default: chrome)")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run in headless mode (default: True)")
    parser.add_argument("--no-headless", dest="headless", action="store_false",
                        help="Run in headed mode")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173",
                        help="Frontend base URL (default: http://127.0.0.1:5173)")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000",
                        help="Backend API URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--test-file", help="Specific test file to run")
    parser.add_argument("--test-pattern", default="test_selenium_*.py",
                        help="Test file pattern (default: test_selenium_*.py)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--markers", help="Pytest markers to filter (e.g., 'not slow')")
    parser.add_argument("--install-deps", action="store_true",
                        help="Install dependencies before running")

    args = parser.parse_args()

    # Set environment variables
    os.environ["SELENIUM_BROWSER"] = args.browser
    os.environ["SELENIUM_HEADLESS"] = str(args.headless).lower()
    os.environ["SELENIUM_BASE_URL"] = args.base_url
    os.environ["SELENIUM_API_URL"] = args.api_url

    # Install dependencies if requested
    if args.install_deps:
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                       cwd=BACKEND_DIR, check=True)
        print("Installing frontend dependencies...")
        subprocess.run(["pnpm", "install"], cwd=PROJECT_ROOT / "frontend", check=True)
        print("Building frontend...")
        subprocess.run(["pnpm", "run", "build"], cwd=PROJECT_ROOT / "frontend", check=True)

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    if args.test_file:
        cmd.append(str(BACKEND_DIR / "tests" / args.test_file))
    else:
        cmd.append(str(BACKEND_DIR / "tests" / args.test_pattern))

    cmd.extend(["--selenium"])

    if args.verbose:
        cmd.append("-v")

    if args.markers:
        cmd.extend(["-m", args.markers])

    print(f"Running: {' '.join(cmd)}")
    print(f"Browser: {args.browser}, Headless: {args.headless}")
    print(f"Frontend: {args.base_url}, Backend: {args.api_url}")
    print("-" * 60)

    # Run tests
    result = subprocess.run(cmd, cwd=BACKEND_DIR)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())