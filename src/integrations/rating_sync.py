"""Push ratings from Shelve to connected external services (Trakt, SIMKL)."""

import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

import app.providers.services as services
from app.models import MediaTypes, Sources
from integrations.imports.helpers import decrypt, encrypt

logger = logging.getLogger(__name__)

TRAKT_API_BASE_URL = "https://api.trakt.tv"
SIMKL_API_BASE_URL = "https://api.simkl.com"

# Media types that Trakt/SIMKL support for ratings
TRAKT_SUPPORTED_TYPES = {
    MediaTypes.MOVIE.value,
    MediaTypes.TV.value,
    MediaTypes.SEASON.value,
    MediaTypes.ANIME.value,
}
SIMKL_SUPPORTED_TYPES = {
    MediaTypes.MOVIE.value,
    MediaTypes.TV.value,
    MediaTypes.ANIME.value,
}


def shelve_score_to_external(score):
    """Convert Shelve score (Decimal 0-10) to external API integer (1-10).

    Returns None if score cannot be mapped (e.g. 0 or None).
    """
    if score is None:
        return None
    int_score = int(Decimal(str(score)).quantize(Decimal("1")))
    if int_score < 1:
        return None
    return min(int_score, 10)


def get_tmdb_id_for_item(item):
    """Resolve TMDB ID for an Item. Returns (tmdb_id, media_type_for_api) or (None, None)."""
    if item.source == Sources.TMDB.value:
        return item.media_id, item.media_type

    # Check ItemProviderLink for a TMDB mapping
    from app.models import ItemProviderLink

    link = ItemProviderLink.objects.filter(
        item=item,
        provider=Sources.TMDB.value,
    ).first()
    if link:
        return link.provider_media_id, item.media_type

    return None, None


def push_rating_to_all(user, item, score):
    """Dispatch rating push to all connected services for this user.

    Called from score update views. Enqueues Celery tasks for each service.
    """
    from integrations.tasks import push_rating_simkl, push_rating_trakt

    score_str = str(score) if score is not None else None

    # Trakt
    trakt_account = getattr(user, "trakt_account", None)
    if trakt_account and trakt_account.is_connected and trakt_account.rating_sync_enabled:
        if item.media_type in TRAKT_SUPPORTED_TYPES:
            if score_str is not None:
                push_rating_trakt.delay(user.id, item.id, score_str)
            else:
                from integrations.tasks import remove_rating_trakt

                remove_rating_trakt.delay(user.id, item.id)

    # SIMKL
    simkl_account = getattr(user, "simkl_account", None)
    if simkl_account and simkl_account.is_connected and simkl_account.rating_sync_enabled:
        if item.media_type in SIMKL_SUPPORTED_TYPES:
            if score_str is not None:
                push_rating_simkl.delay(user.id, item.id, score_str)
            else:
                from integrations.tasks import remove_rating_simkl

                remove_rating_simkl.delay(user.id, item.id)


def get_valid_trakt_token(trakt_account):
    """Return a valid decrypted access token, refreshing if needed.

    Returns None if refresh fails (marks connection as needing re-auth).
    """
    if not trakt_account.access_token:
        return None

    access_token = decrypt(trakt_account.access_token)

    # Check if token is still valid (refresh 1 day before expiry)
    if trakt_account.token_expires_at and trakt_account.token_expires_at > timezone.now() + timedelta(days=1):
        return access_token

    # Token expired or about to expire - refresh it
    if not trakt_account.refresh_token:
        return None

    refresh_token = decrypt(trakt_account.refresh_token)
    client_id = settings.TRAKT_API
    client_secret = settings.TRAKT_API_SECRET

    # Use per-user credentials if configured
    if trakt_account.client_id:
        client_id = decrypt(trakt_account.client_id)
    if trakt_account.client_secret:
        client_secret = decrypt(trakt_account.client_secret)

    try:
        response = services.api_request(
            "TRAKT",
            "POST",
            f"{TRAKT_API_BASE_URL}/oauth/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "redirect_uri": f"{settings.BASE_URL}/connect/trakt/callback",
            },
        )
    except services.ProviderAPIError:
        logger.warning("Trakt token refresh failed for user %s", trakt_account.user_id)
        return None

    # Store new tokens
    trakt_account.access_token = encrypt(response["access_token"])
    trakt_account.refresh_token = encrypt(response["refresh_token"])
    trakt_account.token_expires_at = timezone.now() + timedelta(days=90)
    trakt_account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])

    return response["access_token"]


