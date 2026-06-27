"""S16-T001: Graphic template schema validation.

Provides simple validation for graphic template JSON structures without
requiring external JSON Schema libraries. Validates all 8 template types:
comparison_card, framework_3_step, decision_tree, cost_stack, before_after,
timeline, annotated_ui_mock, quote_card.
"""

from typing import Any, Dict, List, Tuple


class ValidationError(Exception):
    """Graphic template validation error."""

    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


def validate_graphic_template(template: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a graphic template against the schema.

    Returns:
        (is_valid, errors) tuple where errors is a list of error messages.
    """
    errors = []

    # Validate top-level required fields
    if "schema_version" not in template:
        errors.append("Missing required field: schema_version")
    elif template["schema_version"] != "1.0":
        errors.append(f"Invalid schema_version: {template.get('schema_version')}, expected '1.0'")

    if "template_type" not in template:
        errors.append("Missing required field: template_type")
    else:
        valid_types = {
            "comparison_card",
            "framework_3_step",
            "decision_tree",
            "cost_stack",
            "before_after",
            "timeline",
            "annotated_ui_mock",
            "quote_card"
        }
        if template["template_type"] not in valid_types:
            errors.append(f"Invalid template_type: {template['template_type']}")

    if "content" not in template:
        errors.append("Missing required field: content")
    elif not isinstance(template["content"], dict):
        errors.append("Field 'content' must be an object")
    else:
        # Validate template-specific content
        template_type = template.get("template_type")
        if template_type:
            content_errors = _validate_content(template_type, template["content"])
            errors.extend(content_errors)

    # Validate optional fields
    if "style" in template:
        style_errors = _validate_style(template["style"])
        errors.extend(style_errors)

    if "metadata" in template:
        metadata_errors = _validate_metadata(template["metadata"])
        errors.extend(metadata_errors)

    return (len(errors) == 0, errors)


def _validate_content(template_type: str, content: Dict[str, Any]) -> List[str]:
    """Validate template-specific content."""
    validators = {
        "comparison_card": _validate_comparison_card,
        "framework_3_step": _validate_framework_3_step,
        "decision_tree": _validate_decision_tree,
        "cost_stack": _validate_cost_stack,
        "before_after": _validate_before_after,
        "timeline": _validate_timeline,
        "annotated_ui_mock": _validate_annotated_ui_mock,
        "quote_card": _validate_quote_card
    }

    validator = validators.get(template_type)
    if validator:
        return validator(content)
    return []


def _validate_style(style: Dict[str, Any]) -> List[str]:
    """Validate optional style object."""
    errors = []

    if not isinstance(style, dict):
        return ["Field 'style' must be an object"]

    # Validate color format if present
    for color_field in ["primary_color", "secondary_color", "background_color", "text_color"]:
        if color_field in style:
            color = style[color_field]
            if not isinstance(color, str) or not _is_valid_color(color):
                errors.append(f"Invalid {color_field}: {color}, expected hex color format (#RRGGBB)")

    return errors


def _validate_metadata(metadata: Dict[str, Any]) -> List[str]:
    """Validate optional metadata object."""
    errors = []

    if not isinstance(metadata, dict):
        return ["Field 'metadata' must be an object"]

    # Validate duration_hint_sec range
    if "duration_hint_sec" in metadata:
        duration = metadata["duration_hint_sec"]
        if not isinstance(duration, (int, float)) or duration < 0 or duration > 30:
            errors.append("Invalid duration_hint_sec: must be between 0 and 30")

    return errors


def _validate_comparison_card(content: Dict[str, Any]) -> List[str]:
    """Validate comparison_card content."""
    errors = []

    # Check required fields
    if "left_column" not in content:
        errors.append("Missing required field: content.left_column")
    else:
        errors.extend(_validate_column(content["left_column"], "left_column"))

    if "right_column" not in content:
        errors.append("Missing required field: content.right_column")
    else:
        errors.extend(_validate_column(content["right_column"], "right_column"))

    # Validate optional comparison_label
    if "comparison_label" in content:
        label = content["comparison_label"]
        if not isinstance(label, str) or len(label) > 30:
            errors.append("Invalid comparison_label: must be string <= 30 chars")

    return errors


def _validate_column(column: Dict[str, Any], path: str) -> List[str]:
    """Validate a column (left or right) in comparison_card."""
    errors = []

    if not isinstance(column, dict):
        return [f"Field '{path}' must be an object"]

    # Check required fields
    if "title" not in column:
        errors.append(f"Missing required field: {path}.title")
    elif not isinstance(column["title"], str) or len(column["title"]) > 60:
        errors.append(f"Invalid {path}.title: must be string <= 60 chars")

    if "items" not in column:
        errors.append(f"Missing required field: {path}.items")
    elif not isinstance(column["items"], list):
        errors.append(f"Invalid {path}.items: must be an array")
    else:
        items = column["items"]
        if len(items) < 1:
            errors.append(f"Invalid {path}.items: must have at least 1 item")
        elif len(items) > 8:
            errors.append(f"Invalid {path}.items: must have at most 8 items")
        else:
            for i, item in enumerate(items):
                if not isinstance(item, str) or len(item) > 120:
                    errors.append(f"Invalid {path}.items[{i}]: must be string <= 120 chars")

    # Validate optional highlight_index
    if "highlight_index" in column:
        idx = column["highlight_index"]
        if not isinstance(idx, int) or idx < 0 or idx >= len(column.get("items", [])):
            errors.append(f"Invalid {path}.highlight_index: must be valid item index")

    return errors


def _validate_framework_3_step(content: Dict[str, Any]) -> List[str]:
    """Validate framework_3_step content."""
    errors = []

    # Check required fields
    if "title" not in content:
        errors.append("Missing required field: content.title")
    elif not isinstance(content["title"], str) or len(content["title"]) > 80:
        errors.append("Invalid title: must be string <= 80 chars")

    if "steps" not in content:
        errors.append("Missing required field: content.steps")
    elif not isinstance(content["steps"], list):
        errors.append("Invalid steps: must be an array")
    else:
        steps = content["steps"]
        if len(steps) != 3:
            errors.append("Invalid steps: must have exactly 3 items")
        else:
            valid_icons = {"circle", "arrow", "check", "star", "none"}
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(f"Invalid steps[{i}]: must be an object")
                    continue

                if "number" not in step:
                    errors.append(f"Missing required field: steps[{i}].number")
                elif not isinstance(step["number"], int) or step["number"] < 1 or step["number"] > 3:
                    errors.append(f"Invalid steps[{i}].number: must be integer 1-3")

                if "label" not in step:
                    errors.append(f"Missing required field: steps[{i}].label")
                elif not isinstance(step["label"], str) or len(step["label"]) > 50:
                    errors.append(f"Invalid steps[{i}].label: must be string <= 50 chars")

                if "description" not in step:
                    errors.append(f"Missing required field: steps[{i}].description")
                elif not isinstance(step["description"], str) or len(step["description"]) > 200:
                    errors.append(f"Invalid steps[{i}].description: must be string <= 200 chars")

                if "icon" in step and step["icon"] not in valid_icons:
                    errors.append(f"Invalid steps[{i}].icon: must be one of {valid_icons}")

    # Validate optional connector_style
    if "connector_style" in content:
        style = content["connector_style"]
        if style not in {"arrow", "line", "none"}:
            errors.append("Invalid connector_style: must be one of 'arrow', 'line', 'none'")

    return errors


def _validate_decision_tree(content: Dict[str, Any]) -> List[str]:
    """Validate decision_tree content."""
    errors = []

    # Check required fields
    if "root" not in content:
        errors.append("Missing required field: content.root")
    elif not isinstance(content["root"], dict):
        errors.append("Invalid root: must be an object")
    else:
        if "question" not in content["root"]:
            errors.append("Missing required field: content.root.question")
        elif not isinstance(content["root"]["question"], str) or len(content["root"]["question"]) > 100:
            errors.append("Invalid root.question: must be string <= 100 chars")

    if "branches" not in content:
        errors.append("Missing required field: content.branches")
    elif not isinstance(content["branches"], list):
        errors.append("Invalid branches: must be an array")
    else:
        branches = content["branches"]
        if len(branches) < 2 or len(branches) > 4:
            errors.append("Invalid branches: must have 2-4 items")
        else:
            for i, branch in enumerate(branches):
                if not isinstance(branch, dict):
                    errors.append(f"Invalid branches[{i}]: must be an object")
                    continue

                if "condition" not in branch:
                    errors.append(f"Missing required field: branches[{i}].condition")
                elif not isinstance(branch["condition"], str) or len(branch["condition"]) > 60:
                    errors.append(f"Invalid branches[{i}].condition: must be string <= 60 chars")

                if "outcome" not in branch:
                    errors.append(f"Missing required field: branches[{i}].outcome")
                elif not isinstance(branch["outcome"], str) or len(branch["outcome"]) > 150:
                    errors.append(f"Invalid branches[{i}].outcome: must be string <= 150 chars")

                if "is_recommended" in branch and not isinstance(branch["is_recommended"], bool):
                    errors.append(f"Invalid branches[{i}].is_recommended: must be boolean")

    return errors


def _validate_cost_stack(content: Dict[str, Any]) -> List[str]:
    """Validate cost_stack content."""
    errors = []

    # Check required fields
    if "title" not in content:
        errors.append("Missing required field: content.title")
    elif not isinstance(content["title"], str) or len(content["title"]) > 60:
        errors.append("Invalid title: must be string <= 60 chars")

    if "segments" not in content:
        errors.append("Missing required field: content.segments")
    elif not isinstance(content["segments"], list):
        errors.append("Invalid segments: must be an array")
    else:
        segments = content["segments"]
        if len(segments) < 2 or len(segments) > 6:
            errors.append("Invalid segments: must have 2-6 items")
        else:
            for i, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    errors.append(f"Invalid segments[{i}]: must be an object")
                    continue

                if "label" not in segment:
                    errors.append(f"Missing required field: segments[{i}].label")
                elif not isinstance(segment["label"], str) or len(segment["label"]) > 50:
                    errors.append(f"Invalid segments[{i}].label: must be string <= 50 chars")

                if "value" not in segment:
                    errors.append(f"Missing required field: segments[{i}].value")
                elif not isinstance(segment["value"], (str, int, float)):
                    errors.append(f"Invalid segments[{i}].value: must be string or number")

                if "color" in segment and not _is_valid_color(segment["color"]):
                    errors.append(f"Invalid segments[{i}].color: must be hex color (#RRGGBB)")

    # Validate optional total_label and total_value
    if "total_label" in content:
        label = content["total_label"]
        if not isinstance(label, str) or len(label) > 30:
            errors.append("Invalid total_label: must be string <= 30 chars")

    if "total_value" in content:
        value = content["total_value"]
        if not isinstance(value, str) or len(value) > 20:
            errors.append("Invalid total_value: must be string <= 20 chars")

    return errors


def _validate_before_after(content: Dict[str, Any]) -> List[str]:
    """Validate before_after content."""
    errors = []

    # Check required fields
    if "before" not in content:
        errors.append("Missing required field: content.before")
    else:
        errors.extend(_validate_section(content["before"], "before"))

    if "after" not in content:
        errors.append("Missing required field: content.after")
    else:
        errors.extend(_validate_section(content["after"], "after"))

    # Validate optional change_highlight
    if "change_highlight" in content:
        highlight = content["change_highlight"]
        if not isinstance(highlight, str) or len(highlight) > 100:
            errors.append("Invalid change_highlight: must be string <= 100 chars")

    return errors


def _validate_section(section: Dict[str, Any], path: str) -> List[str]:
    """Validate a section (before or after) in before_after."""
    errors = []

    if not isinstance(section, dict):
        return [f"Field '{path}' must be an object"]

    if "label" not in section:
        errors.append(f"Missing required field: {path}.label")
    elif not isinstance(section["label"], str) or len(section["label"]) > 40:
        errors.append(f"Invalid {path}.label: must be string <= 40 chars")

    if "description" not in section:
        errors.append(f"Missing required field: {path}.description")
    elif not isinstance(section["description"], str) or len(section["description"]) > 200:
        errors.append(f"Invalid {path}.description: must be string <= 200 chars")

    return errors


def _validate_timeline(content: Dict[str, Any]) -> List[str]:
    """Validate timeline content."""
    errors = []

    # Check optional title
    if "title" in content:
        title = content["title"]
        if not isinstance(title, str) or len(title) > 60:
            errors.append("Invalid title: must be string <= 60 chars")

    # Check required events
    if "events" not in content:
        errors.append("Missing required field: content.events")
    elif not isinstance(content["events"], list):
        errors.append("Invalid events: must be an array")
    else:
        events = content["events"]
        if len(events) < 2 or len(events) > 6:
            errors.append("Invalid events: must have 2-6 items")
        else:
            for i, event in enumerate(events):
                if not isinstance(event, dict):
                    errors.append(f"Invalid events[{i}]: must be an object")
                    continue

                if "time_label" not in event:
                    errors.append(f"Missing required field: events[{i}].time_label")
                elif not isinstance(event["time_label"], str) or len(event["time_label"]) > 30:
                    errors.append(f"Invalid events[{i}].time_label: must be string <= 30 chars")

                if "label" not in event:
                    errors.append(f"Missing required field: events[{i}].label")
                elif not isinstance(event["label"], str) or len(event["label"]) > 80:
                    errors.append(f"Invalid events[{i}].label: must be string <= 80 chars")

                if "description" in event and not isinstance(event["description"], str):
                    errors.append(f"Invalid events[{i}].description: must be string")

    # Validate optional orientation
    if "orientation" in content:
        orientation = content["orientation"]
        if orientation not in {"horizontal", "vertical"}:
            errors.append("Invalid orientation: must be 'horizontal' or 'vertical'")

    return errors


def _validate_annotated_ui_mock(content: Dict[str, Any]) -> List[str]:
    """Validate annotated_ui_mock content."""
    errors = []

    # Check required fields
    if "ui_title" not in content:
        errors.append("Missing required field: content.ui_title")
    elif not isinstance(content["ui_title"], str) or len(content["ui_title"]) > 60:
        errors.append("Invalid ui_title: must be string <= 60 chars")

    # Check optional ui_description
    if "ui_description" in content:
        desc = content["ui_description"]
        if not isinstance(desc, str) or len(desc) > 200:
            errors.append("Invalid ui_description: must be string <= 200 chars")

    # Check required annotations
    if "annotations" not in content:
        errors.append("Missing required field: content.annotations")
    elif not isinstance(content["annotations"], list):
        errors.append("Invalid annotations: must be an array")
    else:
        annotations = content["annotations"]
        if len(annotations) < 1 or len(annotations) > 6:
            errors.append("Invalid annotations: must have 1-6 items")
        else:
            valid_positions = {"top", "bottom", "left", "right", "center"}
            for i, annotation in enumerate(annotations):
                if not isinstance(annotation, dict):
                    errors.append(f"Invalid annotations[{i}]: must be an object")
                    continue

                if "element_name" not in annotation:
                    errors.append(f"Missing required field: annotations[{i}].element_name")
                elif not isinstance(annotation["element_name"], str) or len(annotation["element_name"]) > 50:
                    errors.append(f"Invalid annotations[{i}].element_name: must be string <= 50 chars")

                if "callout_text" not in annotation:
                    errors.append(f"Missing required field: annotations[{i}].callout_text")
                elif not isinstance(annotation["callout_text"], str) or len(annotation["callout_text"]) > 120:
                    errors.append(f"Invalid annotations[{i}].callout_text: must be string <= 120 chars")

                if "position_hint" in annotation and annotation["position_hint"] not in valid_positions:
                    errors.append(f"Invalid annotations[{i}].position_hint: must be one of {valid_positions}")

    return errors


def _validate_quote_card(content: Dict[str, Any]) -> List[str]:
    """Validate quote_card content."""
    errors = []

    # Check required fields
    if "quote" not in content:
        errors.append("Missing required field: content.quote")
    elif not isinstance(content["quote"], str) or len(content["quote"]) > 300:
        errors.append("Invalid quote: must be string <= 300 chars")

    if "author" not in content:
        errors.append("Missing required field: content.author")
    elif not isinstance(content["author"], str) or len(content["author"]) > 60:
        errors.append("Invalid author: must be string <= 60 chars")

    # Check optional author_title
    if "author_title" in content:
        title = content["author_title"]
        if not isinstance(title, str) or len(title) > 80:
            errors.append("Invalid author_title: must be string <= 80 chars")

    # Check optional context
    if "context" in content:
        ctx = content["context"]
        if not isinstance(ctx, str) or len(ctx) > 100:
            errors.append("Invalid context: must be string <= 100 chars")

    return errors


def _is_valid_color(color: str) -> bool:
    """Check if string is a valid hex color (#RRGGBB)."""
    if not isinstance(color, str):
        return False
    if len(color) != 7 or color[0] != "#":
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False


# Public API
__all__ = ["validate_graphic_template", "ValidationError"]
