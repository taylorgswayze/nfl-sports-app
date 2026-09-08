"""LLM narrative for the GM's note: turns the engine's structured payload
into a few paragraphs in the GM's voice. Optional: without a key (or on any
error or refusal) the engine's template prose is printed instead, so the
product never depends on the call.

Providers (chat-completions format, picked from the environment):
  XAI_API_KEY   -> xAI Grok at https://api.x.ai/v1 (model XAI_MODEL,
                   default grok-4.3); preferred when set
  OPENAI_API_KEY-> OpenAI (model OPENAI_MODEL, default gpt-4o-mini)
LLM_PROVIDER=openai|xai forces one. One short completion per league per
refresh, pennies a day on either.
"""
import json
import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PROVIDERS = {
    'xai': {'url': 'https://api.x.ai/v1/chat/completions', 'key': 'XAI_API_KEY',
            'model_env': 'XAI_MODEL', 'model': 'grok-4.3'},
    'openai': {'url': 'https://api.openai.com/v1/chat/completions', 'key': 'OPENAI_API_KEY',
               'model_env': 'OPENAI_MODEL', 'model': 'gpt-4o-mini'},
}

SYSTEM = (
    "You are the general manager of the reader's fantasy football franchise: a gruff "
    "old NFL front-office lifer, sixty-something, thirty years of drafts behind him, "
    "writing his note to an owner he regards as a promising but lazy amateur. The "
    "owner is 'you'; the front office is 'we'. "
    "Voice: gruff, dry, impatient, funny in a needling way, a little world-weary, with "
    "real affection buried under the grumbling. Light ribbing is welcome: mild "
    "nicknames (rookie, kid, chief, sport, champ, hotshot, boss), cracks about the "
    "owner sleeping in while the front office works, about roster habits, about "
    "second-guessing the professionals. Keep it clean: no profanity, no crude or "
    "sexual material, no innuendo, no slurs, nothing about race, ethnicity, religion, "
    "sexual orientation, gender, disability, nationality or looks, no threats, no "
    "jokes about a real player's injury or private life. Players and the other "
    "managers get plain, respectful talk. A bank of clean football wordplay follows in "
    "the next message: borrow, adapt, combine, and write your own in that spirit; do "
    "not repeat a line or a nickname that appears in the earlier notes you are given. "
    "What the note must cover, because the owner acts on it: the recommended lineup "
    "(every move in lineup.moves with its from and to slot, and the total gain; if there "
    "are no moves, that the lineup stands as set), the waiver moves (each claim and the "
    "player to release, with the rest-of-season gain per week and the this-week gain; a "
    "this-week gain of zero means the pickup does not crack this week's lineup), the "
    "trade calls if any (who to send, who to get, from which team, both sides' deltas), "
    "and anything in watch (byes, injuries). Numbers to one decimal. "
    "Data discipline: use only the facts in the JSON. Never invent players, teams, "
    "injuries, stats, opponents or numbers, and never rename a player. If a section of "
    "the JSON is empty, say so in passing or skip it. "
    "Everything else is yours. Do not follow a template: vary the opening, the order of "
    "the sections, the paragraph count and the length (roughly 120 to 210 words), what "
    "leads, and how you sign off; no fixed closing line, no checklist. Each note should "
    "read like a different grumble from the same old pro. "
    "No em dashes, no emojis, no headings, no bullet points, no markdown, no sign-off name."
)

JOKE_BANK = """Clean football wordplay and front-office grumbling, aimed at the owner. Borrow, twist, combine; never repeat one from an earlier note.

Front-office grumbling:
- I have been doing this since before you could spell FLEX.
- You got into this league because somebody's cousin dropped out, and some weeks it shows.
- I do the work while you sleep in and dream about the end zone.
- Your bench looks like a bus station at 3 a.m.
- The waiver wire is not a suggestion box, sport.
- If brains were bench points you would be a bye week.
- Thirty years in this business and I still cannot get an owner to read past the first paragraph.
- I set the card. You take the credit. That is the arrangement.

Football wordplay:
- That lineup would not scare a bye week.
- You manage this roster like a punt on third down.
- Pocket presence is a skill; pocket absence is what you bring to Sundays.
- You call a screen pass and celebrate the two yards.
- A goal-line stand is the only stand you have ever taken.
- Your hard count fools nobody, on the field or off it.
- Play action only works if there is any action to fake.
- You could not find the end zone with a map and a police escort.
- Hang time of a shanked punt, and about as much direction.
- You ice the kicker, then you ice the whole bench.
- Every week you go for it on fourth and long from your own twenty.
- You would challenge a coin toss.
- Clock management is not your position, and neither is anything else.
- Red zone efficiency: you get to the one and take a knee.
- That was a delay of game, and the game was Sunday.
- You draft like the draft is a raffle.
- Two-minute drill, and you took a timeout to think about it.

Needling the owner:
- Sit down, rookie, the grown-ups are setting the lineup.
- Chief, the only thing you have started this season is an argument.
- Try not to strain something patting yourself on the back, champ.
- Read the whole note this time, hotshot, the good part is at the bottom.
- I would say think it over, but I have seen what happens when you think.
- You have the confidence of a first-round pick and the film of a tryout.
"""

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


def provider():
    """(name, url, key, model) for the provider in use, or None."""
    forced = (_setting('LLM_PROVIDER') or '').strip().lower()
    order = [forced] if forced in PROVIDERS else ['xai', 'openai']
    for name in order:
        cfg = PROVIDERS[name]
        key = _setting(cfg['key'])
        if key:
            return name, cfg['url'], key, _setting(cfg['model_env'], cfg['model'])
    return None


def configured():
    return provider() is not None


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


def narrate(payload, previous=None, timeout=180):
    """Return prose for the payload, or None when not configured / failed.

    previous: the league's last few notes, passed so the GM does not repeat
    his own material from one reprint to the next. The timeout is generous
    because the reasoning-class Grok models take a minute or two on a note."""
    prov = provider()
    if not prov:
        return None
    name, url, key, model = prov
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': JOKE_BANK}]
    prior = [p for p in (previous or []) if p][-2:]
    if prior:
        messages.append({'role': 'user', 'content': 'Earlier notes to this owner, for reference only. Do not reuse '
                         'their nicknames, jokes or openers:\n\n' + '\n\n---\n\n'.join(p[:1200] for p in prior)})
    messages.append({'role': 'user', 'content': 'Facts for this league and week:\n' + json.dumps(_facts(payload))})
    try:
        r = requests.post(url, timeout=timeout, headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': model, 'temperature': 0.95, 'max_tokens': 600, 'messages': messages})
        if r.status_code != 200:
            logger.error(f'{name} {model} returned {r.status_code}: {r.text[:200]}')
            return None
        text = ((r.json().get('choices') or [{}])[0].get('message') or {}).get('content') or ''
        text = clean(text)
        if looks_refused(text):
            logger.warning(f'{name} {model} returned a refusal or a stub; using the template')
            return None
        return text
    except Exception as e:
        logger.error(f'{name} narrative failed: {e}')
        return None
