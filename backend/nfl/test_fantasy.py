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
    """Both numbers come straight from Sleeper: this week's projection under
    league scoring, and the average of the remaining weekly projections."""

    def _ctx(self, ros=None, season=None, game=True):
        return {
            'players': {'p': {'name': 'P', 'pos': 'WR', 'positions': ['WR'], 'team': 'DAL', 'injury': None}},
            'proj': {'p': {'stats': {'rec': 5, 'rec_yd': 60}, 'pos': 'WR', 'team': 'DAL', 'opp': 'NYG'}},
            'ros_ppw': lambda pid, s: ros,
            'season_ppg': lambda pid, s: season,
            'team_game': lambda team: {'has_game': game, 'started': False, 'final': False},
        }

    def test_this_week_is_sleepers_number_under_league_scoring(self):
        vals = fe.player_values(['p'], self._ctx(ros=13.0), SETTINGS, week=1)
        self.assertAlmostEqual(vals['p']['proj'], 5 + 6.0, places=2)   # rec 5 x 1 + 60 yd x 0.1
        self.assertAlmostEqual(vals['p']['ros'], 13.0, places=2)

    def test_bye_zeroes_the_week_but_not_the_season_value(self):
        vals = fe.player_values(['p'], self._ctx(ros=13.0, game=False), SETTINGS, week=5)
        self.assertEqual(vals['p']['proj'], 0.0)
        self.assertIn('bye', vals['p']['flags'])
        self.assertAlmostEqual(vals['p']['ros'], 13.0, places=2)

    def test_out_players_project_zero_and_carry_half_their_season_value(self):
        ctx = self._ctx(ros=13.0)
        ctx['players']['p']['injury'] = 'Out'
        vals = fe.player_values(['p'], ctx, SETTINGS, week=3)
        self.assertEqual(vals['p']['proj'], 0.0)
        self.assertIn('out', vals['p']['flags'])
        self.assertAlmostEqual(vals['p']['ros'], 6.5, places=2)

    def test_ros_falls_back_to_the_season_snapshot_then_this_week(self):
        vals = fe.player_values(['p'], self._ctx(ros=None, season=9.0), SETTINGS, week=2)
        self.assertAlmostEqual(vals['p']['ros'], 9.0, places=2)
        vals = fe.player_values(['p'], self._ctx(ros=None, season=None), SETTINGS, week=2)
        self.assertAlmostEqual(vals['p']['ros'], vals['p']['proj'], places=2)


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

    def test_second_claim_is_repaired_with_the_next_cheapest_release(self):
        # both free agents would release the benched DEF; the second line
        # takes the next cheapest release instead of vanishing
        fa = {'fa1': V('fa1', 'WR', 14, team='MIA'), 'fa2': V('fa2', 'WR', 13, team='MIA')}
        lines = fe.waiver_report(SLOTS, self.roster, self.values, ['fa1', 'fa2'], fa, protected=['d1'])
        self.assertEqual([l['add']['player_id'] for l in lines], ['fa1', 'fa2'])
        self.assertEqual(lines[0]['drop']['player_id'], 'd2')
        self.assertEqual(lines[1]['drop']['player_id'], 'w3')
        self.assertTrue(lines[0].get('best_season'))

    def test_wire_caps_at_three_and_keeps_the_best_this_week(self):
        # four season-value claims; the fourth is the best play this week
        fa = {f'fa{i}': V(f'fa{i}', 'WR', 12.5 + i * 0.1, ros=16 - i, team='MIA') for i in range(1, 4)}
        fa['fa4'] = V('fa4', 'WR', 18, ros=12.6, team='MIA')
        lines = fe.waiver_report(SLOTS, self.roster, self.values, list(fa), fa, protected=['d1'])
        self.assertEqual(len(lines), 3)
        ids = [l['add']['player_id'] for l in lines]
        self.assertIn('fa4', ids)
        self.assertEqual(ids[0], 'fa1')                      # ordered by season gain
        self.assertTrue(next(l for l in lines if l['add']['player_id'] == 'fa4').get('best_week'))
        self.assertEqual(len({l['drop']['player_id'] for l in lines}), 3)   # three different releases

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
                                      season=2026, week=1,
                                      payload={'league_id': 'L1', 'name': 'One', 'narrative': 'now',
                                               'narrative_history': ['earlier', 'earliest']})
        r = self.client.get('/api/fantasy/insights/?username=someone')
        body = json.loads(r.content)
        self.assertEqual(body['status'], 'ready')
        self.assertEqual(body['leagues'][0]['name'], 'One')
        # the GM's earlier notes are memory for the next rewrite, not page content
        self.assertNotIn('narrative_history', body['leagues'][0])
        self.assertEqual(body['leagues'][0]['narrative'], 'now')
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


