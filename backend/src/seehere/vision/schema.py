"""The JSON contract for visual units returned by a vision model, and the instructions for it.

The schema is strict (every field required, no extra fields) so it can be passed as a
`json_schema` response format, and every reply is validated against it again on our side.
"""

from __future__ import annotations

from typing import Any

from seehere.db.enums import VisualKind

KINDS = [k.value for k in VisualKind]

_BOX = {
    "type": "object",
    "additionalProperties": False,
    "required": ["x", "y", "w", "h"],
    "properties": {
        "x": {"type": "number", "minimum": 0, "maximum": 1},
        "y": {"type": "number", "minimum": 0, "maximum": 1},
        "w": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "h": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
    },
}

UNITS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["units"],
    "properties": {
        "units": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "label", "details", "visible_text", "box"],
                "properties": {
                    "kind": {"type": "string", "enum": KINDS},
                    "label": {"type": "string", "minLength": 1, "maxLength": 200},
                    # What a sighted viewer can see: axes, trend, parts, relations. No guesses.
                    "details": {"type": "string", "maxLength": 1000},
                    # Text and numbers exactly as they appear inside this unit.
                    "visible_text": {
                        "type": "array",
                        "maxItems": 50,
                        "items": {"type": "string", "maxLength": 300},
                    },
                    "box": _BOX,
                },
            },
        }
    },
}

PROMPT = (
    """You are describing one frame of a recorded lecture for blind and low-vision students.
List the meaningful visual units on screen: charts, diagrams, tables, equations, text blocks and
images. For each unit give:
- kind: one of """
    + ", ".join(KINDS)
    + """
- label: a short name, e.g. "Bar chart of quarterly revenue"
- details: only what is visible (axes, labels, trends, parts and how they connect). Do not guess
  values that are not shown and do not add outside knowledge.
- visible_text: text and numbers exactly as they appear inside the unit
- box: its position as fractions of the frame (x, y from the top-left; w, h)
Ignore the presenter, the video player interface and decorative elements.
Reply with JSON only."""
)
