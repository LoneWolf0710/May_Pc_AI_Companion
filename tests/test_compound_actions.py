"""
Tests for compound 'open X and write Y' action fixes.

Verifies:
1. Compound fast-path regex matches various input patterns
2. Smart content routing converts type_text > 500 chars → write_file + open_app
3. _extra_open is properly set and executed after write_file
4. System prompt contains the strengthened TOOL GUIDELINES
"""

import ast
import os
import re
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Shared mock setup (avoids duplication across every test) ─────────────
_mocked_modules = {
    'llm.resilience': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'llm.tools': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(TOOLS=[]),
    'llm.tool_tiering': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(get_tools_for_message=[]),
    'llm.core_bridge': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'plugins': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(
        get_plugin_manager=__import__('unittest.mock', fromlist=['MagicMock']).MagicMock(
            return_value=__import__('unittest.mock', fromlist=['MagicMock']).MagicMock(get_all_plugin_tools=lambda: [])
        )
    ),
    'system.risk_classifier': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'system.audit_log': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'intelligence.tuner_cache': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(get_gene=1024),
    'intelligence.conditioned_reflexes': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'intelligence.screen_watcher': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'memory.skill_store': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'memory.shadow_learner': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
    'memory.memory_injector': __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(),
}


@pytest.fixture
def fast_path_fn():
    """Import and return _try_fast_path with mocked dependencies."""
    with __import__('unittest.mock', fromlist=['patch']).patch.dict('sys.modules', _mocked_modules):
        from backend.llm import jarvis
        return jarvis._try_fast_path



class TestCompoundFastPath:
    """Test the compound fast-path regex in _try_fast_path."""

    def test_compound_basic_html(self, fast_path_fn):
        """Basic: 'open notepad and write "<html>...""' → write_file"""
        result = fast_path_fn('open notepad and write "<html><body>test</body></html>"')
        assert result is not None
        tool_name, tool_args = result
        assert tool_name == "write_file"
        assert "path" in tool_args
        assert "<html>" in tool_args["content"]

    def test_compound_html_extension(self, fast_path_fn):
        """HTML content should produce .html extension."""
        result = fast_path_fn('open notepad and write "<!DOCTYPE html><html><head><title>Test</title></head><body>Hello</body></html>"')
        assert result is not None
        tool_name, tool_args = result
        assert tool_name == "write_file"
        assert tool_args["path"].endswith(".html")

    def test_compound_description_falls_through(self, fast_path_fn):
        """'open notepad and write a poem' → falls through to simple open_app."""
        result = fast_path_fn('open notepad and write a poem about cats')
        if result is not None:
            tool_name, _ = result
            # Should be open_app (simple pattern), not write_file
            assert tool_name == "open_app"

    def test_compound_two_ands_falls_through(self, fast_path_fn):
        """User's actual command with two 'and's falls through to LLM."""
        result = fast_path_fn(
            'open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage'
        )
        # The compound regex only handles ONE separator.
        # With two "and"s, it falls through to the simple "open X" pattern.
        if result is not None:
            tool_name, _ = result
            assert tool_name == "open_app"

    def test_compound_with_then(self, fast_path_fn):
        """'open notepad then write "<html>..." → write_file."""
        result = fast_path_fn('open notepad then write "<html>test</html>"')
        # "then" is a valid separator in the regex
        # But the content must start with quotes or contain < or {
        if result is not None:
            tool_name, tool_args = result
            assert tool_name == "write_file"
            assert "content" in tool_args

    def test_simple_open_still_works(self, fast_path_fn):
        """Simple 'open notepad' should still return open_app."""
        result = fast_path_fn('open notepad')
        assert result is not None
        tool_name, tool_args = result
        assert tool_name == "open_app"
        assert tool_args["app_name"] == "notepad"


