"""Temporary middleware for memory profiling during upload debugging."""

import os
import sys

import psutil
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class MemoryProfilingMiddleware(BaseHTTPMiddleware):
    """Profile memory usage for each request (temporary debugging tool)."""

    async def dispatch(self, request: Request, call_next):
        # Only profile upload requests
        if request.url.path != "/upload-form":
            return await call_next(request)

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024

        print(f"[MEMORY MIDDLEWARE] Before request: {mem_before:.1f} MB", flush=True)
        sys.stdout.flush()

        response = await call_next(request)

        mem_after = process.memory_info().rss / 1024 / 1024
        print(
            f"[MEMORY MIDDLEWARE] After request: {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB)",
            flush=True,
        )
        sys.stdout.flush()

        return response
