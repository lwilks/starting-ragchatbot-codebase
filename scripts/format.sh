#!/bin/bash
# Code Formatting Script
# Auto-format all code in the project

set -e

echo "🎨 Formatting code..."
echo ""

echo "📝 Running Black formatter..."
uv run black backend/ main.py
echo "✅ Black formatting complete"
echo ""

echo "📦 Sorting imports with isort..."
uv run isort backend/ main.py
echo "✅ isort complete"
echo ""

echo "✨ Code formatting complete! ✨"
