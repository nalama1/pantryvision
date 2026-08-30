"""Ensures the shared `common` package is importable during tests.

This conftest inserts the `backend/` directory on sys.path so that
`from common.responses import ...` resolves when running pytest from
any working directory. The file lives at backend/common/tests/conftest.py,
so three dirname() calls up from this file resolves to backend/.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