class DraftWatchTests(TestCase):
    LEAGUES = [{'league_id': 'L1', 'status': 'in_season'}, {'league_id': 'L2', 'status': 'in_season'},
               {'league_id': 'L3', 'status': 'pre_draft'}]

    def setUp(self):
        FantasyInsight.objects.create(sleeper_user_id='u1', username='someone', league_id='L1',
                                      season=2026, week=1, payload={'league_id': 'L1', 'status': 'in_season'})
        FantasyInsight.objects.create(sleeper_user_id='u1', username='someone', league_id='L2',
                                      season=2026, week=1, payload={'league_id': 'L2', 'status': 'pre_draft'})
        FantasyInsight.objects.create(sleeper_user_id='u1', username='someone', league_id='L3',
                                      season=2026, week=1, payload={'league_id': 'L3', 'status': 'pre_draft'})

    @mock.patch('nfl.fantasy_insights.sleeper.leagues')
    def test_only_the_freshly_drafted_league_is_flagged(self, leagues):
        leagues.return_value = self.LEAGUES
        self.assertEqual(fi.newly_drafted_leagues('u1', 2026), ['L2'])

    @mock.patch('nfl.fantasy_insights.sleeper.leagues')
    def test_a_league_without_a_note_is_flagged_too(self, leagues):
        leagues.return_value = self.LEAGUES + [{'league_id': 'L4', 'status': 'in_season'}]
        self.assertEqual(fi.newly_drafted_leagues('u1', 2026), ['L2', 'L4'])

    @mock.patch('nfl.fantasy_insights.generate_in_background', return_value=True)
    @mock.patch('nfl.fantasy_insights.newly_drafted_leagues', return_value=['L2'])
    @mock.patch('nfl.fantasy_views.sleeper.state', return_value={'season': '2026', 'week': 1})
    @mock.patch('nfl.fantasy_views.sleeper.user', return_value={'user_id': 'u1'})
    def test_reading_the_page_rewrites_the_drafted_league_now(self, _user, _state, _changed, gen):
        client = Client()
        sign_in(client)
        r = client.get('/api/fantasy/insights/?username=someone')
        body = json.loads(r.content)
        self.assertEqual(body['regenerating'], ['L2'])
        self.assertTrue(body['generating'])
        gen.assert_called_once_with('someone', 'u1', league_ids=['L2'])

    @mock.patch('nfl.fantasy_insights.generate_for_user')
    @mock.patch('nfl.fantasy_insights.sleeper.leagues')
    @mock.patch('nfl.fantasy_insights.sleeper.state', return_value={'season': '2026', 'week': 1})
    def test_the_watcher_writes_only_what_changed(self, _state, leagues, gen):
        leagues.return_value = self.LEAGUES
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fi, 'LOCK_DIR', Path(d)):
            done = fi.refresh_newly_drafted()
        self.assertEqual(done, {'someone': ['L2']})
        gen.assert_called_once_with('someone', use_llm=True, league_ids=['L2'])


