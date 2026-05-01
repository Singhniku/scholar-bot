"""
pytest configuration for the skills/ test suite.
Adds the project root to sys.path so 'from src.xxx import' works.
"""
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))
