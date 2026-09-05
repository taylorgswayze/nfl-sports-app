"""OpenAI narrative for the Week Room: turns the engine's structured
payload into a few sentences in the Desk's voice. Optional: without
OPENAI_API_KEY (or on any error) the engine's template prose is printed
instead, so the product never depends on the call.

Uses the same OpenAI account as the budget app (OPENAI_API_KEY in .env);
one short chat completion per league per refresh, a few cents a day.
"""
import json
import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

API_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'

SYSTEM = (
    "You write the Week Room note for Gridiron Desk, a fantasy football almanac. "
    "Write in plain, direct English, second person (you), like a sharp beat writer. "
    "Two or three short paragraphs, 110 to 170 words total. Use only the facts in the "
    "JSON; never invent players, injuries, stats or opponents. "
    "Paragraph one: the matchup (your projected total vs theirs), then the exact "
    "roster moves in lineup.moves, each named with its from and to slot (move X from "
    "BN to FLEX, move Y from FLEX to BN), and the total gain. If lineup.moves is "
    "empty, say the lineup is already the projected optimum and move on. A waiver "
    "claim is never a lineup change. "
    "Paragraph two: waivers. These are recommended claims, not moves already made: "
    "say claim X and drop Y, with the rest-of-season gain per week and the this-week "
    "gain, plus anything in watch (byes, injuries). If waivers is empty, say no free "
    "agent clears the bench. "
    "Paragraph three, only if trades is non-empty: one trade idea with both sides' "
    "deltas, framed as an idea to float. "
    "Numbers to one decimal. No em dashes, no emojis, no headings, no bullet points, "
    "no markdown."
)

_EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


ENV_FILE = Path(__file__).resolve().parent.parent.parent / '.env'


def _dotenv(name):
    """Read one KEY=VALUE from the project .env: the cron driver (runcrons
    from crontab) does not load the systemd unit's EnvironmentFile."""
    try:
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f'{name}='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _setting(name, default=None):
    return os.environ.get(name) or _dotenv(name) or default


def configured():
    return bool(_setting('OPENAI_API_KEY'))


def _facts(p):
    """The slice of the payload the model needs, kept small."""
    def r1(v):
        return round(v, 1) if isinstance(v, (int, float)) else v

    def brief(x):
        if not x:
            return None
        return {k: r1(x.get(k)) for k in ('name', 'pos', 'team', 'proj', 'ros', 'injury', 'opp') if x.get(k) is not None}
    lu = p.get('lineup') or {}
    return {
        'league': p.get('name'), 'week': p.get('week'), 'scoring': p.get('scoring'),
        'record': p.get('record'), 'rank': p.get('rank'), 'teams': p.get('teams'),
        'matchup': {k: r1(v) for k, v in (p.get('matchup') or {}).items()} if p.get('matchup') else None,
        'lineup': {
            'current_total': r1(lu.get('current_total')), 'optimal_total': r1(lu.get('optimal_total')),
            'gain': r1(lu.get('gain')),
            'moves': [{'name': m.get('name'), 'pos': m.get('pos'), 'from': m.get('from'), 'to': m.get('to'),
                       'proj': r1(m.get('proj'))} for m in (lu.get('moves') or [])[:8]],
        },
        'watch': [{'name': f['name'], 'flags': f['flags']} for f in (p.get('flags') or [])[:4]],
        'waivers': [{'add': brief(w['add']), 'drop': brief(w['drop']), 'ros_gain_per_week': r1(w['gain']),
                     'this_week_gain': r1(w.get('week_gain')),
                     'trending_adds': w.get('trending'), 'reason': w.get('reason')} for w in (p.get('waivers') or [])[:3]],
        'waiver_rules': p.get('waiver'),
        'trades': [{'partner': t['partner'], 'send': [brief(x) for x in t['send']],
                    'receive': [brief(x) for x in t['receive']], 'my_delta': r1(t['my_delta']),
                    'their_delta': r1(t['their_delta'])} for t in (p.get('trades') or [])[:2]],
    }


def clean(text):
    text = re.sub(r'\s*—\s*', ', ', text)
    text = re.sub(r'(?<=\d)\s*–\s*(?=\d)', ' to ', text)
    text = re.sub(r'\s*–\s*', ', ', text)
    text = _EMOJI.sub('', text)
    text = re.sub(r'^\s*[#*\-]+\s*', '', text, flags=re.M)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def narrate(payload, timeout=45):
    """Return prose for the payload, or None when not configured / failed."""
    key = _setting('OPENAI_API_KEY')
    if not key:
        return None
    model = _setting('OPENAI_MODEL', DEFAULT_MODEL)
    try:
        r = requests.post(API_URL, timeout=timeout, headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'model': model, 'temperature': 0.5, 'max_tokens': 420,
                'messages': [
                    {'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': 'Facts for this league and week:\n' + json.dumps(_facts(payload))},
                ],
            })
        if r.status_code != 200:
            logger.error(f'openai {model} returned {r.status_code}: {r.text[:200]}')
            return None
        text = ((r.json().get('choices') or [{}])[0].get('message') or {}).get('content') or ''
        text = clean(text)
        return text if len(text) > 40 else None
    except Exception as e:
        logger.error(f'openai narrative failed: {e}')
        return None
