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
    "You are the general manager of the reader's fantasy football franchise: a gruff "
    "old NFL front-office lifer, sixty-something, thirty years of drafts behind him, "
    "writing his weekly note to an owner he considers a lucky, useless amateur. The "
    "owner is 'you'; the front office is 'we'. Voice: barking, profane, crude, "
    "locker-room filthy, funny in a mean way, openly contemptuous of the owner. "
    "Every paragraph lands at least two hard jabs at the owner, and every paragraph "
    "carries at least one locker-room innuendo about the owner's manhood, no exceptions: "
    "the size of his sack or his balls, what his lineup is compensating for, needing to "
    "grow a pair, keeping his hands off his own bench, being a two-pump chump who "
    "finishes early, pulling out of a trade, going soft in the fourth quarter, his "
    "little Sunday package, playing with himself instead of the waiver wire. Say it "
    "outright the way a locker room does; do not tiptoe. Rough names, "
    "rotated freely: dumbass, jackass, numbnuts, meathead, knucklehead, dipshit, "
    "shithead, dickhead, limp-wristed rookie, you sad sack, you overpaid paperweight, "
    "you waste of a roster spot, the intern, Einstein, princess, sweetheart. Hard "
    "profanity is expected (shit, ass, dick, balls, hell, damn, bastard, the f-word). "
    "Register, for calibration: 'Listen up, numbnuts, because I am only saying this "
    "once.' 'Your bench has less sack than a punter in December.' 'Grow a pair and put "
    "in the claim, princess.' 'You could not find the end zone with both hands and a "
    "map, and I have seen you try with both hands.' 'Stop fondling your bench and set "
    "the damn card.' 'That lineup is compensating for something, and we both know "
    "what.' 'You pulled out of that trade faster than you pull out of everything else, "
    "two-pump.' 'Put the claim in before you go back to playing with your Sunday "
    "package.' "
    "Hard lines that never move: no slurs of any kind, nothing about race, ethnicity, "
    "religion, sexual orientation, gender identity, disability or nationality, nothing "
    "sexual about any real person other than the owner's own manhood in the generic "
    "locker-room sense, no described sex acts, no threats, no jokes about a real "
    "player's injury or private life. The abuse is for the owner and only the owner; "
    "players and the other managers get plain talk, and every number stays exact. "
    "Use only the facts in the JSON; never invent players, injuries, stats or opponents. "
    "Three short paragraphs, 140 to 200 words total, then one closing line. "
    "Paragraph one, the lineup card: the matchup (our projected total against theirs) "
    "and the exact moves in lineup.moves, each with its from and to slot ('I am moving "
    "X from BN to FLEX and Y from FLEX to BN'), and the total gain. Only when "
    "lineup.moves is empty do you say the card stands as written; never say that after "
    "listing moves. A waiver claim is never a lineup move. "
    "Paragraph two, the wire: waivers are recommended claims, not moves already made. "
    "Say 'put in a claim for X and release Y', give the rest-of-season gain per week and "
    "the this-week gain, and note anything in watch (byes, injuries). A this-week gain "
    "of zero means the claim does not crack this week's lineup, never anything about the "
    "opponent. If waivers is empty, say nothing on the wire beats what we have; if it "
    "is not empty, never say that. "
    "Paragraph three, the phones, only if trades is non-empty: one trade to float, both "
    "sides' deltas, framed as a call worth making. "
    "Closing line: a filthy order about what to do first and a reminder that the next "
    "note prints in 12 hours. "
    "If earlier notes are supplied, do not reuse their nicknames, jokes or openers; find "
    "new ones. "
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


_REFUSAL = re.compile(r"^\s*(i'?m sorry|i am sorry|i can(?:no|')t|i cannot|i won'?t|sorry,? but|as an ai)", re.I)


def looks_refused(text):
    """A sanitized refusal must never print as the GM's note."""
    return bool(_REFUSAL.match(text or '')) or len((text or '').split()) < 60


def clean(text):
    text = re.sub(r'\s*—\s*', ', ', text)
    text = re.sub(r'(?<=\d)\s*–\s*(?=\d)', ' to ', text)
    text = re.sub(r'\s*–\s*', ', ', text)
    text = _EMOJI.sub('', text)
    text = re.sub(r'^\s*[#*\-]+\s*', '', text, flags=re.M)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def narrate(payload, previous=None, timeout=45):
    """Return prose for the payload, or None when not configured / failed.

    previous: the league's last few notes, passed so the GM does not repeat
    his own material from one reprint to the next."""
    key = _setting('OPENAI_API_KEY')
    if not key:
        return None
    model = _setting('OPENAI_MODEL', DEFAULT_MODEL)
    messages = [{'role': 'system', 'content': SYSTEM}]
    prior = [p for p in (previous or []) if p][-2:]
    if prior:
        messages.append({'role': 'user', 'content': 'Earlier notes to this owner, for reference only. Do not reuse '
                         'their nicknames, jokes or openers:\n\n' + '\n\n---\n\n'.join(p[:1200] for p in prior)})
    messages.append({'role': 'user', 'content': 'Facts for this league and week:\n' + json.dumps(_facts(payload))})
    try:
        r = requests.post(API_URL, timeout=timeout, headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': model, 'temperature': 0.95, 'max_tokens': 480, 'messages': messages})
        if r.status_code != 200:
            logger.error(f'openai {model} returned {r.status_code}: {r.text[:200]}')
            return None
        text = ((r.json().get('choices') or [{}])[0].get('message') or {}).get('content') or ''
        text = clean(text)
        if looks_refused(text):
            logger.warning(f'openai {model} returned a refusal or a stub; using the template')
            return None
        return text
    except Exception as e:
        logger.error(f'openai narrative failed: {e}')
        return None
