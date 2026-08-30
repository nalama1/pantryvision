"""pytest path setup for the delete-product Lambda tests.

The handler under test does `from common.responses import ...`, so both the
package directory (for `from handler import ...`) and the backend root (for the
shared `common` package) must be importable regardless of the working directory
pytest is invoked from.
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))  # backend/delete-product/tests
_pkg = os.path.dirname(_here)                        # backend/delete-product
_backend = os.path.dirname(_pkg)                     # backend

# Insert the backend root first, then the package dir, so `handler` resolves
# from the package dir and `common.responses` resolves from the backend root.
sys.path.insert(0, _backend)
sys.path.insert(0, _pkg)