def _trakt_media_type(media_type):
    """Map Shelve media type to Trakt API key."""
    if media_type in (MediaTypes.MOVIE.value,):
        return "movies"
    if media_type in (MediaTypes.TV.value, MediaTypes.ANIME.value):
        return "shows"
    if media_type == MediaTypes.SEASON.value:
        return "seasons"
    return None


def _simkl_media_type(media_type):
    """Map Shelve media type to SIMKL API key."""
    if media_type == MediaTypes.MOVIE.value:
        return "movies"
    if media_type in (MediaTypes.TV.value, MediaTypes.ANIME.value):
        return "shows"
    return None


def do_push_rating_to_trakt(user_id, item_id, score_str):
    """Push a single rating to Trakt."""
    from app.models import Item
    from integrations.models import TraktAccount

    try:
        trakt_account = TraktAccount.objects.get(user_id=user_id)
    except TraktAccount.DoesNotExist:
        return

    access_token = get_valid_trakt_token(trakt_account)
    if not access_token:
        logger.warning("No valid Trakt token for user %s, skipping rating push", user_id)
        return

    item = Item.objects.get(id=item_id)
    tmdb_id, media_type = get_tmdb_id_for_item(item)
    if not tmdb_id:
        logger.debug("No TMDB ID for item %s, skipping Trakt rating push", item)
        return

    trakt_type = _trakt_media_type(media_type)
    if not trakt_type:
        return

    score = shelve_score_to_external(Decimal(score_str))
    if score is None:
        return do_remove_rating_from_trakt(user_id, item_id)

    client_id = settings.TRAKT_API
    if trakt_account.client_id:
        client_id = decrypt(trakt_account.client_id)

    payload = {
        trakt_type: [
            {
                "rating": score,
                "ids": {"tmdb": int(tmdb_id)},
            },
        ],
    }

    try:
        services.api_request(
            "TRAKT",
            "POST",
            f"{TRAKT_API_BASE_URL}/sync/ratings",
            headers={
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": client_id,
                "Authorization": f"Bearer {access_token}",
            },
            params=payload,
        )
        logger.info("Pushed rating %s to Trakt for %s (TMDB %s)", score, item.title, tmdb_id)
    except services.ProviderAPIError as e:
        if e.status_code == requests.codes.unauthorized:
            logger.warning("Trakt auth failed for user %s, clearing tokens", user_id)
            trakt_account.access_token = None
            trakt_account.refresh_token = None
            trakt_account.token_expires_at = None
            trakt_account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        else:
            raise


def do_remove_rating_from_trakt(user_id, item_id):
    """Remove a rating from Trakt."""
    from app.models import Item
    from integrations.models import TraktAccount

    try:
        trakt_account = TraktAccount.objects.get(user_id=user_id)
    except TraktAccount.DoesNotExist:
        return

    access_token = get_valid_trakt_token(trakt_account)
    if not access_token:
        return

    item = Item.objects.get(id=item_id)
    tmdb_id, media_type = get_tmdb_id_for_item(item)
    if not tmdb_id:
        return

    trakt_type = _trakt_media_type(media_type)
    if not trakt_type:
        return

    client_id = settings.TRAKT_API
    if trakt_account.client_id:
        client_id = decrypt(trakt_account.client_id)

    payload = {
        trakt_type: [
            {"ids": {"tmdb": int(tmdb_id)}},
        ],
    }

    try:
        services.api_request(
            "TRAKT",
            "POST",
            f"{TRAKT_API_BASE_URL}/sync/ratings/remove",
            headers={
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": client_id,
                "Authorization": f"Bearer {access_token}",
            },
            params=payload,
        )
        logger.info("Removed rating from Trakt for %s (TMDB %s)", item.title, tmdb_id)
    except services.ProviderAPIError as e:
        if e.status_code == requests.codes.unauthorized:
            trakt_account.access_token = None
            trakt_account.refresh_token = None
            trakt_account.token_expires_at = None
            trakt_account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        else:
            raise


