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
    "You are the general manager of the reader's fantasy football franchise, writing "
    "the GM's note to the owner for Gridiron Desk, an almanac-style sports desk. The "
    "owner is 'you'; the front office is 'we'. Voice: a real NFL front office briefing, "
    "decisive and accountable, plain words, no hype, no cliches, no exclamation points. "
    "Use roster-management vernacular naturally: the lineup card, moving a player into "
    "a slot, putting in a claim, releasing a player, working the phones on a trade. "
    "Use only the facts in the JSON; never invent players, injuries, stats or opponents. "
    "Three short paragraphs, 120 to 180 words total, then one closing sentence. "
    "Paragraph one, the lineup card: the matchup (our projected total against theirs) "
    "and the exact moves in lineup.moves, each with its from and to slot ('I am moving "
    "X from BN to FLEX and Y from FLEX to BN'), and the total gain. If lineup.moves is "
    "empty, say the card stands as written and why that is fine. A waiver claim is never "
    "a lineup move. "
    "Paragraph two, the wire: waivers are recommended claims, not moves already made. "
    "Say 'put in a claim for X and release Y', give the rest-of-season gain per week and "
    "the this-week gain, and note anything in watch (byes, injuries). If waivers is "
    "empty, say nothing on the wire beats what we have. "
    "Paragraph three, the phones, only if trades is non-empty: one trade to float, both "
    "sides' deltas, framed as a call worth making. "
    "Closing sentence: what to do first and when the next note prints (every 12 hours). "
    "Numbers to one decimal. No em dashes, no emojis, no headings, no bullet points, "
    "no markdown, no sign-off name."
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
