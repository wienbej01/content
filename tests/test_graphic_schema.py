"""S16-T001: Graphic template schema validation tests.

Tests verify:
1. Valid examples for all 8 template types pass validation.
2. Missing required fields fail validation.
3. Invalid data types fail validation.
4. String length constraints are enforced.
5. Enum constraints are enforced.
6. Array min/max constraints are enforced.
7. Schema version must be "1.0".
8. Invalid template_type fails.
9. OneOf content validation works correctly.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import graphic_template_schema as gts


def _make_base_template(template_type):
    """Helper: create minimal valid template base."""
    return {
        "schema_version": "1.0",
        "template_type": template_type,
        "content": {}
    }


class TestSchemaStructure:
    """Schema metadata and structure tests."""

    def test_schema_file_exists(self):
        """Schema file exists and is valid JSON."""
        import json
        schema_path = ROOT / "schemas" / "graphic_template.schema.json"
        assert schema_path.exists()
        with open(schema_path) as f:
            json.load(f)


class TestComparisonCard:
    """comparison_card template validation."""

    def test_valid_comparison_card_passes(self):
        """Valid comparison_card passes validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {
                "title": "Before",
                "items": ["Item 1", "Item 2", "Item 3"]
            },
            "right_column": {
                "title": "After",
                "items": ["Better 1", "Better 2", "Better 3"]
            },
            "comparison_label": "vs"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid comparison_card should pass: {errors}"
        assert len(errors) == 0

    def test_comparison_card_missing_left_column_fails(self):
        """Missing left_column fails validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "right_column": {
                "title": "After",
                "items": ["A", "B"]
            }
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("left_column" in e for e in errors)

    def test_comparison_card_empty_items_fails(self):
        """Empty items array fails validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "L", "items": []},
            "right_column": {"title": "R", "items": ["A"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("at least 1 item" in e for e in errors)

    def test_comparison_card_too_many_items_fails(self):
        """More than 8 items fails validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "L", "items": ["X"] * 9},
            "right_column": {"title": "R", "items": ["Y"] * 9}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("at most 8 items" in e for e in errors)

    def test_comparison_card_title_too_long_fails(self):
        """Title >60 chars fails validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "X" * 61, "items": ["A"]},
            "right_column": {"title": "R", "items": ["B"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("title" in e and "60" in e for e in errors)

    def test_comparison_card_item_too_long_fails(self):
        """Item >120 chars fails validation."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "L", "items": ["X" * 121]},
            "right_column": {"title": "R", "items": ["B"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("120" in e for e in errors)

    def test_comparison_card_with_highlight_passes(self):
        """Valid comparison_card with highlight_index passes."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "L", "items": ["A", "B", "C"], "highlight_index": 1},
            "right_column": {"title": "R", "items": ["X", "Y", "Z"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid comparison_card with highlight should pass: {errors}"


class TestFramework3Step:
    """framework_3_step template validation."""

    def test_valid_framework_3_step_passes(self):
        """Valid framework_3_step passes validation."""
        template = _make_base_template("framework_3_step")
        template["content"] = {
            "title": "Three-Step Framework",
            "steps": [
                {"number": 1, "label": "Step One", "description": "First step details", "icon": "circle"},
                {"number": 2, "label": "Step Two", "description": "Second step details", "icon": "arrow"},
                {"number": 3, "label": "Step Three", "description": "Third step details", "icon": "check"}
            ],
            "connector_style": "arrow"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid framework_3_step should pass: {errors}"

    def test_framework_3_step_missing_title_fails(self):
        """Missing title fails validation."""
        template = _make_base_template("framework_3_step")
        template["content"] = {
            "steps": [
                {"number": 1, "label": "S1", "description": "D1"},
                {"number": 2, "label": "S2", "description": "D2"},
                {"number": 3, "label": "S3", "description": "D3"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("title" in e for e in errors)

    def test_framework_3_step_not_exactly_3_steps_fails(self):
        """Steps array must have exactly 3 items."""
        template = _make_base_template("framework_3_step")
        template["content"] = {
            "title": "Framework",
            "steps": [
                {"number": 1, "label": "S1", "description": "D1"},
                {"number": 2, "label": "S2", "description": "D2"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("exactly 3 items" in e for e in errors)

    def test_framework_3_step_invalid_icon_fails(self):
        """Invalid icon enum value fails validation."""
        template = _make_base_template("framework_3_step")
        template["content"] = {
            "title": "Framework",
            "steps": [
                {"number": 1, "label": "S1", "description": "D1", "icon": "invalid_icon"},
                {"number": 2, "label": "S2", "description": "D2"},
                {"number": 3, "label": "S3", "description": "D3"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("icon" in e for e in errors)


class TestDecisionTree:
    """decision_tree template validation."""

    def test_valid_decision_tree_passes(self):
        """Valid decision_tree passes validation."""
        template = _make_base_template("decision_tree")
        template["content"] = {
            "root": {"question": "Which path to take?"},
            "branches": [
                {"condition": "Option A", "outcome": "Result A", "is_recommended": False},
                {"condition": "Option B", "outcome": "Result B (recommended)", "is_recommended": True}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid decision_tree should pass: {errors}"

    def test_decision_tree_missing_root_fails(self):
        """Missing root fails validation."""
        template = _make_base_template("decision_tree")
        template["content"] = {
            "branches": [
                {"condition": "A", "outcome": "Result A"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("root" in e for e in errors)

    def test_decision_tree_too_few_branches_fails(self):
        """Fewer than 2 branches fails validation."""
        template = _make_base_template("decision_tree")
        template["content"] = {
            "root": {"question": "Q?"},
            "branches": [
                {"condition": "A", "outcome": "Result A"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("2-4 items" in e for e in errors)

    def test_decision_tree_question_too_long_fails(self):
        """Question >100 chars fails validation."""
        template = _make_base_template("decision_tree")
        template["content"] = {
            "root": {"question": "X" * 101},
            "branches": [
                {"condition": "A", "outcome": "Result A"},
                {"condition": "B", "outcome": "Result B"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("question" in e and "100" in e for e in errors)


class TestCostStack:
    """cost_stack template validation."""

    def test_valid_cost_stack_passes(self):
        """Valid cost_stack passes validation."""
        template = _make_base_template("cost_stack")
        template["content"] = {
            "title": "Total Cost Breakdown",
            "subtitle": "Monthly expenses",
            "segments": [
                {"label": "Housing", "value": "1200", "color": "#1B2A4A"},
                {"label": "Food", "value": "400", "color": "#C8973E"},
                {"label": "Transport", "value": "200", "color": "#F5F0E8"}
            ],
            "total_label": "Total",
            "total_value": "$1,800"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid cost_stack should pass: {errors}"

    def test_cost_stack_missing_title_fails(self):
        """Missing title fails validation."""
        template = _make_base_template("cost_stack")
        template["content"] = {
            "segments": [
                {"label": "A", "value": "100"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("title" in e for e in errors)

    def test_cost_stack_invalid_color_fails(self):
        """Invalid color format fails validation."""
        template = _make_base_template("cost_stack")
        template["content"] = {
            "title": "Costs",
            "segments": [
                {"label": "A", "value": "100", "color": "invalid_color"},
                {"label": "B", "value": "200"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("color" in e for e in errors)

    def test_cost_stack_too_many_segments_fails(self):
        """More than 6 segments fails validation."""
        template = _make_base_template("cost_stack")
        template["content"] = {
            "title": "Costs",
            "segments": [
                {"label": f"S{i}", "value": i} for i in range(7)
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("2-6 items" in e for e in errors)


class TestBeforeAfter:
    """before_after template validation."""

    def test_valid_before_after_passes(self):
        """Valid before_after passes validation."""
        template = _make_base_template("before_after")
        template["content"] = {
            "before": {
                "label": "Before",
                "description": "Old way of doing things with more text here."
            },
            "after": {
                "label": "After",
                "description": "New improved way with better results."
            },
            "change_highlight": "50% improvement"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid before_after should pass: {errors}"

    def test_before_after_missing_after_fails(self):
        """Missing after section fails validation."""
        template = _make_base_template("before_after")
        template["content"] = {
            "before": {"label": "Before", "description": "Old way"}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("after" in e for e in errors)

    def test_before_after_description_too_long_fails(self):
        """Description >200 chars fails validation."""
        template = _make_base_template("before_after")
        template["content"] = {
            "before": {"label": "B", "description": "X" * 201},
            "after": {"label": "A", "description": "Y"}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("description" in e and "200" in e for e in errors)


class TestTimeline:
    """timeline template validation."""

    def test_valid_timeline_passes(self):
        """Valid timeline passes validation."""
        template = _make_base_template("timeline")
        template["content"] = {
            "title": "Project Timeline",
            "events": [
                {"time_label": "Week 1", "label": "Planning", "description": "Initial setup"},
                {"time_label": "Week 2", "label": "Execution", "description": "Main work"},
                {"time_label": "Week 3", "label": "Review", "description": "Final checks"}
            ],
            "orientation": "horizontal"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid timeline should pass: {errors}"

    def test_timeline_missing_events_fails(self):
        """Missing events fails validation."""
        template = _make_base_template("timeline")
        template["content"] = {
            "title": "Timeline"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("events" in e for e in errors)

    def test_timeline_invalid_orientation_fails(self):
        """Invalid orientation enum fails validation."""
        template = _make_base_template("timeline")
        template["content"] = {
            "events": [
                {"time_label": "T1", "label": "E1"}
            ],
            "orientation": "diagonal"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("orientation" in e for e in errors)


class TestAnnotatedUiMock:
    """annotated_ui_mock template validation."""

    def test_valid_annotated_ui_mock_passes(self):
        """Valid annotated_ui_mock passes validation."""
        template = _make_base_template("annotated_ui_mock")
        template["content"] = {
            "ui_title": "Dashboard Interface",
            "ui_description": "Main analytics dashboard showing key metrics.",
            "annotations": [
                {"element_name": "Chart", "callout_text": "Revenue over time", "position_hint": "center"},
                {"element_name": "Filter", "callout_text": "Date range selector", "position_hint": "top"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid annotated_ui_mock should pass: {errors}"

    def test_annotated_ui_mock_missing_annotations_fails(self):
        """Missing annotations fails validation."""
        template = _make_base_template("annotated_ui_mock")
        template["content"] = {
            "ui_title": "UI"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("annotations" in e for e in errors)

    def test_annotated_ui_mock_invalid_position_fails(self):
        """Invalid position_hint enum fails validation."""
        template = _make_base_template("annotated_ui_mock")
        template["content"] = {
            "ui_title": "UI",
            "annotations": [
                {"element_name": "E", "callout_text": "C", "position_hint": "outside"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("position_hint" in e for e in errors)


class TestQuoteCard:
    """quote_card template validation."""

    def test_valid_quote_card_passes(self):
        """Valid quote_card passes validation."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "The best way to predict the future is to create it.",
            "author": "Peter Drucker",
            "author_title": "Management Consultant",
            "context": "On innovation and leadership"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid quote_card should pass: {errors}"

    def test_quote_card_missing_quote_fails(self):
        """Missing quote fails validation."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "author": "Name"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("quote" in e for e in errors)

    def test_quote_card_too_long_fails(self):
        """Quote >300 chars fails validation."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "X" * 301,
            "author": "A"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("quote" in e and "300" in e for e in errors)

    def test_quote_card_author_too_long_fails(self):
        """Author >60 chars fails validation."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "A quote",
            "author": "X" * 61
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("author" in e and "60" in e for e in errors)


class TestCommonValidation:
    """Common validation rules across all templates."""

    def test_invalid_schema_version_fails(self):
        """schema_version must be exactly '1.0'."""
        template = _make_base_template("comparison_card")
        template["schema_version"] = "2.0"
        template["content"] = {
            "left_column": {"title": "L", "items": ["A"]},
            "right_column": {"title": "R", "items": ["B"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("schema_version" in e for e in errors)

    def test_missing_schema_version_fails(self):
        """schema_version is required."""
        template = {
            "template_type": "comparison_card",
            "content": {
                "left_column": {"title": "L", "items": ["A"]},
                "right_column": {"title": "R", "items": ["B"]}
            }
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("schema_version" in e for e in errors)

    def test_invalid_template_type_fails(self):
        """Invalid template_type fails validation."""
        template = _make_base_template("invalid_template_type")
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("template_type" in e for e in errors)

    def test_optional_style_passes(self):
        """Optional style object with valid color passes."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "A quote",
            "author": "Author"
        }
        template["style"] = {
            "primary_color": "#1B2A4A",
            "secondary_color": "#C8973E"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid style should pass: {errors}"

    def test_optional_metadata_passes(self):
        """Optional metadata object passes."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "A quote",
            "author": "Author"
        }
        template["metadata"] = {
            "title": "Episode 5 Quote",
            "beat_id": "beat_005",
            "duration_hint_sec": 4.0
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid metadata should pass: {errors}"

    def test_invalid_color_format_fails(self):
        """Invalid color format in style fails."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "A quote",
            "author": "Author"
        }
        template["style"] = {
            "primary_color": "not_a_color"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert not is_valid
        assert any("color" in e for e in errors)


class TestAllTemplateTypesHaveValidExamples:
    """Every template type has at least one valid example."""

    def test_comparison_card_has_valid_example(self):
        """comparison_card has a valid example."""
        template = _make_base_template("comparison_card")
        template["content"] = {
            "left_column": {"title": "Option A", "items": ["Pro 1", "Pro 2"]},
            "right_column": {"title": "Option B", "items": ["Pro 1", "Pro 2"]}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid comparison_card should pass: {errors}"

    def test_framework_3_step_has_valid_example(self):
        """framework_3_step has a valid example."""
        template = _make_base_template("framework_3_step")
        template["content"] = {
            "title": "Framework",
            "steps": [
                {"number": 1, "label": "S1", "description": "D1"},
                {"number": 2, "label": "S2", "description": "D2"},
                {"number": 3, "label": "S3", "description": "D3"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid framework_3_step should pass: {errors}"

    def test_decision_tree_has_valid_example(self):
        """decision_tree has a valid example."""
        template = _make_base_template("decision_tree")
        template["content"] = {
            "root": {"question": "Choose?"},
            "branches": [
                {"condition": "Yes", "outcome": "Go right"},
                {"condition": "No", "outcome": "Go left"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid decision_tree should pass: {errors}"

    def test_cost_stack_has_valid_example(self):
        """cost_stack has a valid example."""
        template = _make_base_template("cost_stack")
        template["content"] = {
            "title": "Budget",
            "segments": [
                {"label": "A", "value": "100"},
                {"label": "B", "value": "200"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid cost_stack should pass: {errors}"

    def test_before_after_has_valid_example(self):
        """before_after has a valid example."""
        template = _make_base_template("before_after")
        template["content"] = {
            "before": {"label": "Old", "description": "Previous state"},
            "after": {"label": "New", "description": "Improved state"}
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid before_after should pass: {errors}"

    def test_timeline_has_valid_example(self):
        """timeline has a valid example."""
        template = _make_base_template("timeline")
        template["content"] = {
            "events": [
                {"time_label": "Q1", "label": "Start"},
                {"time_label": "Q2", "label": "Middle"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid timeline should pass: {errors}"

    def test_annotated_ui_mock_has_valid_example(self):
        """annotated_ui_mock has a valid example."""
        template = _make_base_template("annotated_ui_mock")
        template["content"] = {
            "ui_title": "UI",
            "annotations": [
                {"element_name": "Button", "callout_text": "Click me"}
            ]
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid annotated_ui_mock should pass: {errors}"

    def test_quote_card_has_valid_example(self):
        """quote_card has a valid example."""
        template = _make_base_template("quote_card")
        template["content"] = {
            "quote": "Be the change.",
            "author": "Gandhi"
        }
        is_valid, errors = gts.validate_graphic_template(template)
        assert is_valid, f"Valid quote_card should pass: {errors}"