def do_push_rating_to_simkl(user_id, item_id, score_str):
    """Push a single rating to SIMKL."""
    from app.models import Item
    from integrations.models import SimklAccount

    try:
        simkl_account = SimklAccount.objects.get(user_id=user_id)
    except SimklAccount.DoesNotExist:
        return

    if not simkl_account.access_token:
        return

    access_token = decrypt(simkl_account.access_token)

    item = Item.objects.get(id=item_id)
    tmdb_id, media_type = get_tmdb_id_for_item(item)
    if not tmdb_id:
        logger.debug("No TMDB ID for item %s, skipping SIMKL rating push", item)
        return

    simkl_type = _simkl_media_type(media_type)
    if not simkl_type:
        return

    score = shelve_score_to_external(Decimal(score_str))
    if score is None:
        return do_remove_rating_from_simkl(user_id, item_id)

    payload = {
        simkl_type: [
            {
                "rating": score,
                "ids": {"tmdb": int(tmdb_id)},
            },
        ],
    }

    try:
        services.api_request(
            "SIMKL",
            "POST",
            f"{SIMKL_API_BASE_URL}/sync/ratings",
            headers={
                "Content-Type": "application/json",
                "simkl-api-key": settings.SIMKL_ID,
                "Authorization": f"Bearer {access_token}",
            },
            params=payload,
        )
        logger.info("Pushed rating %s to SIMKL for %s (TMDB %s)", score, item.title, tmdb_id)
    except services.ProviderAPIError as e:
        if e.status_code == requests.codes.unauthorized:
            logger.warning("SIMKL auth failed for user %s, clearing token", user_id)
            simkl_account.access_token = None
            simkl_account.save(update_fields=["access_token", "updated_at"])
        else:
            raise


def do_remove_rating_from_simkl(user_id, item_id):
    """Remove a rating from SIMKL."""
    from app.models import Item
    from integrations.models import SimklAccount

    try:
        simkl_account = SimklAccount.objects.get(user_id=user_id)
    except SimklAccount.DoesNotExist:
        return

    if not simkl_account.access_token:
        return

    access_token = decrypt(simkl_account.access_token)

    item = Item.objects.get(id=item_id)
    tmdb_id, media_type = get_tmdb_id_for_item(item)
    if not tmdb_id:
        return

    simkl_type = _simkl_media_type(media_type)
    if not simkl_type:
        return

    payload = {
        simkl_type: [
            {"ids": {"tmdb": int(tmdb_id)}},
        ],
    }

    try:
        services.api_request(
            "SIMKL",
            "POST",
            f"{SIMKL_API_BASE_URL}/sync/ratings/remove",
            headers={
                "Content-Type": "application/json",
                "simkl-api-key": settings.SIMKL_ID,
                "Authorization": f"Bearer {access_token}",
            },
            params=payload,
        )
        logger.info("Removed rating from SIMKL for %s (TMDB %s)", item.title, tmdb_id)
    except services.ProviderAPIError as e:
        if e.status_code == requests.codes.unauthorized:
            simkl_account.access_token = None
            simkl_account.save(update_fields=["access_token", "updated_at"])
        else:
            raise
