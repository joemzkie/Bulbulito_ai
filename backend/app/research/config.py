# Model registry keys are centralized here so research stages can be changed
# without affecting the user's independent chat model selection.
RIZARTS_PROFILE = {
    "planner_model": "gemini-3.5-flash-lite",
    "extractor_model": "gemini-3.5-flash-lite",
    "synthesizer_model": "gemini-3.5-flash-lite",
    "auditor_model": "gemini-3.5-flash-lite",
}

DEPTH_CONFIG = {
    "quick": {"query_counts": (3, 3), "refinements": 0},
    "standard": {"query_counts": (3, 4), "refinements": 1},
    "deep": {"query_counts": (5, 5), "refinements": 1},
}
