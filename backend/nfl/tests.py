import base64
import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase, Client
from django.utils import timezone

from .models import Athlete, Calendar, DeskUser, Game, GameStatistic, Team


def fake_id_token(claims):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'header.{payload}.signature'


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    @mock.patch('nfl.auth_views.CLIENT_SECRET', 'test-secret')
    @mock.patch('nfl.auth_views.CLIENT_ID', 'test-client')
    def test_login_redirects_to_google_with_state(self):
        resp = self.client.get('/api/auth/login/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('accounts.google.com', resp['Location'])
        self.assertIn('state=', resp['Location'])
        self.assertIn('oauth_state', resp.cookies)

    def test_login_unconfigured_returns_503(self):
        with mock.patch('nfl.auth_views.CLIENT_ID', ''):
            resp = self.client.get('/api/auth/login/')
        self.assertEqual(resp.status_code, 503)

    @mock.patch('nfl.auth_views.requests.post')
    def test_callback_creates_user_and_session(self, post):
        claims = {'sub': 'g-123', 'email': 'fan@example.com',
                  'email_verified': True, 'name': 'A Fan', 'picture': ''}
        post.return_value = mock.Mock(status_code=200,
                                      json=lambda: {'id_token': fake_id_token(claims)})
        self.client.cookies['oauth_state'] = 'abc'
        resp = self.client.get('/api/auth/callback/', {'code': 'x', 'state': 'abc'})
        self.assertEqual(resp.status_code, 302)
        user = DeskUser.objects.get(google_sub='g-123')
        self.assertEqual(user.email, 'fan@example.com')

        me = self.client.get('/api/me/').json()
        self.assertTrue(me['authenticated'])
        self.assertEqual(me['email'], 'fan@example.com')

    @mock.patch('nfl.auth_views.requests.post')
    def test_callback_works_on_console_registered_path(self, post):
        """The Google console registers /auth/callback (no /api, no slash);
        that exact path must resolve."""
        claims = {'sub': 'g-77', 'email': 'path@example.com',
                  'email_verified': True, 'name': 'P'}
        post.return_value = mock.Mock(status_code=200,
                                      json=lambda: {'id_token': fake_id_token(claims)})
        self.client.cookies['oauth_state'] = 's'
        resp = self.client.get('/auth/callback', {'code': 'x', 'state': 's'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DeskUser.objects.filter(google_sub='g-77').exists())

    def test_callback_rejects_bad_state(self):
        self.client.cookies['oauth_state'] = 'abc'
        resp = self.client.get('/api/auth/callback/', {'code': 'x', 'state': 'wrong'})
        self.assertEqual(resp.status_code, 400)

    @mock.patch('nfl.auth_views.requests.post')
    def test_callback_rejects_unverified_email(self, post):
        claims = {'sub': 'g-9', 'email': 'shady@example.com', 'email_verified': False}
        post.return_value = mock.Mock(status_code=200,
                                      json=lambda: {'id_token': fake_id_token(claims)})
        self.client.cookies['oauth_state'] = 's'
        resp = self.client.get('/api/auth/callback/', {'code': 'x', 'state': 's'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(DeskUser.objects.exists())

    def test_me_anonymous(self):
        resp = self.client.get('/api/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['authenticated'])

    def _sign_in(self):
        user = DeskUser.objects.create(google_sub='g-1', email='t@example.com')
        session = self.client.session
        session['desk_user_id'] = user.id
        session.save()
        return user

    def test_me_patch_saves_sleeper_settings(self):
        self._sign_in()
        resp = self.client.patch(
            '/api/me/',
            data=json.dumps({'sleeper_username': '  swayze  ',
                             'settings': {'favorite_team': 22}}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['sleeper_username'], 'swayze')
        self.assertEqual(body['settings']['favorite_team'], 22)
        user = DeskUser.objects.get()
        self.assertEqual(user.sleeper_username, 'swayze')

    def test_me_patch_merges_settings(self):
        user = self._sign_in()
        user.settings = {'a': 1}
        user.save()
        self.client.patch('/api/me/', data=json.dumps({'settings': {'b': 2}}),
                          content_type='application/json')
        user.refresh_from_db()
        self.assertEqual(user.settings, {'a': 1, 'b': 2})

    def test_logout_clears_session(self):
        self._sign_in()
        resp = self.client.get('/api/auth/logout/')
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(self.client.get('/api/me/').json()['authenticated'])


class GamesWindowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.home = Team.objects.create(team_id=1, team_name='Home Club', short_name='HOM')
        self.away = Team.objects.create(team_id=2, team_name='Away Club', short_name='AWY')
        now = timezone.now()
        self.wk_pre = Calendar.objects.create(
            name='HOF', details='This week', week_num=1, season=2026,
            season_type_id=1, season_type_name='Preseason',
            start_date=now - timedelta(days=3), end_date=now + timedelta(days=4))
        self.wk_next = Calendar.objects.create(
            name='Week 2', details='Next week', week_num=2, season=2026,
            season_type_id=1, season_type_name='Preseason',
            start_date=now + timedelta(days=4), end_date=now + timedelta(days=11))

    def _game(self, event_id, when, week):
        return Game.objects.create(
            event_id=event_id, short_name=f'G{event_id}', game_datetime=when,
            season=2026, week_num=week.week_num, season_type_id=week.season_type_id,
            home_team=self.home, away_team=self.away, week=week)

    def test_window_includes_and_groups(self):
        now = timezone.now()
        self._game(100, now - timedelta(hours=30), self.wk_pre)   # too old
        self._game(101, now - timedelta(hours=3), self.wk_pre)    # last 24h
        self._game(102, now + timedelta(days=2), self.wk_pre)     # upcoming
        self._game(103, now + timedelta(days=5), self.wk_next)    # next week
        self._game(104, now + timedelta(days=9), self.wk_next)    # beyond 7d

        body = self.client.get('/api/games/window/').json()
        self.assertEqual(body['total_games'], 3)
        self.assertEqual(len(body['sections']), 2)

        first, second = body['sections']
        self.assertEqual(first['week_name'], 'HOF')
        self.assertEqual(first['season_type_name'], 'Preseason')
        self.assertEqual([g['event_id'] for g in first['games']], [101, 102])
        self.assertEqual(second['week_name'], 'Week 2')
        self.assertEqual([g['event_id'] for g in second['games']], [103])

    def test_window_chronological_across_sections(self):
        now = timezone.now()
        self._game(201, now + timedelta(days=5), self.wk_next)
        self._game(200, now + timedelta(hours=1), self.wk_pre)
        body = self.client.get('/api/games/window/').json()
        self.assertEqual([s['week_name'] for s in body['sections']], ['HOF', 'Week 2'])

    def test_window_empty(self):
        body = self.client.get('/api/games/window/').json()
        self.assertEqual(body['sections'], [])
        self.assertEqual(body['total_games'], 0)


class RosterTests(TestCase):
    """Roster view: current players only, depth ordering, starter flags,
    and season-to-date key stats aggregated from GameStatistic."""

    def setUp(self):
        self.client = Client()
        self.team = Team.objects.create(team_id=8, team_name='Detroit Lions', short_name='DET')
        opp = Team.objects.create(team_id=9, team_name='Green Bay Packers', short_name='GB')
        self.qb1 = Athlete.objects.create(
            athlete_id=1, display_name='Starter QB', position='Quarterback',
            position_abbreviation='QB', team=self.team, status='Active',
            status_id=1, jersey=16, depth_rank=1, depth_slot=9)
        self.qb2 = Athlete.objects.create(
            athlete_id=2, display_name='Backup QB', position='Quarterback',
            position_abbreviation='QB', team=self.team, status='Active',
            status_id=1, jersey=10, depth_rank=2, depth_slot=9)
        self.deep = Athlete.objects.create(
            athlete_id=3, display_name='Camp Arm', position='Quarterback',
            position_abbreviation='QB', team=self.team, status='Practice Squad',
            status_id=29, jersey=19)
        # Boxscore-created historical row: no status, must not appear.
        self.ghost = Athlete.objects.create(
            athlete_id=4, display_name='Ghost Of 2021', team=self.team)
        # Two 2025 regular season games with stats for the starter.
        now = timezone.now()
        for i, event_id in enumerate([9001, 9002]):
            Game.objects.create(
                event_id=event_id, game_datetime=now - timedelta(days=200 + i),
                season=2025, week_num=i + 1, season_type_id=2,
                home_team=self.team, away_team=opp)
            for name, value in [('completions', 20 + i), ('passingAttempts', 30),
                                ('passingYards', 250), ('passingTouchdowns', 2),
                                ('interceptions', 1)]:
                GameStatistic.objects.create(
                    athlete=self.qb1, event_id=str(event_id),
                    category_name='passing', stat_name=name, stat_value=value)

    def test_roster_excludes_statusless_and_orders_by_depth(self):
        body = self.client.get('/api/teams/8/roster/').json()
        names = [p['display_name'] for p in body['roster']]
        self.assertEqual(names, ['Starter QB', 'Backup QB', 'Camp Arm'])
        self.assertNotIn('Ghost Of 2021', names)

    def test_starter_flag_and_key_stats(self):
        body = self.client.get('/api/teams/8/roster/').json()
        starter, backup, deep = body['roster']
        self.assertTrue(starter['starter'])
        self.assertFalse(backup['starter'])
        self.assertIsNone(deep['depth_rank'])
        self.assertEqual(body['stats_season'], 2025)
        self.assertEqual(starter['games_played'], 2)
        stats = {s['label']: s['value'] for s in starter['key_stats']}
        self.assertEqual(stats['CMP/ATT'], '41/60')
        self.assertEqual(stats['YDS'], '500')
        self.assertEqual(stats['TD'], '4')
        self.assertEqual(stats['INT'], '2')
        self.assertEqual(deep['games_played'], 0)
        self.assertEqual({s['label'] for s in deep['key_stats']},
                         {'CMP/ATT', 'YDS', 'TD', 'INT'})

    def test_missing_team_404(self):
        self.assertEqual(self.client.get('/api/teams/77/roster/').status_code, 404)


class RosterIngestTests(TestCase):
    """update_rosters detach logic and depth chart application."""

    def setUp(self):
        self.team = Team.objects.create(team_id=8, team_name='Detroit Lions', short_name='DET')

    def test_apply_depth_chart_ranks_and_skips_returners(self):
        import utils.get_data as get_data
        for aid in (11, 12, 13):
            Athlete.objects.create(athlete_id=aid, team=self.team, status='Active',
                                   position_abbreviation='QB')
        payload = {'items': [
            {'name': '3WR 1TE', 'positions': {
                'qb': {'athletes': [
                    {'rank': 1, 'slot': 9, 'athlete': {'$ref': 'http://x/athletes/11?a=1'}},
                    {'rank': 2, 'slot': 9, 'athlete': {'$ref': 'http://x/athletes/12?a=1'}},
                ]},
            }},
            {'name': 'Special Teams', 'positions': {
                'kr': {'athletes': [
                    {'rank': 1, 'slot': 1, 'athlete': {'$ref': 'http://x/athletes/12?a=1'}},
                ]},
            }},
        ]}
        with mock.patch.object(get_data.session, 'get') as get:
            get.return_value = mock.Mock(json=lambda: payload)
            get_data.apply_depth_chart(8, season=2026)
        self.assertEqual(Athlete.objects.get(athlete_id=11).depth_rank, 1)
        # The kick-return slot must not promote the backup to rank 1.
        self.assertEqual(Athlete.objects.get(athlete_id=12).depth_rank, 2)
        self.assertIsNone(Athlete.objects.get(athlete_id=13).depth_rank)

    def test_apply_depth_chart_never_stamps_other_teams_players(self):
        """A stale chart listing a departed player must not rank him on his
        NEW team (or while detached)."""
        import utils.get_data as get_data
        other = Team.objects.create(team_id=9, team_name='Green Bay Packers',
                                    short_name='GB')
        traded = Athlete.objects.create(athlete_id=55, team=other,
                                        status='Active', depth_rank=2)
        payload = {'items': [{'name': '3WR 1TE', 'positions': {
            'qb': {'athletes': [
                {'rank': 1, 'slot': 9, 'athlete': {'$ref': 'http://x/athletes/55?a=1'}},
            ]},
        }}]}
        with mock.patch.object(get_data.session, 'get') as get:
            get.return_value = mock.Mock(json=lambda: payload)
            get_data.apply_depth_chart(8, season=2026)  # team 8's stale chart
        traded.refresh_from_db()
        self.assertEqual(traded.depth_rank, 2, 'rank on the new team must survive')

    def test_apply_depth_chart_error_payload_raises_and_preserves(self):
        import utils.get_data as get_data
        player = Athlete.objects.create(athlete_id=61, team=self.team,
                                        status='Active', depth_rank=1)
        error = {'error': {'message': 'Depth charts not supported', 'code': 400}}
        with mock.patch.object(get_data.session, 'get') as get:
            get.return_value = mock.Mock(json=lambda: error)
            with self.assertRaises(ValueError):
                get_data.apply_depth_chart(8, season=2028)
        player.refresh_from_db()
        self.assertEqual(player.depth_rank, 1)

    def test_apply_depth_chart_empty_chart_preserves(self):
        import utils.get_data as get_data
        player = Athlete.objects.create(athlete_id=62, team=self.team,
                                        status='Active', depth_rank=1)
        with mock.patch.object(get_data.session, 'get') as get:
            get.return_value = mock.Mock(json=lambda: {'items': []})
            get_data.apply_depth_chart(8, season=2026)
        player.refresh_from_db()
        self.assertEqual(player.depth_rank, 1)

    def test_update_rosters_detaches_departed(self):
        from django.core.management import call_command
        import utils.get_data as get_data
        keeper = Athlete.objects.create(athlete_id=21, team=self.team,
                                        status='Active', depth_rank=1)
        leaver = Athlete.objects.create(athlete_id=22, team=self.team,
                                        status='Active', depth_rank=2)
        with mock.patch('utils.get_data.get_athletes_from_espn', return_value={21}), \
             mock.patch('utils.get_data.apply_depth_chart'):
            call_command('update_rosters')
        leaver.refresh_from_db()
        keeper.refresh_from_db()
        self.assertIsNone(leaver.team)
        self.assertIsNone(leaver.status)
        self.assertIsNone(leaver.depth_rank)
        self.assertEqual(keeper.team, self.team)

    def test_update_rosters_failed_fetch_leaves_team_untouched(self):
        from django.core.management import call_command
        import utils.get_data as get_data
        player = Athlete.objects.create(athlete_id=31, team=self.team, status='Active')
        with mock.patch('utils.get_data.get_athletes_from_espn',
                        side_effect=Exception('espn down')), \
             mock.patch('utils.get_data.apply_depth_chart'):
            call_command('update_rosters')
        player.refresh_from_db()
        self.assertEqual(player.team, self.team)
        self.assertEqual(player.status, 'Active')


class StandingsTests(TestCase):
    def test_standings_groups_divisions_and_sorts(self):
        from utils import get_data

        def entry(abbr, team_id, wins, losses, pct, diff):
            return {
                'team': {'id': str(team_id), 'displayName': abbr, 'abbreviation': abbr},
                'stats': [
                    {'name': 'wins', 'displayValue': str(wins), 'value': wins},
                    {'name': 'losses', 'displayValue': str(losses), 'value': losses},
                    {'name': 'ties', 'displayValue': '0', 'value': 0},
                    {'name': 'winPercent', 'displayValue': f'{pct:.3f}', 'value': pct},
                    {'name': 'differential', 'displayValue': str(diff), 'value': diff},
                ],
            }

        payload = {
            'season': {'year': 2026, 'displayName': '2026'},
            'children': [
                {'name': 'American Football Conference', 'standings': {'entries': [
                    entry('BUF', 2, 1, 0, 1.0, 10),
                    entry('MIA', 15, 0, 1, 0.0, -10),
                    entry('NE', 17, 1, 0, 1.0, 3),
                ]}},
                {'name': 'National Football Conference', 'standings': {'entries': [
                    entry('DET', 8, 1, 0, 1.0, 20),
                ]}},
            ],
        }
        import nfl.live_views as lv
        lv._cache.clear()
        with mock.patch.object(get_data.session, 'get') as get:
            get.return_value = mock.Mock(json=lambda: payload)
            body = self.client.get('/api/standings/').json()
        self.assertEqual(body['season'], 2026)
        afc = body['conferences'][0]
        east = afc['divisions'][0]
        self.assertEqual(east['name'], 'AFC East')
        # BUF over NE on differential at equal pct; MIA last.
        self.assertEqual([t['abbr'] for t in east['teams']], ['BUF', 'NE', 'MIA'])
        nfc_north = body['conferences'][1]['divisions'][1]
        self.assertEqual(nfc_north['name'], 'NFC North')
        self.assertEqual([t['abbr'] for t in nfc_north['teams']], ['DET'])

    def test_standings_upstream_failure_502(self):
        from utils import get_data
        import nfl.live_views as lv
        lv._cache.clear()
        with mock.patch.object(get_data.session, 'get',
                               side_effect=Exception('espn down')):
            resp = self.client.get('/api/standings/')
        self.assertEqual(resp.status_code, 502)
