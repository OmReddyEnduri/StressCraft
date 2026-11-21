"""
StressCraft
===========
Automated Competitive Programming differential fuzzing, testcase generator,
and counterexample minimizer engine.
"""

from stresscraft.differ import OutputComparator
from stresscraft.fuzzer import StressFuzzer, fuzz
from stresscraft.generators import RandomGenerator
from stresscraft.minimizer import DeltaDebugger
from stresscraft.models import (
    ComparisonResult,
    Counterexample,
    FuzzReport,
    Language,
    RunResult,
    RunStatus,
)
from stresscraft.runners import CompilationError, SourceRunner

__version__ = "1.0.0"

__all__ = [
    # Version
    "__version__",
    # Models
    "Language",
    "RunStatus",
    "RunResult",
    "ComparisonResult",
    "Counterexample",
    "FuzzReport",
    # Generators
    "RandomGenerator",
    # Runners
    "SourceRunner",
    "CompilationError",
    # Differ
    "OutputComparator",
    # Minimizer
    "DeltaDebugger",
    # Fuzzing Engine
    "StressFuzzer",
    "fuzz",
]
