"""Stable, location-scoped Streamlit download widget identity.

An output fingerprint is deliberately NOT used for the widget key: identical
calculation evidence can appear multiple times in one render, particularly
within a Gemini tool trace. Occurrence is the one-based trace position.
"""

_LOCATIONS = frozenset({
    'manual_result',
    'clarified_result',
    'ai_trace_result',
    'manual_comparison',
    'clarified_comparison',
    'ai_comparison',
    'ai_response',
})


def evidence_key(location: str, occurrence: int = 0) -> str:
    """Make a key from a declared, unique rendering surface and its position."""
    if not isinstance(location, str) or location not in _LOCATIONS:
        raise ValueError('Unsupported evidence download location.')
    if type(occurrence) is not int or occurrence < 0:
        raise ValueError('Evidence download occurrence must be a nonnegative integer.')
    if location != 'ai_trace_result' and occurrence != 0:
        raise ValueError('Only AI trace downloads may have repeated occurrences.')
    if location == 'ai_trace_result' and occurrence < 1:
        raise ValueError('AI trace download occurrence must be one-based.')
    return f'finding_watch:evidence:{location}:{occurrence}'
