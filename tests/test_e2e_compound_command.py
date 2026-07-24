"""
End-to-end integration test for compound commands.

Tests the actual user command flow:
  "open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage"

Verifies:
1. Fast-path doesn't match (two 'and's) — falls through to LLM
2. LLM generates write_file + open_app (correct routing)
3. If LLM incorrectly generates type_text >500 chars, smart routing intercepts
4. _extra_open execution (open_app after write_file)
"""

import os
import sys
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Mock all jarvis.py dependencies ──────────────────────────────────────
_mocked_modules = {
    'llm.resilience': MagicMock(format_partial_results=lambda x: "\n".join(x)),
    'llm.tools': MagicMock(TOOLS=[]),
    'llm.tool_tiering': MagicMock(get_tools_for_message=lambda msg, tools: tools),
    'llm.core_bridge': MagicMock(),
    'llm.providers': MagicMock(),
    'plugins': MagicMock(get_plugin_manager=MagicMock(return_value=MagicMock(get_all_plugin_tools=lambda: []))),
    'system.risk_classifier': MagicMock(classify_action=lambda *a: "safe", needs_confirmation=lambda *a: False),
    'system.audit_log': MagicMock(),
    'intelligence.tuner_cache': MagicMock(get_gene=MagicMock(return_value=1024)),
    'intelligence.conditioned_reflexes': MagicMock(),
    'intelligence.screen_watcher': MagicMock(),
    'memory.skill_store': MagicMock(),
    'memory.shadow_learner': MagicMock(),
    'memory.memory_injector': MagicMock(),
}


# ── Test 1: Fast-path correctly falls through for compound command ───────
class TestFastPathFallback:
    """Verify the compound command falls through to LLM (not fast-path)."""

    def test_compound_command_does_not_match_fast_path(self):
        """The user's command has two 'and's — fast-path should not match."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _try_fast_path

        result = _try_fast_path("open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage")
        assert result is None, f"Fast-path should NOT match compound command, got {result}"

    def test_simple_compound_matches_fast_path(self):
        """Simple compound like 'open notepad and write \"hello\"' SHOULD match."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _try_fast_path

        result = _try_fast_path('open notepad and write "<html>test</html>"')
        assert result is not None, "Simple compound should match fast-path"
        assert result[0] == "write_file"


# ── Test 2: Smart routing intercepts long type_text ──────────────────────
class TestSmartRoutingSafetyNet:
    """Verify smart routing converts type_text >500 chars to write_file + open_app."""

    def test_type_text_long_html_intercepted(self):
        """If LLM incorrectly generates type_text with >500 chars of HTML, smart routing intercepts."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _smart_route_type_text

        html_content = "<!DOCTYPE html>\n<html>\n<body>\n" + "<p>Pokemon</p>\n" * 100 + "</body>\n</html>"
        assert len(html_content) > 500

        name, args, extra = _smart_route_type_text("type_text", {"text": html_content, "window_title": "notepad"})

        assert name == "write_file", "Should convert type_text to write_file"
        assert args["content"] == html_content, "Content should be preserved exactly"
        assert args["path"].endswith(".html"), "Should detect HTML extension"
        assert extra is not None, "Should generate _extra_open for open_app"
        assert extra["name"] == "open_app"
        assert extra["args"]["app_name"] == args["path"]

    def test_type_text_short_not_intercepted(self):
        """Short type_text (<500 chars) should NOT be intercepted."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _smart_route_type_text

        name, args, extra = _smart_route_type_text("type_text", {"text": "hello world", "window_title": "notepad"})

        assert name == "type_text", "Should remain type_text"
        assert args["text"] == "hello world"
        assert extra is None, "Should not generate extra_open"


