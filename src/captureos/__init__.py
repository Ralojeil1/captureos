"""CaptureOS — Three-basket universal capture router.

Classifies natural-language input into exactly three baskets:
  1. Task / Reminder
  2. Event / Meeting
  3. Idea / Note

Works as a Hermes Agent skill pack AND a standalone CLI tool.
"""

__version__ = "0.3.0"
__all__ = [
    "classify",
    "classify_multi",
    "router",
    "state",
    "writer",
    "conflict",
    "__version__",
]

from captureos.classifier import classify, classify_multi
