import asyncio
import types

# Compatibility shim for Python 3.13+ where asyncio.coroutine was removed.
# pysnmp (system package) still references it at import time.
if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = types.coroutine
