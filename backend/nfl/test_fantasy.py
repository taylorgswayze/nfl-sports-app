"""Week Room engine and API tests. Pure-engine cases need no network; the
view test stubs the Sleeper lookups and the background generator."""
import json
from unittest import mock

from django.test import TestCase, Client
from django.utils import timezone

from nfl import fantasy_engine as fe
from nfl import fantasy_insights as fi
from nfl.models import FantasyInsight
from utils import llm

SLOTS = ['QB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'SUPER_FLEX', 'K', 'DEF']
SETTINGS = {'pass_yd': 0.04, 'pass_td': 4, 'pass_int': -1, 'rush_yd': 0.1, 'rush_td': 6,
            'rec': 1, 'rec_yd': 0.1, 'rec_td': 6, 'fum_lost': -2, 'bonus_rec_te': 0.5}


def V(pid, pos, proj, ros=None, **kw):
    row = {'player_id': pid, 'name': pid.upper(), 'pos': pos, 'positions': [pos], 'team': 'DAL',
           'proj': proj, 'proj_raw': proj, 'ros': proj if ros is None else ros, 'injury': None,
           'has_game': True, 'locked': False, 'opp': 'NYG', 'flags': []}
    row.update(kw)
    return row


class ScoringTests(TestCase):
    def test_league_scoring_is_sleepers_arithmetic(self):
        stats = {'pass_yd': 250, 'pass_td': 2, 'pass_int': 1, 'rush_yd': 30, 'rec': 4,
                 'rec_yd': 40, 'bonus_rec_te': 4, 'gp': 1, 'pts_ppr': 99}
        self.assertAlmostEqual(fe.score(stats, SETTINGS), 10 + 8 - 1 + 3 + 4 + 4 + 2)

    def test_missing_and_zero_keys_are_ignored(self):
        self.assertEqual(fe.score({}, SETTINGS), 0.0)
        self.assertEqual(fe.score({'pts_allow': 21}, SETTINGS), 0.0)


class LineupTests(TestCase):
    def test_superflex_takes_second_qb_over_rb(self):
        cands = [('q1', ['QB'], 20), ('q2', ['QB'], 18), ('r1', ['RB'], 15), ('r2', ['RB'], 14),
                 ('w1', ['WR'], 12), ('w2', ['WR'], 11), ('w3', ['WR'], 10), ('t1', ['TE'], 8),
                 ('k1', ['K'], 7), ('d1', ['DEF'], 6)]
        total, asg = fe.optimal_lineup(SLOTS, cands)
        named = {SLOTS[i]: p for i, p in asg.items()}
        self.assertEqual({named['QB'], named['SUPER_FLEX']}, {'q1', 'q2'})
        self.assertEqual({named['RB'], named['FLEX']}, {'r1', 'r2'})
        self.assertAlmostEqual(total, 20 + 18 + 15 + 14 + 12 + 11 + 8 + 7 + 6)

    def test_fixed_slots_are_respected(self):
        cands = [('q1', ['QB'], 20), ('q2', ['QB'], 18), ('r1', ['RB'], 15)]
        total, asg = fe.optimal_lineup(['QB', 'SUPER_FLEX', 'RB'], cands, fixed={0: ('q2', 18)})
        self.assertEqual(asg[0], 'q2')
        self.assertEqual(asg[1], 'q1')
        self.assertAlmostEqual(total, 53)

    def test_multi_position_player_fills_the_best_slot(self):
        cands = [('x', ['RB', 'WR'], 9), ('w', ['WR'], 8), ('r', ['RB'], 5)]
        _t, asg = fe.optimal_lineup(['RB', 'WR'], cands)
        self.assertEqual({asg[0], asg[1]}, {'x', 'w'})

    def test_lineup_report_swaps_and_respects_locks(self):
        values = {
            'q1': V('q1', 'QB', 20), 'r1': V('r1', 'RB', 15), 'r2': V('r2', 'RB', 9),
            'r3': V('r3', 'RB', 14), 'w1': V('w1', 'WR', 12), 'w2': V('w2', 'WR', 11),
            'w3': V('w3', 'WR', 4, flags=['bye'], has_game=False, proj_raw=12),
            't1': V('t1', 'TE', 8), 'k1': V('k1', 'K', 7), 'd1': V('d1', 'DEF', 6),
            'q2': V('q2', 'QB', 17, locked=True),
        }
        roster = list(values)
        starters = ['q1', 'r1', 'w1', 'w3', 't1', 'r2', 'q2', 'k1', 'd1']
        rep = fe.lineup_report(SLOTS, roster, starters, values)
        self.assertTrue(rep['material'])
        started = {c['start']['player_id'] for c in rep['changes'] if c['start']}
        sat = {c['sit']['player_id'] for c in rep['changes'] if c['sit']}
        self.assertEqual(started, {'w2', 'r3'})
        self.assertEqual(sat, {'w3', 'r2'})
        self.assertIn('q2', rep['starting'])  # locked starter kept
        self.assertAlmostEqual(rep['gain'], (11 - 4) + (14 - 9))
        # explicit moves: two in, two out, everyone else stays seated
        moves = {m['player_id']: (m['from'], m['to']) for m in rep['moves']}
        self.assertEqual(moves['w2'], ('BN', 'WR'))
        self.assertEqual(moves['r3'], ('BN', 'FLEX'))
        self.assertEqual(moves['w3'], ('WR', 'BN'))
        self.assertEqual(moves['r2'], ('FLEX', 'BN'))
        self.assertEqual(len(rep['moves']), 4)
        self.assertEqual([m['to'] for m in rep['moves']][:2], ['WR', 'FLEX'])  # into the lineup first

    def test_equal_players_are_not_shuffled_between_slots(self):
        values = {'r1': V('r1', 'RB', 12), 'r2': V('r2', 'RB', 12), 'w1': V('w1', 'WR', 9), 'x': V('x', 'WR', 15)}
        rep = fe.lineup_report(['RB', 'FLEX', 'WR'], list(values), ['r2', 'r1', 'w1'], values)
        self.assertTrue(rep['material'])
        self.assertEqual([(m['player_id'], m['from'], m['to']) for m in rep['moves']],
                         [('x', 'BN', 'WR'), ('w1', 'WR', 'BN')])

    def test_tie_prints_the_current_lineup(self):
        values = {'q1': V('q1', 'QB', 20), 'q2': V('q2', 'QB', 19.98)}
        rep = fe.lineup_report(['QB'], ['q1', 'q2'], ['q2'], values)
        self.assertFalse(rep['material'])
        self.assertEqual(rep['changes'], [])
        self.assertEqual(rep['moves'], [])
        self.assertEqual(rep['starting'], ['q2'])

    def test_small_real_gain_is_still_printed(self):
        values = {'q1': V('q1', 'QB', 20), 'q2': V('q2', 'QB', 19.5)}
        rep = fe.lineup_report(['QB'], ['q1', 'q2'], ['q2'], values)
        self.assertTrue(rep['material'])
        self.assertEqual([(m['player_id'], m['to']) for m in rep['moves']], [('q1', 'QB'), ('q2', 'BN')])

    def test_reserve_players_cannot_start(self):
        values = {'q1': V('q1', 'QB', 20), 'q2': V('q2', 'QB', 10)}
        rep = fe.lineup_report(['QB'], ['q1', 'q2'], ['q2'], values, reserve=['q1'])
        self.assertEqual(rep['starting'], ['q2'])


class ProjectionTests(TestCase):
    def _ctx(self, prior=None, game=True):
        return {
            'players': {'p': {'name': 'P', 'pos': 'WR', 'positions': ['WR'], 'team': 'DAL', 'injury': None}},
            'proj': {'p': {'stats': {'rec': 5, 'rec_yd': 60}, 'pos': 'WR', 'team': 'DAL', 'opp': 'NYG'}},
            'prior': prior or {},
            'factor': lambda pid, pos: 1.0,
            'trailing': lambda pid: None,
            'season_ppg': lambda pid, s: None,
            'team_game': lambda team: {'has_game': game, 'started': False, 'final': False},
        }

    def test_blend_uses_capped_prior_weight_at_week_one(self):
        vals = fe.player_values(['p'], self._ctx(prior={'p': {'ppg': 21.0}}), SETTINGS, week=1)
        # weekly = 5 + 6 = 11; prior 21 at weight 0.30
        self.assertAlmostEqual(vals['p']['proj'], 0.7 * 11 + 0.3 * 21, places=2)
        self.assertAlmostEqual(fe.prior_weight(17), 3 / 19, places=3)

    def test_bye_zeroes_the_week_but_not_the_season_value(self):
        vals = fe.player_values(['p'], self._ctx(prior={'p': {'ppg': 21.0}}, game=False), SETTINGS, week=5)
        self.assertEqual(vals['p']['proj'], 0.0)
        self.assertIn('bye', vals['p']['flags'])
        self.assertGreater(vals['p']['ros'], 15)

    def test_out_players_project_zero(self):
        ctx = self._ctx()
        ctx['players']['p']['injury'] = 'Out'
        vals = fe.player_values(['p'], ctx, SETTINGS, week=3)
        self.assertEqual(vals['p']['proj'], 0.0)
        self.assertIn('out', vals['p']['flags'])


class WaiverAndTradeTests(TestCase):
    def setUp(self):
        self.values = {
            'q1': V('q1', 'QB', 20), 'r1': V('r1', 'RB', 15), 'r2': V('r2', 'RB', 12),
            'w1': V('w1', 'WR', 12), 'w2': V('w2', 'WR', 11), 'w3': V('w3', 'WR', 3),
            't1': V('t1', 'TE', 8), 'k1': V('k1', 'K', 7), 'd1': V('d1', 'DEF', 6), 'd2': V('d2', 'DEF', 5),
            'q2': V('q2', 'QB', 17),
        }
        self.roster = list(self.values)

    def test_waiver_names_cheapest_drop_and_never_this_weeks_starter(self):
        fa = {'fa1': V('fa1', 'WR', 14, team='MIA')}
        lines = fe.waiver_report(SLOTS, self.roster, self.values, ['fa1'], fa,
                                 protected=['d1'])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['add']['player_id'], 'fa1')
        self.assertEqual(lines[0]['drop']['player_id'], 'd2')  # benched DEF costs nothing
        self.assertTrue(lines[0]['starts'])
        self.assertGreater(lines[0]['gain'], fe.WAIVER_FLOOR)
        self.assertAlmostEqual(lines[0]['week_gain'], 14 - 11)  # fa1 replaces w2 in this week's lineup

    def test_weak_free_agent_is_not_a_claim(self):
        fa = {'fa1': V('fa1', 'WR', 2, team='MIA')}
        self.assertEqual(fe.waiver_report(SLOTS, self.roster, self.values, ['fa1'], fa), [])

    def test_drop_candidates_are_bench_only(self):
        drops = fe.drop_candidates(SLOTS, self.roster, self.values, protected=['d1'])
        ids = [d['player_id'] for d in drops]
        self.assertIn('w3', ids)
        self.assertNotIn('q1', ids)
        self.assertNotIn('d1', ids)

    def test_trade_requires_both_sides_to_hold_value(self):
        partner_vals = dict(self.values)
        partner_vals.update({'pw': V('pw', 'WR', 16), 'pr': V('pr', 'RB', 6), 'pq': V('pq', 'QB', 15),
                             'pt': V('pt', 'TE', 7), 'pk': V('pk', 'K', 6), 'pd': V('pd', 'DEF', 5),
                             'pw2': V('pw2', 'WR', 10), 'pw3': V('pw3', 'WR', 9)})
        partners = [{'name': 'Them', 'pids': ['pw', 'pr', 'pq', 'pt', 'pk', 'pd', 'pw2', 'pw3'], 'values': partner_vals}]
        ideas = fe.trade_report(SLOTS, self.roster, self.values, partners)
        for t in ideas:
            self.assertGreaterEqual(t['my_delta'], fe.TRADE_FLOOR)
            self.assertGreaterEqual(t['their_delta'], -0.25)