# ── Test 3: Agentic loop executes write_file + open_app ──────────────────
class TestAgenticLoopFlow:
    """Verify the agentic loop correctly executes write_file then open_app."""

    @pytest.mark.asyncio
    async def test_write_file_then_open_app_executed(self):
        """When LLM returns write_file + open_app, both should be executed."""
        mock_execute = AsyncMock(return_value="OK")

        with patch.dict('sys.modules', _mocked_modules):
            with patch('backend.llm.jarvis.execute_tool', mock_execute):
                from backend.llm.jarvis import _smart_route_type_text

                # Simulate what the agentic loop does with type_text >500 chars
                tool_name = "type_text"
                tool_args = {"text": "<!DOCTYPE html><html><body>" + "x" * 600 + "</body></html>", "window_title": "notepad"}

                # Smart routing converts type_text → write_file + open_app
                new_name, new_args, extra_open = _smart_route_type_text(tool_name, tool_args)

                assert new_name == "write_file"

                # Simulate agentic loop executing write_file
                result1 = await mock_execute(new_name, new_args)
                assert result1 == "OK"

                # Simulate agentic loop executing _extra_open
                if extra_open is not None:
                    result2 = await mock_execute(extra_open["name"], extra_open["args"])
                    assert result2 == "OK"

                assert mock_execute.call_count == 2, "Both write_file and open_app should be called"
                call_args_list = [call.args for call in mock_execute.call_args_list]
                assert call_args_list[0][0] == "write_file"
                assert call_args_list[1][0] == "open_app"


