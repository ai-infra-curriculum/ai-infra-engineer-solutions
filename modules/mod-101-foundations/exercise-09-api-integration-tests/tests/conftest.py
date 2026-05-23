"""Top-level fixtures shared by all test tiers."""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "..", "exercise-08-production-model-serving", "src",
))