class ProseTests(TestCase):
    def test_template_has_no_em_dashes_and_names_the_moves(self):
        payload = {
            'name': 'L', 'week': 3, 'status': 'in_season',
            'matchup': {'opp_name': 'Foes', 'my_total': 101.2, 'opp_total': 98.4},
            'lineup': {'gain': 4.4, 'material': True, 'changes': [], 'moves': [
                {'name': 'A', 'pos': 'RB', 'from': 'BN', 'to': 'FLEX', 'proj': 14.0},
                {'name': 'B', 'pos': 'RB', 'from': 'FLEX', 'to': 'BN', 'proj': 9.6}]},
            'waivers': [{'add': {'name': 'C', 'pos': 'WR', 'team': 'MIA'}, 'drop': {'name': 'D'}, 'gain': 2.1,
                         'week_gain': 1.2}],
            'trades': [], 'flags': [],
        }
        text = fe.template_narrative(payload)
        self.assertNotIn('—', text)
        for name in ('Foes', 'A from BN to FLEX', 'B from FLEX to BN', 'C', 'D'):
            self.assertIn(name, text)

    def test_llm_clean_strips_dashes_and_emoji(self):
        self.assertEqual(llm.clean('Start A — sit B 🏈'), 'Start A, sit B')
        self.assertEqual(llm.clean('weeks 10–12'), 'weeks 10 to 12')

    def test_llm_without_key_returns_none(self):
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': '', 'XAI_API_KEY': '', 'LLM_PROVIDER': ''}), \
                mock.patch.object(llm, '_dotenv', return_value=None):
            self.assertIsNone(llm.narrate({}))
            self.assertFalse(llm.configured())

    def test_xai_key_is_preferred_and_forcing_works(self):
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': 'o', 'XAI_API_KEY': 'x', 'XAI_MODEL': 'grok-4.6', 'LLM_PROVIDER': ''}), \
                mock.patch.object(llm, '_dotenv', return_value=None):
            name, url, key, model = llm.provider()
            self.assertEqual((name, model), ('xai', 'grok-4.6'))
            self.assertIn('api.x.ai', url)
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': 'o', 'XAI_API_KEY': 'x', 'LLM_PROVIDER': 'openai'}), \
                mock.patch.object(llm, '_dotenv', return_value=None):
            self.assertEqual(llm.provider()[0], 'openai')


