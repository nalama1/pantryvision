"""Ensures the check-expiring-products package directory is importable
when running pytest from any working directory."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
