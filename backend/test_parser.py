"""Test the text-based tool call parser."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from llm.jarvis import _parse_text_tool_calls, _strip_tool_json

# Test 1: ```json code block
test1 = 'Sure!\n```json\n{"tool": "open_app", "args": {"app_name": "notepad"}}\n```\nDone~'
calls1 = _parse_text_tool_calls(test1)
print(f"Test1 calls: {calls1}")
assert len(calls1) == 1, f"Expected 1 call, got {len(calls1)}"
assert calls1[0]["name"] == "open_app"
assert calls1[0]["args"]["app_name"] == "notepad"
print("Test1 PASS")

# Test 2: bare JSON
test2 = 'Let me do that. {"tool": "set_volume", "args": {"level": 80}}'
calls2 = _parse_text_tool_calls(test2)
print(f"Test2 calls: {calls2}")
assert len(calls2) == 1, f"Expected 1 call, got {len(calls2)}"
assert calls2[0]["name"] == "set_volume"
assert calls2[0]["args"]["level"] == 80
print("Test2 PASS")

# Test 3: no tool calls (normal chat)
test3 = "Hey there~ How are you doing today?"
calls3 = _parse_text_tool_calls(test3)
assert len(calls3) == 0
print("Test3 PASS: no false positives")

# Test 4: multiple tool calls
test4 = '''```json
{"tool": "open_app", "args": {"app_name": "chrome"}}
```
```json
{"tool": "web_search", "args": {"query": "cute cats"}}
```'''
calls4 = _parse_text_tool_calls(test4)
print(f"Test4 calls: {calls4}")
assert len(calls4) == 2, f"Expected 2 calls, got {len(calls4)}"
assert calls4[0]["name"] == "open_app"
assert calls4[1]["name"] == "web_search"
print("Test4 PASS")

# Test 5: strip tool json from text
test5_input = 'Opening notepad!\n```json\n{"tool": "open_app", "args": {"app_name": "notepad"}}\n```\nDone~'
test5_stripped = _strip_tool_json(test5_input)
print(f"Test5 stripped: {test5_stripped!r}")
assert "open_app" not in test5_stripped
assert "Opening" in test5_stripped
assert "Done" in test5_stripped
print("Test5 PASS")

# Test 6: strip bare JSON
test6_input = 'Let me set volume. {"tool": "set_volume", "args": {"level": 80}} Done~'
test6_stripped = _strip_tool_json(test6_input)
print(f"Test6 stripped: {test6_stripped!r}")
assert "set_volume" not in test6_stripped
assert "Let me set volume" in test6_stripped
assert "Done" in test6_stripped
print("Test6 PASS")

print("\nALL TESTS PASSED")
