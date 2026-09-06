"""Google sign-in (authorization-code flow) plus Django sessions.

Uses the same Google OAuth client as undaunted.taylorswayze.com and mirrors
that app's flow: /api/auth/login/ redirects to Google, /api/auth/callback/
exchanges the code and sets the session cookie, /api/auth/logout/ clears it.
The id_token is accepted without local signature verification because it is
obtained directly from Google's token endpoint over TLS in the same request.

Anyone with a verified Google account may sign in; per-user state (Sleeper
username, notification settings) lives on DeskUser via /api/me/.
"""

import base64
import functools
import json
import logging
import os
import secrets
import urllib.parse

import requests
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import DeskUser
from .usage import track

logger = logging.getLogger(__name__)

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
REDIRECT_URI = os.environ.get(
    'OAUTH_REDIRECT', 'https://nfl-beta.taylorswayze.com/auth/callback')

AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URI = 'https://oauth2.googleapis.com/token'

STATE_COOKIE = 'oauth_state'
NEXT_COOKIE = 'oauth_next'


def _safe_next(value):
    """Only same-site paths come back from the sign-in trip."""
    v = (value or '').strip()
    return v if v.startswith('/') and not v.startswith('//') and '\\' not in v else '/'


def login_required_api(view):
    """The fantasy side of the Desk is for signed-in readers: 401 JSON with
    the sign-in URL so the page can print its gate instead of an error."""
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if not current_user(request):
            return JsonResponse({'error': 'sign in required', 'login': '/api/auth/login/'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def _is_https(request):
    return request.headers.get('x-forwarded-proto', request.scheme) == 'https'


def current_user(request):
    """The signed-in DeskUser for this request, or None."""
    uid = request.session.get('desk_user_id')
    if not uid:
        return None
    return DeskUser.objects.filter(id=uid).first()


@require_http_methods(['GET'])
def login(request):
    if not CLIENT_ID or not CLIENT_SECRET:
        return JsonResponse({'error': 'Google sign-in is not configured'}, status=503)
    state = secrets.token_urlsafe(16)
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    }
    resp = HttpResponseRedirect(f'{AUTH_URI}?{urllib.parse.urlencode(params)}')
    resp.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True,
                    secure=_is_https(request), samesite='Lax')
    resp.set_cookie(NEXT_COOKIE, _safe_next(request.GET.get('next')), max_age=600, httponly=True,
                    secure=_is_https(request), samesite='Lax')
    return resp


@require_http_methods(['GET'])
def callback(request):
    error = request.GET.get('error', '')
    if error:
        return HttpResponseRedirect('/?auth_error=' + urllib.parse.quote(error))
    code = request.GET.get('code', '')
    state = request.GET.get('state', '')
    if not code or not state or state != request.COOKIES.get(STATE_COOKIE):
        return JsonResponse({'error': 'Bad OAuth state'}, status=400)
    try:
        tok = requests.post(TOKEN_URI, data={
            'code': code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
        }, timeout=15)
    except requests.RequestException as e:
        logger.error(f'Google token exchange failed: {e}')
        return JsonResponse({'error': 'Google token exchange failed'}, status=502)
    if tok.status_code != 200:
        logger.error(f'Google token exchange returned {tok.status_code}: {tok.text[:200]}')
        return JsonResponse({'error': 'Google token exchange failed'}, status=502)
    id_token = tok.json().get('id_token', '')
    try:
        payload = id_token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return JsonResponse({'error': 'Bad id_token'}, status=502)
    if not claims.get('email') or not claims.get('email_verified', False):
        return JsonResponse({'error': 'Google account has no verified email'}, status=403)

    user, _created = DeskUser.objects.update_or_create(
        google_sub=claims['sub'],
        defaults={
            'email': claims['email'],
            'name': claims.get('name') or claims['email'],
            'picture': claims.get('picture', ''),
        })
    request.session['desk_user_id'] = user.id
    request.session.set_expiry(60 * 60 * 24 * 90)
    track('login', user=user.email)
    resp = HttpResponseRedirect(_safe_next(request.COOKIES.get(NEXT_COOKIE)))
    resp.delete_cookie(STATE_COOKIE)
    resp.delete_cookie(NEXT_COOKIE)
    return resp


@require_http_methods(['GET'])
def logout(request):
    request.session.flush()
    return HttpResponseRedirect('/')


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def me(request):
    """GET: who am I plus saved settings. PATCH: save sleeper_username and
    settings. CSRF is covered by the SameSite=Lax session cookie; the
    endpoint only ever touches the caller's own row."""
    user = current_user(request)
    if not user:
        return JsonResponse({'authenticated': False}, status=200)
    week_room = None
    if request.method == 'PATCH':
        try:
            body = json.loads(request.body or b'{}')
        except ValueError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        linked = False
        if 'sleeper_username' in body:
            new_name = str(body['sleeper_username'] or '').strip()[:100]
            linked = bool(new_name) and new_name.lower() != (user.sleeper_username or '').lower()
            user.sleeper_username = new_name
        if 'settings' in body and isinstance(body['settings'], dict):
            user.settings = {**user.settings, **body['settings']}
        user.save()
        if linked:
            # Linking a Sleeper account is the moment the Week Room starts:
            # build this user's reports now; the 12-hour cron takes over after.
            from . import fantasy_insights
            week_room = 'generating' if fantasy_insights.kick_for_username(user.sleeper_username) else 'ready'
            track('sleeper_linked', user=user.email, username=user.sleeper_username)
    return JsonResponse({
        'authenticated': True,
        'email': user.email,
        'name': user.name,
        'picture': user.picture,
        'sleeper_username': user.sleeper_username,
        'settings': user.settings,
        'week_room': week_room,
    })