def sign_in(client):
    from nfl.models import DeskUser
    u, _ = DeskUser.objects.get_or_create(google_sub='sub-test', defaults={'email': 't@example.com', 'name': 'T'})
    session = client.session
    session['desk_user_id'] = u.id
    session.save()
    return u


class InsightsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        sign_in(self.client)

    def test_requires_username(self):
        r = self.client.get('/api/fantasy/insights/')
        self.assertEqual(r.status_code, 400)

    @mock.patch('nfl.fantasy_insights.generate_in_background', return_value=True)
    @mock.patch('nfl.fantasy_views.sleeper.user', return_value={'user_id': 'u1'})
    def test_first_sight_starts_generation(self, _user, gen):
        r = self.client.get('/api/fantasy/insights/?username=someone')
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertEqual(body['status'], 'generating')
        self.assertTrue(body['generating'])
        gen.assert_called_once()

    @mock.patch('nfl.fantasy_insights.generate_in_background', return_value=True)
    @mock.patch('nfl.fantasy_views.sleeper.user', return_value={'user_id': 'u1'})
    def test_stored_rows_are_served_without_regenerating(self, _user, gen):
        FantasyInsight.objects.create(sleeper_user_id='u1', username='someone', league_id='L1',
                                      season=2026, week=1, payload={'league_id': 'L1', 'name': 'One'})
        r = self.client.get('/api/fantasy/insights/?username=someone')
        body = json.loads(r.content)
        self.assertEqual(body['status'], 'ready')
        self.assertEqual(body['leagues'][0]['name'], 'One')
        gen.assert_not_called()
        # a refresh on a fresh row is refused (20 minute floor)
        r = self.client.get('/api/fantasy/insights/?username=someone&refresh=1')
        gen.assert_not_called()

    def test_freshness_helper(self):
        self.assertFalse(fi.is_fresh([]))
        row = FantasyInsight.objects.create(sleeper_user_id='u1', username='x', league_id='L1',
                                            season=2026, week=1, payload={})
        self.assertTrue(fi.is_fresh([row]))


