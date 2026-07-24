"""
Tests for smart content routing — imports and tests the ACTUAL helper function
from jarvis.py (_smart_route_type_text), not inline simulation.

Also tests _extra_open execution code and system prompt via source assertions.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Mock jarvis.py dependencies so we can import the helper ──────────────
from unittest.mock import MagicMock, patch

_mocked_modules = {
    'llm.resilience': MagicMock(),
    'llm.tools': MagicMock(TOOLS=[]),
    'llm.tool_tiering': MagicMock(),
    'llm.core_bridge': MagicMock(),
    'plugins': MagicMock(get_plugin_manager=MagicMock(return_value=MagicMock(get_all_plugin_tools=lambda: []))),
    'system.risk_classifier': MagicMock(),
    'system.audit_log': MagicMock(),
    'intelligence.tuner_cache': MagicMock(get_gene=1024),
    'intelligence.conditioned_reflexes': MagicMock(),
    'intelligence.screen_watcher': MagicMock(),
    'memory.skill_store': MagicMock(),
    'memory.shadow_learner': MagicMock(),
    'memory.memory_injector': MagicMock(),
}

# Load jarvis.py source once for source-level assertions
_JARVIS_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py')
with open(_JARVIS_PATH, 'r', encoding='utf-8') as _f:
    _JARVIS_SOURCE = _f.read()


@pytest.fixture
def smart_route():
    """Import and return the actual _smart_route_type_text function from jarvis.py."""
    with patch.dict('sys.modules', _mocked_modules) as cm:
        from backend.llm.jarvis import _smart_route_type_text
        yield _smart_route_type_text
    # patch.dict restores sys.modules automatically on exit


class TestSmartRouteHelper:
    """Test the ACTUAL _smart_route_type_text function imported from jarvis.py."""

    def test_long_html_converts_to_write_file(self, smart_route):
        """type_text with >500 chars of HTML → write_file + open_app."""
        html = "<!DOCTYPE html>\n<html>\n<body>\n" + "<p>paragraph</p>\n" * 100 + "</body>\n</html>"
        assert len(html) > 500

        name, args, extra = smart_route("type_text", {"text": html})

        assert name == "write_file"
        assert args["content"] == html
        assert args["path"].endswith(".html")
        assert "may_output" in args["path"]
        assert extra is not None
        assert extra["name"] == "open_app"
        assert extra["args"]["app_name"] == args["path"]

    def test_long_python_converts_to_py(self, smart_route):
        """type_text with >500 chars of Python → .py file."""
        py = "import os\nimport sys\n" + "print('hello')\n" * 100
        assert len(py) > 500

        name, args, extra = smart_route("type_text", {"text": py})

        assert name == "write_file"
        assert args["path"].endswith(".py")

    def test_long_markdown_converts_to_md(self, smart_route):
        """type_text with >500 chars of Markdown → .md file."""
        md = "# Title\n\n" + "Paragraph with content.\n\n" * 80
        assert len(md) > 500

        name, args, extra = smart_route("type_text", {"text": md})

        assert name == "write_file"
        assert args["path"].endswith(".md")

    def test_long_css_converts_to_css(self, smart_route):
        """type_text with >500 chars of CSS → .css file."""
        css = "body {\n  margin: 0;\n  padding: 0;\n  font-family: Arial, sans-serif;\n}\n\n.container {\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 20px;\n}\n\n" + ".item { color: red; }\n" * 50
        assert len(css) > 500

        name, args, extra = smart_route("type_text", {"text": css})

        assert name == "write_file"
        assert args["path"].endswith(".css")
        assert "may_output" in args["path"]
        assert extra is not None
        assert extra["name"] == "open_app"

    def test_long_json_converts_to_js(self, smart_route):
        """type_text with >500 chars of JSON starting with { → .js file."""
        js = '{"config": {' + '"key": "value", ' * 50 + '"end": true}}'
        assert len(js) > 500

        name, args, extra = smart_route("type_text", {"text": js})

        assert name == "write_file"
        assert args["path"].endswith(".js")

    def test_short_text_not_converted(self, smart_route):
        """Content ≤500 chars should NOT be converted."""
        name, args, extra = smart_route("type_text", {"text": "hello world"})

        assert name == "type_text"
        assert args["text"] == "hello world"
        assert extra is None

    def test_exactly_500_chars_not_converted(self, smart_route):
        """Exactly 500 chars should NOT trigger routing (threshold is >500)."""
        text = "x" * 500
        assert len(text) == 500

        name, args, extra = smart_route("type_text", {"text": text})

        assert name == "type_text"
        assert extra is None

    def test_501_chars_converts(self, smart_route):
        """501 chars should trigger routing."""
        text = "x" * 501
        assert len(text) == 501

        name, args, extra = smart_route("type_text", {"text": text})

        assert name == "write_file"
        assert extra is not None
        assert extra["name"] == "open_app"

    def test_empty_text_not_converted(self, smart_route):
        """Empty text should NOT be converted."""
        name, args, extra = smart_route("type_text", {"text": ""})

        assert name == "type_text"
        assert extra is None

    def test_non_type_text_not_affected(self, smart_route):
        """Non-type_text tools should pass through unchanged."""
        name, args, extra = smart_route("write_file", {"path": "/tmp/test.txt", "content": "hello"})

        assert name == "write_file"
        assert args["path"] == "/tmp/test.txt"
        assert extra is None

    def test_content_preserved_exactly(self, smart_route):
        """Full content must be preserved, not truncated or modified."""
        content = '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n</head>\n<body>\n'
        content += '<p>"quotes" &amp; &lt;special&gt; chars</p>\n'
        content += "</body>\n</html>\n"
        content += "<!-- " + "padding " * 100 + "-->"
        assert len(content) > 500

        name, args, extra = smart_route("type_text", {"text": content})

        assert args["content"] == content
        assert '&amp;' in args["content"]
        assert '"quotes"' in args["content"]


# ── Test: _extra_open execution code exists in jarvis.py ─────────────────

class TestJarvisSourceCode:
    """Verify the actual jarvis.py source contains expected code patterns."""

    def test_smart_route_helper_exists(self):
        """_smart_route_type_text function must exist."""
        assert "def _smart_route_type_text(" in _JARVIS_SOURCE

    def test_smart_route_called_in_loop(self):
        """The agentic loop must call _smart_route_type_text."""
        assert "_smart_route_type_text(tool_name, tool_args)" in _JARVIS_SOURCE

    def test_extra_open_execution_exists(self):
        """_extra_open execution code must exist."""
        assert "_extra_open is not None" in _JARVIS_SOURCE
        assert "_eo_name = _extra_open[\"name\"]" in _JARVIS_SOURCE
        assert "_eo_result = await execute_tool(_eo_name, _eo_args)" in _JARVIS_SOURCE

    def test_system_prompt_forbids_type_text_for_code(self):
        """System prompt must forbid typing code via type_text."""
        assert "NEVER try to type code/HTML via type_text" in _JARVIS_SOURCE
        assert "ALWAYS use write_file for long content" in _JARVIS_SOURCE

    def test_max_tokens_increased(self):
        """Follow-up rounds must use max_tokens=1024."""
        assert "max_tokens=1024" in _JARVIS_SOURCE
        assert "max_tokens=512" not in _JARVIS_SOURCE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
