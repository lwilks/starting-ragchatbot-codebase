#!/bin/bash
# Code Quality Check Script
# Run all code quality checks for the project

set -e

echo "🔍 Running code quality checks..."
echo ""

echo "📝 Checking code formatting with Black..."
uv run black --check backend/ main.py
echo "✅ Black check passed"
echo ""

echo "📦 Checking import sorting with isort..."
uv run isort --check-only backend/ main.py
echo "✅ isort check passed"
echo ""

echo "🔬 Running flake8 linter..."
uv run flake8 backend/ main.py --max-line-length=88 --extend-ignore=E203,W503
echo "✅ flake8 check passed"
echo ""

echo "🎯 Running mypy type checker..."
uv run mypy backend/ main.py
echo "✅ mypy check passed"
echo ""

echo "✨ All quality checks passed! ✨"