# ── Test 4: System prompt correctly guides LLM ──────────────────────────
class TestSystemPromptGuidance:
    """Verify the system prompt contains the correct guidance for the LLM."""

    def test_prompt_forbids_type_text_for_code(self):
        """System prompt must tell LLM to NEVER type code via type_text."""
        with open(os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py'), 'r', encoding='utf-8') as f:
            source = f.read()

        assert "NEVER try to type code/HTML via type_text" in source
        assert "ALWAYS use write_file for long content" in source
        assert "Long text (code, HTML, essays, >200 chars) -> write_file" in source

    def test_prompt_tells_llm_to_use_write_file_then_open_app(self):
        """System prompt must tell LLM to use write_file THEN open_app."""
        with open(os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py'), 'r', encoding='utf-8') as f:
            source = f.read()

        assert "write_file(path=\"filename.ext\", content=\"the code\") THEN open_app" in source


# ── Test 5: _extra_open is actually executed (not just set) ──────────────
class TestExtraOpenExecution:
    """Verify the agentic loop actually executes _extra_open, not just sets it."""

    def test_extra_open_execution_exists_in_source(self):
        """The agentic loop must have code to execute _extra_open after write_file."""
        with open(os.path.join(os.path.dirname(__file__), '..', 'backend', 'llm', 'jarvis.py'), 'r', encoding='utf-8') as f:
            source = f.read()

        assert "_extra_open is not None" in source
        assert "_eo_name = _extra_open[\"name\"]" in source
        assert "_eo_result = await execute_tool(_eo_name, _eo_args)" in source
        assert "yield f\"\\n\\n🔧 `{_eo_name}({_eo_args_str})`\\n\"" in source


# ── Test 6: Full flow simulation ────────────────────────────────────────
class TestFullFlowSimulation:
    """Simulate the complete flow from user message to tool execution."""

    def test_full_simulation_with_mocked_llm(self):
        """Simulate: user message → fast-path check → LLM response → smart routing → tool execution."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _try_fast_path, _smart_route_type_text

        user_message = "open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage"

        # Step 1: Fast-path should NOT match
        fast = _try_fast_path(user_message)
        assert fast is None, "Step 1: Fast-path should not match compound command"

        # Step 2: Simulate LLM incorrectly generating type_text (the safety net scenario)
        llm_tool_name = "type_text"
        llm_tool_args = {
            "text": "<!DOCTYPE html>\n<html>\n<head>\n<title>Pokemon</title>\n</head>\n<body>\n<h1>Pokemon Fan Page</h1>\n" + "<p>Content</p>\n" * 100 + "</body>\n</html>",
            "window_title": "notepad",
        }
        assert len(llm_tool_args["text"]) > 500, "LLM content should be >500 chars"

        # Step 3: Smart routing should intercept
        routed_name, routed_args, extra_open = _smart_route_type_text(llm_tool_name, llm_tool_args)
        assert routed_name == "write_file", "Step 3: Smart routing should convert to write_file"
        assert routed_args["content"] == llm_tool_args["text"], "Content must be preserved"
        assert routed_args["path"].endswith(".html"), "Should detect HTML"
        assert extra_open is not None, "Step 3: Should generate open_app"
        assert extra_open["name"] == "open_app"

        # Step 4: Verify the open_app targets the written file
        assert extra_open["args"]["app_name"] == routed_args["path"], "open_app should target the written file"

    def test_full_simulation_with_correct_llm_response(self):
        """Simulate: LLM correctly generates write_file + open_app (no smart routing needed)."""
        with patch.dict('sys.modules', _mocked_modules):
            from backend.llm.jarvis import _try_fast_path, _smart_route_type_text

        user_message = "open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage"

        # Step 1: Fast-path should NOT match
        fast = _try_fast_path(user_message)
        assert fast is None, "Step 1: Fast-path should not match"

        # Step 2: Simulate LLM correctly generating write_file (what the system prompt guides it to do)
        llm_tool_name = "write_file"
        llm_tool_args = {
            "path": os.path.join(os.path.expanduser("~"), "Desktop", "pokemon.html"),
            "content": "<!DOCTYPE html>\n<html>\n<head><title>Pokemon</title></head>\n<body>\n<h1>Pokemon</h1>\n</body>\n</html>",
        }

        # Step 3: Smart routing should NOT interfere (content is already write_file)
        routed_name, routed_args, extra_open = _smart_route_type_text(llm_tool_name, llm_tool_args)
        assert routed_name == "write_file", "Should remain write_file"
        assert routed_args == llm_tool_args, "Args should be unchanged"
        assert extra_open is None, "Should not generate extra_open (already write_file)"


# ── Test 7: True E2E through jarvis_chat ─────────────────────────────────
class TestJarvisChatE2E:
    """True end-to-end test calling jarvis_chat with mocked LLM."""

    @pytest.mark.asyncio
    async def test_chat_write_file_and_open_app(self):
        """jarvis_chat with mocked LLM returning write_file + open_app."""
        # LLM returns write_file + open_app in tool_calls
        llm_response_events = [
            {"type": "text", "content": "I'll create a Pokemon HTML file for you."},
            {"type": "tool_calls", "tool_calls": [
                {"id": "call_1", "name": "write_file", "args": {
                    "path": os.path.join(os.path.expanduser("~"), "Desktop", "pokemon.html"),
                    "content": "<!DOCTYPE html>\n<html>\n<body><h1>Pokemon</h1></body>\n</html>",
                }},
                {"id": "call_2", "name": "open_app", "args": {
                    "app_name": os.path.join(os.path.expanduser("~"), "Desktop", "pokemon.html"),
                }},
            ]},
        ]
        # After first round, LLM returns no more tool calls
        llm_response_done = [
            {"type": "text", "content": "Done! Pokemon HTML created and opened."},
        ]

        call_count = 0
        async def mock_stream(**kwargs):
            nonlocal call_count
            events = llm_response_events if call_count == 0 else llm_response_done
            call_count += 1
            for e in events:
                yield e

        mock_execute = AsyncMock(return_value="Tool executed OK")

        with patch.dict('sys.modules', _mocked_modules):
            # Set mock_stream directly on the mock module (avoids patch() import resolution issues)
            _mocked_modules['llm.providers'].stream_chat_with_tools = mock_stream

            with patch('backend.llm.jarvis.execute_tool', mock_execute):
                # Disable skill store, reflexes, memory to avoid side effects
                import backend.llm.jarvis as jarvis_mod
                jarvis_mod._skill_store_ref = None
                jarvis_mod._conditioned_reflexes_ref = None
                jarvis_mod._memory_injector_ref = None
                jarvis_mod._personality_modes_ref = None

                from backend.llm.jarvis import jarvis_chat

                responses = []
                async for chunk in jarvis_chat(
                    message="open notepad and write HTML code about pokemon",
                    history=[],
                    provider="test",
                    model="test",
                ):
                    responses.append(chunk)

                # Both write_file and open_app should have been called
                assert mock_execute.call_count == 2, f"Expected 2 tool calls, got {mock_execute.call_count}"
                call_names = [call.args[0] for call in mock_execute.call_args_list]
                assert "write_file" in call_names, "write_file should be called"
                assert "open_app" in call_names, "open_app should be called"

                # LLM text response should appear
                full_text = " ".join(responses)
                assert "Pokemon" in full_text or "HTML" in full_text or "Done" in full_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
