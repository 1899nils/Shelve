"""Helper to retrieve application settings from the database."""

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "app_settings_tmdb_api_key"
CACHE_TTL = 60 * 10  # 10 minutes


def get_tmdb_api_key():
    """Return the TMDB API key, preferring DB value over env var."""
    # Try cache first
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached if cached != "" else ""

    # Try database
    try:
        from app.models import AppSettings

        app_settings = AppSettings.load()
        if app_settings.tmdb_api_key:
            cache.set(CACHE_KEY, app_settings.tmdb_api_key, CACHE_TTL)
            return app_settings.tmdb_api_key
    except Exception:
        # DB not ready yet (migrations, collectstatic, etc.)
        pass

    # Fall back to environment variable
    env_key = settings.TMDB_API
    if env_key:
        cache.set(CACHE_KEY, env_key, CACHE_TTL)
    return env_key


def clear_tmdb_api_key_cache():
    """Clear the cached TMDB API key after updates."""
    cache.delete(CACHE_KEY)
