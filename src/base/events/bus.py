import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event_name: str):
        def decorator(handler: Handler):
            self._handlers[event_name].append(handler)
            return handler
        return decorator

    async def emit(self, event_name: str, payload: dict[str, Any]):
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return
        tasks = [handler(payload) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
