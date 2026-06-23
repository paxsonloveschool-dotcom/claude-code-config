"""Caption stage: transcribe to word-level segments, then burn animated captions."""

from .burn import burn_captions
from .transcribe import Segment, Word, transcribe

__all__ = ["Segment", "Word", "transcribe", "burn_captions"]
