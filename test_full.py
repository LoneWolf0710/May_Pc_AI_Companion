import asyncio
import subprocess
import sys
import time

# Start daemon
proc = subprocess.Popen([sys.executable, '-m', 'core.daemon', 'debug'], 
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# Wait for startup
time.sleep(3)

# Test
async def test():
    try:
        from core.client import send_command
        result = await send_command('application', 'launch_app', {'app_name': 'lenovo vantage'}, timeout=15.0)
        print(f'Launch: success={result.success}, method={result.method_used}, error={result.error}')
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test())

# Give time for logs to flush
time.sleep(1)

# Check log
with open('core/logs/control_core.log', 'r') as f:
    content = f.read()
    idx = content.rfind('LIVE on 127.0.0.1:7650')
    if idx >= 0:
        after = content[idx:]
        print('Log after startup:')
        print(after[-2000:])

# Cleanup
try:
    proc.terminate()
except:
    pass