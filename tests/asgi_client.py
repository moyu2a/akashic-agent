from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

import httpx2
from fastapi import FastAPI
from fastapi.routing import APIRoute, request_response


class TestClient:
    """Small sync ASGI client for tests.

    Starlette's TestClient currently blocks in this environment while starting
    its anyio blocking portal. The dashboard tests only need basic HTTP methods,
    so this wrapper uses httpx2's ASGITransport directly.
    """

    __test__ = False

    def __init__(self, app: Any, *, base_url: str = "http://testserver") -> None:
        self._app = _wrap_sync_endpoints(app)
        self._base_url = base_url
        self._loop = asyncio.new_event_loop()
        self._lock = threading.RLock()

    def __enter__(self) -> "TestClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
        return None

    def close(self) -> None:
        with self._lock:
            if self._loop.is_closed():
                return
            self._loop.run_until_complete(_drain_pending_tasks())
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def get(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self._request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self._request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self._request("DELETE", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        return self._request(method, url, **kwargs)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        async def _run() -> httpx2.Response:
            transport = httpx2.ASGITransport(app=self._app)
            async with httpx2.AsyncClient(
                transport=transport,
                base_url=self._base_url,
            ) as client:
                return await client.request(method, url, **kwargs)

        with self._lock:
            response = self._loop.run_until_complete(_run())
            self._loop.run_until_complete(asyncio.sleep(0))
            return response


async def _drain_pending_tasks() -> None:
    pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    if not pending:
        return
    done, pending = await asyncio.wait(pending, timeout=2.0)
    for task in done:
        task.result()
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def _wrap_sync_endpoints(app: Any) -> Any:
    if not isinstance(app, FastAPI):
        return app
    wrapped = FastAPI(
        title=app.title,
        description=app.description,
        version=app.version,
        lifespan=app.router.lifespan_context,
    )
    wrapped.state.__dict__.update(app.state.__dict__)
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            wrapped.router.routes.append(route)
            continue
        endpoint = route.dependant.call
        if endpoint is None or inspect.iscoroutinefunction(endpoint):
            wrapped.router.routes.append(route)
            continue
        route.dependant.call = _async_endpoint(endpoint)
        route.dependant.is_coroutine_callable = True
        route.endpoint = route.dependant.call
        route.app = request_response(route.get_route_handler())
        wrapped.router.routes.append(route)
    return wrapped


def _async_endpoint(endpoint: Any) -> Any:
    async def _wrapped(*args: Any, **kwargs: Any) -> Any:
        return endpoint(*args, **kwargs)

    _wrapped.__name__ = getattr(endpoint, "__name__", "_wrapped")
    _wrapped.__qualname__ = getattr(endpoint, "__qualname__", _wrapped.__name__)
    if hasattr(endpoint, "__signature__"):
        _wrapped.__signature__ = getattr(endpoint, "__signature__")
    return _wrapped
