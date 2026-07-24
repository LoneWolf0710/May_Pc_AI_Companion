import sys
sys.path.insert(0, r'C:\AI\may\backend')
from llm.jarvis import _parse_text_tool_calls

test = """open_app(app_name='notepad')
write_file(path='test.txt', content='hello world')
open_app(app_name='test.txt')"""

calls = _parse_text_tool_calls(test)
for c in calls:
    print(c['name'], c['args'])
