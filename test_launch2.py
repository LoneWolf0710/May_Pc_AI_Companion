import asyncio
import traceback

async def test():
    try:
        from core.bus import CommandBus
        from core.layers.L3_application import handler as app_handler
        
        bus = CommandBus()
        bus.register('application', app_handler)
        
        json_str = '{"layer": "application", "action": "launch_app", "params": {"app_name": "lenovo vantage"}}'
        result = await bus.dispatch_json(json_str)
        print(f'Result: success={result.success}, method={result.method_used}, error={result.error}')
    except Exception as e:
        print(f'Error: {e}')
        traceback.print_exc()

asyncio.run(test())