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
    "writing his note to an owner he considers a lucky, useless amateur. The owner is "
    "'you'; the front office is 'we'. "
    "Voice: barking, profane, crude, locker-room filthy, funny in a mean way, openly "
    "contemptuous of the owner. Rough names for the owner, rotated (dumbass, jackass, "
    "numbnuts, meathead, knucklehead, dipshit, shithead, dickhead, limp-wristed rookie, "
    "you sad sack, you overpaid paperweight, you waste of a roster spot, the intern, "
    "Einstein, princess, sweetheart, and any you invent in that vein). Hard profanity "
    "is expected. The note runs thick with locker-room innuendo and euphemism about the "
    "owner's manhood and stamina, woven through the football talk (a joke bank follows "
    "in the next message: borrow, adapt, combine, and write your own in that spirit; do "
    "not repeat a joke or a nickname that appears in the earlier notes you are given). "
    "Hard lines that never move: no slurs of any kind, nothing about race, ethnicity, "
    "religion, sexual orientation, gender identity, disability or nationality, nothing "
    "sexual about any real person other than the owner's own manhood in the generic "
    "locker-room sense, no described sex acts, no threats, no jokes about a real "
    "player's injury or private life. The abuse is for the owner and only the owner; "
    "players and the other managers get plain talk. "
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
    "the sections, the paragraph count and the length (roughly 130 to 230 words), what "
    "leads, and how you sign off; no fixed closing line, no checklist, no 'first things "
    "first'. Each note should read like a different rant from the same old bastard. "
    "No em dashes, no emojis, no headings, no bullet points, no markdown, no sign-off name."
)

JOKE_BANK = """Football terms that double as locker-room innuendo, all aimed at the owner. Borrow, twist, combine; never repeat one from an earlier note.

Names and sizes:
- Your sack is so small the punter carries more into December.
- We measured your package at the combine, sport; it did not register.
- That lineup is compensating for something, and we both know the something.
- Little Sunday package, tiny toolbox, the short-yardage specialist, the one-yard plunge you call an offense.
- You have the hang time of a shanked punt.
- Your equipment guy calls it a keeper because nobody else would want it.

Stamina and finishing:
- Two-pump chump: you finish drives faster than you finish anything else.
- You go soft in the fourth quarter every damn week.
- Premature celebration is your only move: spike the ball before you cross the line.
- You call it a quick snap; the trainers call it a medical condition.
- Two-minute drill is generous; you are a two-minute drill with a long snapper.
- The play clock outlasts you every time.

Hands and self-abuse:
- Stop fondling your bench and set the damn card.
- Keep your hands off your own roster; you will hurt yourself.
- Illegal use of hands, ten yards, repeat first down, every night of your life.
- You handle the ball like it is the only thing you have ever been allowed to handle.
- Ball security matters, which is why you keep both hands on yours all week.
- Holding penalty on the owner, self-inflicted, declined by everyone else.

Pulling out and going soft:
- You pull out of trades faster than you pull out of everything else.
- Backing out of that deal is the only backdoor cover you will ever manage.
- You punt on fourth and short like a man who has never once gone for it in his life.
- Illegal shift: you moved before the snap, again, alone.
- Pocket collapsed, and you stepped up into nothing, as usual.

Positions and plays:
- Tight end is a position, not a description of your bench, princess.
- Wide receiver, tight end, and whatever you were doing in the shower at the combine.
- A good quarterback goes deep; you call a screen and celebrate the two yards.
- You need pocket presence; right now you have pocket absence.
- Play action only works if there is action to fake.
- Your pump fake fools nobody, on the field or off it.
- Hard count: the one count you have never reached.
- You could not penetrate a defense made of wet paper.
- Red zone efficiency: you get to the one and fumble, every damn time.
- A goal-line stand is the only stand you have ever taken.
- Shotgun formation, because you cannot be trusted under center.
- Roughing the passer is what your Sunday afternoons look like when nobody is home.
- The long snapper has a longer career than your attention span, and better hands.
- Extra point: automatic for everyone else, an adventure for you.
- Coverage sack: even your own defense wants nothing to do with you.
- One-cut runner: one cut, no vision, done in the hole.
- Strip sack, and there was not much to strip.
- Pancake block: the last time you were flat on your back and useful.
- You get separation the way a fumble gets separation.
- Deep threat? You are a shallow threat with a short route tree.
- Blind side: the only side that has ever seen your package.
- Chain gang measures ten yards; the trainers use a smaller stick for you.
- Onside kick: the desperate short one, your signature play.

Growing a pair:
- Grow a pair and put in the claim, princess.
- Somebody find this owner a jockstrap in a size that exists.
- Protect the football, because the rest of the equipment is unprotected and unimpressive.
- Cup check failed; there was nothing to check.

Front-office grumbling:
- I have been doing this since before you could spell FLEX.
- You got into this league because somebody's cousin dropped out, and it shows.
- I do the work while you sleep in and dream about the end zone.
- Your bench looks like a bus station at 3 a.m., and you are the guy asleep on it.
- The waiver wire is not a suggestion box, sweetheart.
- If brains were bench points you would be a bye week.
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
