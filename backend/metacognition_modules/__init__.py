"""Compatibility package: proxies to the top-level metacognition_modules.

The canonical code lives at the repository-root ``metacognition_modules/``
package.  Several backend modules and tests import from
``backend.metacognition_modules.*``; this package makes those imports
succeed by re-exporting every sub-module.
"""

import importlib
import sys
import os

# Ensure the repo root is on sys.path so that the real package is importable.
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# List of sub-modules to proxy.
_SUBMODULES = [
    "cognitive_models",
    "enhanced_metacognition_manager",
    "enhanced_self_monitoring",
    "knowledge_gap_detector",
    "autonomous_knowledge_acquisition",
    "stream_coordinator",
]

for _name in _SUBMODULES:
    _fq = f"backend.metacognition_modules.{_name}"
    if _fq not in sys.modules:
        try:
            _real = importlib.import_module(f"metacognition_modules.{_name}")
            sys.modules[_fq] = _real
        except ImportError:
            pass  # optional module not installed
