"""Federation proxy to The Draft Room's FastAPI service.

The draft board and live advisor stay owned by the fantasy-football repo
(models, Sleeper draft logic, its own deploy pipeline); the Desk exposes them
under this domain so the whole experience lives at one URL. Same-host hop,
allowlisted endpoints only.
"""
import logging
import os

import requests
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .auth_views import login_required_api

logger = logging.getLogger(__name__)

UPSTREAM = os.environ.get('DRAFT_API_UPSTREAM', 'http://127.0.0.1:8010')
# The Draft Room sits behind its own Google gate; the Desk's server-side hop
# carries a shared secret instead (DESK_PROXY_KEY in both .env files).
PROXY_KEY = os.environ.get('DESK_PROXY_KEY', '')

ENDPOINTS = {
    'board': '/board.json',
    'leagues': '/api/leagues',
    'advise': '/api/advise',
}

proxy_session = requests.Session()


@require_http_methods(["GET"])
@login_required_api
def proxy(request, endpoint):
    path = ENDPOINTS.get(endpoint)
    if not path:
        return JsonResponse({'error': f"unknown draft endpoint '{endpoint}'"},
                            status=404)
    try:
        upstream = proxy_session.get(
            f'{UPSTREAM}{path}', params=request.GET.dict(), timeout=30,
            headers={'X-Desk-Key': PROXY_KEY} if PROXY_KEY else None)
    except requests.RequestException as e:
        logger.error(f'draft proxy {endpoint} unreachable: {e}')
        return JsonResponse({'error': 'draft service unavailable',
                             'message': str(e)}, status=502)
    try:
        body = upstream.json()
    except ValueError:
        return JsonResponse({'error': 'draft service returned non-JSON'},
                            status=502)
    return JsonResponse(body, status=upstream.status_code, safe=False)
