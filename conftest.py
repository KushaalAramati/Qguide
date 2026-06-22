"""Ensure the repository root is importable as the `qguide` package during tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
