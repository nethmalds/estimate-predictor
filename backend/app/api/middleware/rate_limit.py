import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])

_IS_DEV = os.getenv("ENV", "development").lower() != "production"


def _dev_limit(prod_limit: str, dev_limit: str = "500/minute") -> str:
    """Return a relaxed limit in dev so local testing never hits rate-limit walls."""
    return dev_limit if _IS_DEV else prod_limit
