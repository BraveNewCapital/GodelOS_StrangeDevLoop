"""Compatibility shim: re-exports from the top-level metacognition_modules.cognitive_models."""

# The real module lives at the repository root, not inside backend/.
# This shim exists so that test code using
#   sys.path.insert(0, '../../backend/metacognition_modules')
#   import cognitive_models
# can find the module.

from metacognition_modules.cognitive_models import *  # noqa: F401,F403