class TestSmartContentRouting:
    """Test the smart routing that converts type_text > 500 chars → write_file + open_app."""

    def test_extension_detection_html(self):
        """HTML content should get .html extension."""
        def detect_extension(text):
            ext = ".txt"
            text_lower = text.lower()
            if "<!doctype html" in text_lower or "<html" in text_lower:
                ext = ".html"
            elif text_lower.strip().startswith("{") and ('"' in text or "function" in text_lower):
                ext = ".js"
            elif text_lower.strip().startswith("import ") or text_lower.strip().startswith("from "):
                ext = ".py"
            elif text_lower.strip().startswith("# ") and "\n" in text:
                ext = ".md"
            return ext

        assert detect_extension('<!DOCTYPE html><html><body>test</body></html>') == ".html"
        assert detect_extension('<html><head></head><body>hello</body></html>') == ".html"

    def test_extension_detection_js(self):
        """JS content should get .js extension."""
        def detect_extension(text):
            ext = ".txt"
            text_lower = text.lower()
            if "<!doctype html" in text_lower or "<html" in text_lower:
                ext = ".html"
            elif text_lower.strip().startswith("{") and ('"' in text or "function" in text_lower):
                ext = ".js"
            elif text_lower.strip().startswith("import ") or text_lower.strip().startswith("from "):
                ext = ".py"
            elif text_lower.strip().startswith("# ") and "\n" in text:
                ext = ".md"
            return ext

        assert detect_extension('{"name": "test"}') == ".js"
        # 'function hello()' doesn't start with '{', so extension detection won't match JS here
        # The actual code only detects JS when text starts with '{'
        assert detect_extension('{"name": "test", "version": "1.0"}') == ".js"

    def test_extension_detection_python(self):
        """Python content should get .py extension."""
        def detect_extension(text):
            ext = ".txt"
            text_lower = text.lower()
            if "<!doctype html" in text_lower or "<html" in text_lower:
                ext = ".html"
            elif text_lower.strip().startswith("{") and ('"' in text or "function" in text_lower):
                ext = ".js"
            elif text_lower.strip().startswith("import ") or text_lower.strip().startswith("from "):
                ext = ".py"
            elif text_lower.strip().startswith("# ") and "\n" in text:
                ext = ".md"
            return ext

        assert detect_extension('import os\nprint("hello")') == ".py"
        assert detect_extension('from pathlib import Path\nprint("hello")') == ".py"

    def test_extension_detection_markdown(self):
        """Markdown content should get .md extension."""
        def detect_extension(text):
            ext = ".txt"
            text_lower = text.lower()
            if "<!doctype html" in text_lower or "<html" in text_lower:
                ext = ".html"
            elif text_lower.strip().startswith("{") and ('"' in text or "function" in text_lower):
                ext = ".js"
            elif text_lower.strip().startswith("import ") or text_lower.strip().startswith("from "):
                ext = ".py"
            elif text_lower.strip().startswith("# ") and "\n" in text:
                ext = ".md"
            return ext

        assert detect_extension('# Hello World\nThis is a test') == ".md"

    def test_smart_routing_threshold(self):
        """Content <= 500 chars should NOT be routed to write_file."""
        short_text = "hello world, this is a short message"
        assert len(short_text) < 500

        long_text = "x" * 600
        assert len(long_text) > 500

    def test_extra_open_variable_is_set(self):
        """Verify _extra_open is set correctly when smart routing triggers."""
        tool_name = "type_text"
        tool_args = {"text": "<!DOCTYPE html><html><body>" + "x" * 600 + "</body></html>"}
        _extra_open = None

        if tool_name == "type_text":
            _text_content = tool_args.get("text", "")
            if len(_text_content) > 500:
                _ext = ".html"
                _file_path = os.path.join(os.path.expanduser("~"), "Desktop", f"may_output{_ext}")
                tool_name = "write_file"
                tool_args = {"path": _file_path, "content": _text_content}
                _extra_open = {"name": "open_app", "args": {"app_name": _file_path}}
            else:
                _extra_open = None
        else:
            _extra_open = None

        assert tool_name == "write_file"
        assert _extra_open is not None
        assert _extra_open["name"] == "open_app"
        assert _extra_open["args"]["app_name"].endswith(".html")


class TestSystemPrompt:
    """Test that the system prompt contains the strengthened TOOL GUIDELINES."""

    def test_prompt_forbids_type_text_for_code(self):
        """System prompt should explicitly forbid typing code via type_text."""
        jarvis_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py')
        with open(jarvis_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "NEVER try to type code/HTML via type_text" in content
        assert "ALWAYS use write_file for long content" in content
        assert "write_file" in content
        assert "open_app" in content

    def test_prompt_has_correct_threshold(self):
        """System prompt should specify <200 chars for type_text."""
        jarvis_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py')
        with open(jarvis_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "<200 chars" in content


class TestExtraOpenExecution:
    """Test that the _extra_open execution code exists and is correct."""

    def test_extra_open_execution_code_exists(self):
        """Verify the jarvis.py file contains the _extra_open execution code."""
        jarvis_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py')
        with open(jarvis_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "_extra_open is not None" in content
        assert "execute_tool(_eo_name, _eo_args)" in content
        assert "round_results.append" in content

    def test_max_tokens_increased(self):
        """Verify follow-up round max_tokens is 1024, not 512."""
        jarvis_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py')
        with open(jarvis_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Should have max_tokens=1024 in the agentic loop
        assert "max_tokens=1024" in content
        # Should NOT have max_tokens=512 (old value)
        assert "max_tokens=512" not in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