class LinkTriggerTests(TestCase):
    def _sign_in(self):
        from nfl.models import DeskUser
        u = DeskUser.objects.create(google_sub='sub1', email='x@example.com', name='X')
        session = self.client.session
        session['desk_user_id'] = u.id
        session.save()
        return u

    @mock.patch('nfl.fantasy_insights.kick_for_username', return_value=True)
    def test_linking_a_handle_kicks_the_week_room(self, kick):
        self._sign_in()
        r = self.client.patch('/api/me/', data=json.dumps({'sleeper_username': 'newbie'}),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content)['week_room'], 'generating')
        kick.assert_called_once_with('newbie')
        # saving the same handle again is not a new link
        kick.reset_mock()
        r = self.client.patch('/api/me/', data=json.dumps({'sleeper_username': 'Newbie'}),
                              content_type='application/json')
        self.assertIsNone(json.loads(r.content)['week_room'])
        kick.assert_not_called()

    @mock.patch('nfl.fantasy_insights.generate_in_background', return_value=True)
    @mock.patch('nfl.fantasy_insights.sleeper.user', return_value={'user_id': 'u9'})
    def test_kick_skips_fresh_reports(self, _user, gen):
        self.assertTrue(fi.kick_for_username('someone'))
        gen.assert_called_once_with('someone', 'u9')
        FantasyInsight.objects.create(sleeper_user_id='u9', username='someone', league_id='L1',
                                      season=2026, week=1, payload={})
        gen.reset_mock()
        self.assertFalse(fi.kick_for_username('someone'))
        gen.assert_not_called()

    def test_lock_is_exclusive_per_user(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fi, 'LOCK_DIR', Path(d)):
            self.assertFalse(fi.in_progress('u1'))
            self.assertTrue(fi._acquire('u1'))
            self.assertTrue(fi.in_progress('u1'))
            self.assertFalse(fi._acquire('u1'))
            fi._release('u1')
            self.assertFalse(fi.in_progress('u1'))


