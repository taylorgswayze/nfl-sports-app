"""Fire-and-forget usage events to the fleet's central sink.

track() posts one small JSON event to usage.taylorswayze.com from a daemon
thread; ActiveUserMiddleware emits a throttled "active" heartbeat for
signed-in users. When USAGE_INGEST_KEY is missing from the environment,
tracking is a silent no-op, so development machines send nothing.
"""

import json
import os
import threading
import time
import urllib.request

USAGE_URL = os.environ.get("USAGE_URL", "http://rpi5.local/collect")
APP_NAME = 'nfl'
HEARTBEAT_SECONDS = 15 * 60

# Request paths that are noise, not user behavior.
SKIP_PREFIXES = ('/static/', '/staticfiles/', '/favicon',
                 '/admin/jsi18n', '/health', '/api/health')


def track(name, user=None, **props):
    """Send one usage event without blocking the request or ever raising."""
    key = os.environ.get('USAGE_INGEST_KEY', '')
    if not key:
        return
    body = {'app': APP_NAME, 'name': name}
    if user:
        body['user'] = user.lower()
    if props:
        body['props'] = props

    def _send():
        try:
            req = urllib.request.Request(
                USAGE_URL,
                data=json.dumps(body).encode(),
                headers={'X-Usage-Key': key,
                         'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=3).close()
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


# In-process heartbeat state: last event time and cached email per DeskUser
# id. Both reset on restart, which at worst means one extra event.
_last_beat = {}
_emails = {}


class ActiveUserMiddleware:
    """Emits track('active') at most once per signed-in user per 15 minutes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            self._heartbeat(request)
        except Exception:
            pass
        return self.get_response(request)

    def _heartbeat(self, request):
        if request.path.startswith(SKIP_PREFIXES):
            return
        uid = request.session.get('desk_user_id')
        if not uid:
            return
        now = time.monotonic()
        last = _last_beat.get(uid)
        if last is not None and now - last < HEARTBEAT_SECONDS:
            return
        email = _emails.get(uid)
        if not email:
            from .models import DeskUser
            row = DeskUser.objects.filter(id=uid).only('email').first()
            if not row:
                return
            email = _emails[uid] = row.email
        _last_beat[uid] = now
        track('active', user=email, path=request.path)
