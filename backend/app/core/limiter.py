"""Shared rate limiter instance.

Defined here (not in main.py) to avoid circular imports when route modules
need to apply @limiter.limit() decorators.

Registered on app.state in main.py.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
