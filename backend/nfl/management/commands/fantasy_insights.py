"""Build the Week Room reports.

    manage.py fantasy_insights --username tswayze        # one Sleeper handle
    manage.py fantasy_insights --all                      # every known handle
    manage.py fantasy_insights --username x --no-llm      # template prose only
"""
import logging

from django.core.management.base import BaseCommand

from nfl import fantasy_insights as fi
from nfl.models import DeskUser, FantasyInsight

logger = logging.getLogger(__name__)
MAX_USERS = 25


class Command(BaseCommand):
    help = 'Generate and store Week Room insights for Sleeper users'

    def add_arguments(self, parser):
        parser.add_argument('--username', action='append', default=[])
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--no-llm', action='store_true')
        parser.add_argument('--drafted', action='store_true',
                            help='only leagues that drafted since their note was printed')

    def handle(self, *args, **opts):
        if opts['drafted']:
            done = fi.refresh_newly_drafted(use_llm=not opts['no_llm'])
            if not done:
                self.stdout.write('draft watch: nothing newly drafted')
            for name, ids in done.items():
                self.stdout.write(f'draft watch: {name}: wrote notes for {", ".join(ids)}')
            return
        names = list(opts['username'])
        if opts['all']:
            names += [u for u in DeskUser.objects.exclude(sleeper_username='')
                      .values_list('sleeper_username', flat=True)]
            names += [u for u in FantasyInsight.objects.values_list('username', flat=True).distinct()]
        seen, todo = set(), []
        for n in names:
            key = n.strip().lower()
            if key and key not in seen:
                seen.add(key); todo.append(n.strip())
        if not todo:
            self.stdout.write('no usernames to refresh')
            return
        for name in todo[:MAX_USERS]:
            try:
                out = fi.generate_for_user(name, use_llm=not opts['no_llm'])
            except Exception as e:
                self.stderr.write(f'{name}: FAILED {e}')
                continue
            for p in out:
                lu = p.get('lineup') or {}
                self.stdout.write(
                    f"{name} / {p.get('name')}: wk {p.get('week')} {p.get('status')} "
                    f"gain {lu.get('gain')} waivers {len(p.get('waivers') or [])} "
                    f"trades {len(p.get('trades') or [])} prose={p.get('narrative_source')}")
