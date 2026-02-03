#!/usr/bin/env python3
"""
Notta Test Runner

Runs all tests with coverage reporting.
Usage:
    python run_tests.py          # Run all tests with coverage
    python run_tests.py -v       # Verbose output
    python run_tests.py -k test_name  # Run specific test
    python run_tests.py --no-cov # Skip coverage
"""

import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description='Run Notta tests with coverage')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-k', '--keyword', help='Run tests matching keyword')
    parser.add_argument('--no-cov', action='store_true', help='Skip coverage reporting')
    parser.add_argument('--html', action='store_true', help='Generate HTML coverage report')
    parser.add_argument('-x', '--exitfirst', action='store_true', help='Exit on first failure')
    parser.add_argument('--module', help='Test specific module (e.g., test_metrics)')
    args = parser.parse_args()

    # Build pytest command
    cmd = [sys.executable, '-m', 'pytest']

    # Test path
    if args.module:
        cmd.append(f'tests/{args.module}.py')
    else:
        cmd.append('tests/')

    # Options
    if args.verbose:
        cmd.append('-v')

    if args.keyword:
        cmd.extend(['-k', args.keyword])

    if args.exitfirst:
        cmd.append('-x')

    # Coverage options
    if not args.no_cov:
        cmd.extend([
            '--cov=health',
            '--cov-report=term-missing',
            '--cov-fail-under=90'  # Fail if coverage below 90%
        ])

        if args.html:
            cmd.extend(['--cov-report=html:coverage_html'])

    # Add markers
    cmd.append('--tb=short')

    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