class GmVoiceTests(TestCase):
    def test_refusals_and_stubs_fall_back_to_the_template(self):
        self.assertTrue(llm.looks_refused("I'm sorry, but I can't write that."))
        self.assertTrue(llm.looks_refused('Too short to be a note.'))
        self.assertFalse(llm.looks_refused('Listen up, numbnuts. ' * 40))

    @mock.patch('utils.llm.requests.post')
    def test_previous_notes_ride_along_and_are_not_reused(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'choices': [{'message': {'content': 'Listen up. ' * 40}}]}
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': 'k', 'XAI_API_KEY': '', 'LLM_PROVIDER': ''}), \
                mock.patch.object(llm, '_dotenv', return_value=None):
            text = llm.narrate({'name': 'L'}, previous=['first note about numbnuts', 'second note'])
        self.assertTrue(text)
        body = post.call_args.kwargs['json']
        prior = [m for m in body['messages'] if 'Earlier notes' in m['content']]
        self.assertEqual(len(prior), 1)
        self.assertIn('second note', prior[0]['content'])
        self.assertIn('Do not reuse', prior[0]['content'])


class FantasyGateTests(TestCase):
    """The fantasy side (leagues, the GM's note, the draft desk) is for
    signed-in readers; anonymous calls get a 401 with the sign-in URL."""

    def test_anonymous_calls_are_refused_with_the_login_url(self):
        c = Client()
        for path in ('/api/fantasy/insights/?username=x', '/api/fantasy/overview/?username=x',
                     '/api/draft/board/', '/api/draft/leagues/?username=x'):
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path)
            self.assertEqual(json.loads(r.content)['login'], '/api/auth/login/')

    def test_public_pages_stay_open(self):
        c = Client()
        self.assertEqual(c.get('/api/me/').status_code, 200)
        self.assertNotEqual(c.get('/api/seasons/').status_code, 401)

    def test_login_remembers_a_safe_next_path(self):
        from nfl import auth_views
        with mock.patch.object(auth_views, 'CLIENT_ID', 'id'), mock.patch.object(auth_views, 'CLIENT_SECRET', 'secret'):
            r = Client().get('/api/auth/login/?next=/leagues')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.cookies['oauth_next'].value, '/leagues')
            r = Client().get('/api/auth/login/?next=https://evil.example/x')
            self.assertEqual(r.cookies['oauth_next'].value, '/')