class ScheduleTests(TestCase):
    """team_games: both sides of a game point at the same game with the
    Desk's home/away and Sleeper's team codes."""

    def test_both_sides_carry_the_game(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Game, Team
        kc = Team.objects.create(team_id=12, team_name='Kansas City Chiefs', short_name='KC')
        wsh = Team.objects.create(team_id=28, team_name='Washington Commanders', short_name='WSH')
        Game.objects.create(event_id=5, game_datetime=timezone.now() + timedelta(days=2),
                            season=2026, week_num=1, season_type_id=2, home_team=wsh, away_team=kc,
                            home_score=None, away_score=None)
        sched = fi._schedule(2026, 1)
        self.assertEqual(set(sched), {'KC', 'WAS'})          # Sleeper's code for Washington
        self.assertEqual(sched['WAS']['opp'], 'KC')
        self.assertTrue(sched['WAS']['home'])
        self.assertFalse(sched['KC']['home'])
        self.assertEqual(sched['KC']['game_id'], sched['WAS']['game_id'])
        self.assertEqual((sched['KC']['away_team'], sched['KC']['home_team']), ('KC', 'WAS'))
        self.assertFalse(sched['KC']['started'])
        self.assertFalse(sched['KC']['final'])
        self.assertIsNone(sched['KC']['home_score'])


class TradeEvaluationTests(TestCase):
    def setUp(self):
        self.values = {
            'q1': V('q1', 'QB', 20), 'r1': V('r1', 'RB', 15), 'r2': V('r2', 'RB', 12),
            'w1': V('w1', 'WR', 12), 'w2': V('w2', 'WR', 11), 'w3': V('w3', 'WR', 3),
            't1': V('t1', 'TE', 8), 'k1': V('k1', 'K', 7), 'd1': V('d1', 'DEF', 6), 'd2': V('d2', 'DEF', 5),
            'q2': V('q2', 'QB', 17),
            'pw': V('pw', 'WR', 16), 'pr': V('pr', 'RB', 6), 'pq': V('pq', 'QB', 15), 'pt': V('pt', 'TE', 7),
            'pk': V('pk', 'K', 6), 'pd': V('pd', 'DEF', 5), 'pw2': V('pw2', 'WR', 10), 'pw3': V('pw3', 'WR', 9),
        }
        self.mine = ['q1', 'r1', 'r2', 'w1', 'w2', 'w3', 't1', 'k1', 'd1', 'd2', 'q2']
        self.theirs = ['pw', 'pr', 'pq', 'pt', 'pk', 'pd', 'pw2', 'pw3']

    def test_a_steal_is_an_accept_and_costs_the_other_side(self):
        ev = fe.evaluate_trade(SLOTS, self.mine, self.theirs, send=['w3'], get=['pw'], values=self.values)
        self.assertEqual(ev['verdict'], 'accept')
        self.assertGreaterEqual(ev['my_ros_delta'], fe.TRADE_FLOOR)
        self.assertGreater(ev['my_week_delta'], 0)          # pw starts over w2 this week
        self.assertLess(ev['their_ros_delta'], 0)
        self.assertEqual([x['player_id'] for x in ev['get']], ['pw'])
        self.assertIn('accept', ev['summary'])

    def test_giving_away_the_quarterback_is_a_decline(self):
        ev = fe.evaluate_trade(SLOTS, self.mine, self.theirs, send=['q1'], get=['pr'], values=self.values)
        self.assertEqual(ev['verdict'], 'decline')
        self.assertLess(ev['my_ros_delta'], 0)

    def test_two_for_one_over_the_roster_limit_names_the_release(self):
        ev = fe.evaluate_trade(SLOTS, self.mine, self.theirs, send=['w3'], get=['pw', 'pw2'],
                               values=self.values, roster_max=len(self.mine))
        self.assertEqual(len(ev['my_cuts']), 1)
        self.assertIn('release', ev['summary'])

    def test_players_not_on_the_rosters_are_ignored(self):
        ev = fe.evaluate_trade(SLOTS, self.mine, self.theirs, send=['nobody'], get=['pw'], values=self.values)
        self.assertEqual(ev['send'], [])
        self.assertEqual([x['player_id'] for x in ev['get']], ['pw'])


class ProposalTests(TestCase):
    """A pending trade in Sleeper's feed that involves my roster is scored
    for both sides; settled ones and other people's trades are not."""

    def test_pending_trade_is_scored(self):
        values = {'a': V('a', 'WR', 12), 'b': V('b', 'WR', 3), 'c': V('c', 'WR', 16), 'd': V('d', 'WR', 9)}
        rosters = [{'roster_id': 1, 'owner_id': 'me', 'players': ['a', 'b']},
                   {'roster_id': 2, 'owner_id': 'them', 'players': ['c', 'd']}]
        users = {'them': {'user_id': 'them', 'display_name': 'Rival'}}
        txs = [{'type': 'trade', 'status': 'pending', 'roster_ids': [1, 2], 'creator': 'them', 'created': 5,
                'adds': {'c': 1, 'b': 2}, 'drops': {'b': 1, 'c': 2}, 'draft_picks': []},
               {'type': 'trade', 'status': 'complete', 'roster_ids': [1, 2], 'adds': {'d': 1}, 'drops': {'d': 2}},
               {'type': 'trade', 'status': 'pending', 'roster_ids': [2, 3], 'adds': {}, 'drops': {}},
               {'type': 'free_agent', 'status': 'complete', 'roster_ids': [1], 'adds': {'zz': 1}}]
        with mock.patch('nfl.fantasy_insights.sleeper.league_transactions', return_value=txs):
            out = fi._proposals('L', 1, 'me', rosters[0], rosters, users, ['WR', 'WR'], values, [], 2)
        self.assertEqual(len(out), 1)
        pr = out[0]
        self.assertEqual(pr['partner'], 'Rival')
        self.assertEqual([x['player_id'] for x in pr['get']], ['c'])
        self.assertEqual([x['player_id'] for x in pr['send']], ['b'])
        self.assertEqual(pr['verdict'], 'accept')
        self.assertFalse(pr['from_me'])
        self.assertEqual(pr['status'], 'pending')

    def test_feed_outage_is_not_fatal(self):
        with mock.patch('nfl.fantasy_insights.sleeper.league_transactions', side_effect=RuntimeError('down')):
            self.assertEqual(fi._proposals('L', 1, 'me', {'roster_id': 1}, [], {}, ['WR'], {}, [], 2), [])


class TradeDeskViewTests(TestCase):
    LEAGUE = {'league_id': 'L1', 'name': 'One', 'scoring_settings': SETTINGS,
              'roster_positions': ['WR', 'WR', 'BN']}
    ROSTERS = [{'roster_id': 1, 'owner_id': 'u1', 'players': ['a', 'b']},
               {'roster_id': 2, 'owner_id': 'u2', 'players': ['c', 'd']}]
    BASE = {'season': 2026, 'week': 1, 'schedule': {}, 'trending': {}, 'season_proj': {},
            'ros': {'weeks': 2, 'stats': {'a': {'rec': 20}, 'b': {'rec': 4}, 'c': {'rec': 30}, 'd': {'rec': 10}}},
            'players': {p: {'name': p.upper(), 'pos': 'WR', 'positions': ['WR'], 'team': 'DAL'} for p in 'abcd'},
            'proj': {p: {'stats': {'rec': n}, 'pos': 'WR', 'team': 'DAL'} for p, n in zip('abcd', (10, 2, 15, 5))}}

    def setUp(self):
        self.client = Client()

    def test_signed_out_is_refused(self):
        r = self.client.get('/api/fantasy/trade/?username=x&league_id=L1')
        self.assertEqual(r.status_code, 401)

    @mock.patch('nfl.fantasy_insights.sleeper.league_users', return_value=[{'user_id': 'u2', 'display_name': 'Rival'}])
    @mock.patch('nfl.fantasy_insights.sleeper.league_rosters', return_value=ROSTERS)
    @mock.patch('nfl.fantasy_insights.build_base_context', return_value=BASE)
    @mock.patch('nfl.fantasy_views.sleeper.state', return_value={'season': '2026', 'week': 1})
    @mock.patch('nfl.fantasy_views.sleeper.league', return_value=LEAGUE)
    @mock.patch('nfl.fantasy_views.sleeper.user', return_value={'user_id': 'u1'})
    def test_rosters_then_an_evaluation(self, *_mocks):
        sign_in(self.client)
        r = self.client.get('/api/fantasy/trade/?username=x&league_id=L1')
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertEqual(body['me']['roster_id'], 1)
        self.assertEqual([p['name'] for p in body['me']['players']], ['A', 'B'])   # ROS order
        self.assertEqual(body['partners'][0]['name'], 'Rival')
        self.assertIsNone(body['evaluation'])
        r = self.client.get('/api/fantasy/trade/?username=x&league_id=L1&partner=2&send=b&get=c')
        body = json.loads(r.content)
        ev = body['evaluation']
        self.assertEqual(ev['verdict'], 'accept')
        self.assertEqual(ev['partner'], 'Rival')
        self.assertGreater(ev['my_ros_delta'], 0)
        self.assertLess(ev['their_ros_delta'], 0)


class NumbersRefreshTests(TestCase):
    """The 3-hour numbers pass rewrites the tables and keeps the prose."""

    @mock.patch('nfl.fantasy_insights.league_insight')
    @mock.patch('nfl.fantasy_insights.build_base_context', return_value={'season': 2026, 'week': 1})
    @mock.patch('nfl.fantasy_insights.sleeper.leagues', return_value=[{'league_id': 'L1', 'name': 'One', 'status': 'in_season'},
                                                                      {'league_id': 'L2', 'name': 'Two', 'status': 'in_season'}])
    @mock.patch('nfl.fantasy_insights.sleeper.user', return_value={'user_id': 'u1'})
    @mock.patch('nfl.fantasy_insights.sleeper.state', return_value={'season': '2026', 'week': 1})
    def test_numbers_only_keeps_the_prose_and_its_time(self, _st, _user, _leagues, _base, insight):
        insight.side_effect = lambda base, lg, uid, use_llm=True, previous=None: {
            'league_id': lg['league_id'], 'name': lg['name'], 'status': 'in_season', 'week': 1,
            'waivers': [{'add': {'name': 'New Guy'}}], 'narrative': 'template prose', 'narrative_source': 'template'}
        row = FantasyInsight.objects.create(sleeper_user_id='u1', username='x', league_id='L1', season=2026, week=1,
                                            payload={'league_id': 'L1', 'status': 'in_season', 'narrative': 'the GM said so',
                                                     'narrative_source': 'xai:grok-4.5', 'narrative_history': ['older'],
                                                     'generated_at': '2026-09-10T04:00:00+00:00', 'waivers': []})
        stamp = FantasyInsight.objects.get(pk=row.pk).generated_at
        out = fi.generate_for_user('x', numbers_only=True)
        self.assertEqual([p['league_id'] for p in out], ['L1'])     # L2 has no note yet: left to the draft watch
        fresh = FantasyInsight.objects.get(pk=row.pk)
        self.assertEqual(fresh.payload['narrative'], 'the GM said so')
        self.assertEqual(fresh.payload['narrative_source'], 'xai:grok-4.5')
        self.assertEqual(fresh.payload['narrative_history'], ['older'])
        self.assertEqual(fresh.payload['generated_at'], '2026-09-10T04:00:00+00:00')
        self.assertEqual(fresh.payload['waivers'][0]['add']['name'], 'New Guy')
        self.assertIn('numbers_at', fresh.payload)
        self.assertEqual(fresh.generated_at, stamp)
        self.assertFalse(insight.call_args_list[0].kwargs.get('use_llm', True))

    def test_numbers_job_is_scheduled(self):
        from django.conf import settings
        self.assertIn('nfl.cron.WeekRoomNumbers', settings.CRON_CLASSES)
