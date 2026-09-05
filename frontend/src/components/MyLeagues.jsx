import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { gameService } from '../api'
import { useMe, rememberSleeperUsername } from '../auth'
import { Masthead, Folio, Footnotes, Colophon } from './Almanac'
import WeekRoom, { WeekRoomPending } from './WeekRoom'

/* MY LEAGUES: every Sleeper league on one page. Each league prints as a
   card (record, rank, this week's matchup with live points, starters
   ledger); below them, THE COMBINE aggregates every rostered player across
   leagues so one glance answers "how are my guys doing right now".
   Re-polls while any of the user's players is in a live game. */

const USER_KEY = 'sleeper_username'

function fmtPts(v) {
  if (v == null) return '–'
  return Number(v).toFixed(1)
}

function GameFlag({ state, detail }) {
  if (state === 'in') {
    return <span className="gflag in"><span className="live-dot" aria-hidden="true"></span>{detail || 'LIVE'}</span>
  }
  if (state === 'post') return <span className="gflag post">{detail || 'Final'}</span>
  if (state === 'pre') return <span className="gflag pre">{detail || 'Scheduled'}</span>
  return <span className="gflag none">–</span>
}

function StartersTable({ rows, caption }) {
  if (!rows?.length) return null
  return (
    <div className="tablewrap">
      <table className="stats">
        <thead>
          <tr>
            <th scope="col" className="txt">{caption}</th>
            <th scope="col">POS</th>
            <th scope="col">TEAM</th>
            <th scope="col">GAME</th>
            <th scope="col">PTS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.player_id}>
              <td className="txt player">{p.name}</td>
              <td className="team">{p.pos || '–'}</td>
              <td className="team">{p.team || 'FA'}</td>
              <td className="n"><GameFlag state={p.game_state} detail={p.game_detail} /></td>
              <td className="n sortcol">{fmtPts(p.points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LeagueCard({ lg, ins, insState, onReprint, reprinting }) {
  const [showBench, setShowBench] = useState(false)
  const m = lg.matchup
  const preDraft = lg.status === 'pre_draft' || lg.status === 'drafting'
  return (
    <article className={`entry lg-card${m && (m.starters || []).some((p) => p.game_state === 'in') ? ' live' : ''}`}>
      <div className="entry-head">
        <span className="entry-no num">{lg.name}</span>
        <span className="entry-time num">{lg.scoring} · {lg.teams || '?'} TEAMS</span>
      </div>

      {ins
        ? <WeekRoom ins={ins} onReprint={onReprint} reprinting={reprinting} />
        : insState ? <WeekRoomPending state={insState} /> : null}

      {lg.error ? (
        <p className="note">{lg.error}.</p>
      ) : preDraft && !ins ? (
        <>
          <p className="note">
            {lg.status === 'drafting' ? 'Draft is LIVE right now.' : 'Draft not held yet.'}
          </p>
          <Link className="ctl advlink" to="/draft/advisor">
            <span className="lbl">OPEN</span> LIVE ADVISOR
          </Link>
        </>
      ) : preDraft ? null : (
        <>
          <p className="lg-standing num">
            {lg.record ? `${lg.record.wins}-${lg.record.losses}${lg.record.ties ? `-${lg.record.ties}` : ''}` : ''}
            {lg.rank ? ` · #${lg.rank} of ${lg.teams}` : ''}
            {lg.points_for != null ? ` · ${fmtPts(lg.points_for)} PF` : ''}
          </p>
          {m && (
            <>
              <div className="lg-score">
                <span className="side me">
                  <span className="who">{lg.my_team_name || 'MY TEAM'}</span>
                  <span className={`fval num ${Number(m.my_points) >= Number(m.opp_points) ? 'win' : 'lose'}`}>{fmtPts(m.my_points)}</span>
                </span>
                <span className="gd-at">vs</span>
                <span className="side opp">
                  <span className="who">{m.opp_name || 'OPPONENT'}</span>
                  <span className={`fval num ${Number(m.opp_points) > Number(m.my_points) ? 'win' : 'lose'}`}>{fmtPts(m.opp_points)}</span>
                </span>
              </div>
              <StartersTable rows={m.starters} caption={`WEEK ${m.week} STARTERS`} />
              {m.bench?.length > 0 && (
                <button type="button" className="benchtoggle"
                  onClick={() => setShowBench((b) => !b)} aria-expanded={showBench}>
                  {showBench ? 'HIDE BENCH' : `BENCH (${m.bench.length})`}
                </button>
              )}
              {showBench && <StartersTable rows={m.bench} caption="BENCH" />}
            </>
          )}
        </>
      )}
    </article>
  )
}

function MyLeagues() {
  const me = useMe()
  const [username, setUsername] = useState(() => localStorage.getItem(USER_KEY) || '')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [insights, setInsights] = useState({ state: null, byLeague: {}, generatedAt: null })
  const [reprinting, setReprinting] = useState(false)
  const timer = useRef(null)
  const insTimer = useRef(null)
  const insTries = useRef(0)

  const stop = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null } }
  const stopIns = () => { if (insTimer.current) { clearTimeout(insTimer.current); insTimer.current = null } }

  /* The Week Room prints from stored reports; a first-time username makes
     the desk generate them in the background, so poll until they land. */
  const loadInsights = (user, refresh = false) => {
    stopIns()
    gameService.fetchFantasyInsights(user, refresh)
      .then((d) => {
        const byLeague = {}
        for (const p of d.leagues || []) byLeague[p.league_id] = p
        const ready = d.status === 'ready' && !(refresh && d.generating)
        setInsights({ state: ready ? 'ready' : 'generating', byLeague, generatedAt: d.generated_at })
        if (d.generating && insTries.current < 40) {
          insTries.current += 1
          insTimer.current = setTimeout(() => loadInsights(user), 6000)
        } else {
          setReprinting(false)
        }
      })
      .catch(() => { setInsights((s) => ({ ...s, state: s.state === 'ready' ? 'ready' : 'error' })); setReprinting(false) })
  }

  const reprint = () => {
    const user = username.trim()
    if (!user || reprinting) return
    setReprinting(true)
    insTries.current = 0
    loadInsights(user, true)
  }

  const load = (name) => {
    const user = (name ?? username).trim()
    if (!user) return
    setError(null)
    setBusy(true)
    gameService.fetchFantasyOverview(user)
      .then((d) => {
        setData(d)
        rememberSleeperUsername(user)
        insTries.current = 0
        setInsights({ state: 'loading', byLeague: {}, generatedAt: null })
        loadInsights(user)
        stop()
        const anyLive = (d.aggregate || []).some((p) => p.game_state === 'in')
        if (anyLive && !document.hidden) timer.current = setTimeout(() => load(user), 45000)
      })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }

  useEffect(() => {
    if (username) load(username)
    return () => { stop(); stopIns() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* The signed-in profile's saved handle fills an empty page on arrival. */
  useEffect(() => {
    if (!username && !data && me?.authenticated && me.sleeper_username) {
      setUsername(me.sleeper_username)
      load(me.sleeper_username)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me])

  const anyLive = (data?.aggregate || []).some((p) => p.game_state === 'in')

  return (
    <>
      <Masthead vol="My Leagues" controls={null} />

      <section aria-labelledby="sec-leagues">
        <Folio sec="MY LEAGUES" id="sec-leagues" title="The Standings Desk"
          cont={data ? `${data.season} · week ${data.week}` : null} />
        <p className="folio-note">
          Every Sleeper league on one page: the Week Room&rsquo;s roster note on
          top (lineup, waivers, trades), then records, this week&rsquo;s matchup,
          and live points while your players are on the field.
          {anyLive && <> <b className="live-note">Players live now; refreshing.</b></>}
        </p>

        <div className="advbar">
          <input className="boardsearch" type="text" placeholder="Sleeper username"
            value={username} onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') load() }}
            aria-label="Sleeper username" />
          <button type="button" className="ctl" onClick={() => load()} disabled={busy}>
            {busy ? 'LOADING…' : 'LOAD LEAGUES'}
          </button>
        </div>

        {error && <p className="wire">COULD NOT LOAD LEAGUES: <b>{error}</b></p>}
        {!data && !error && !busy && (
          <p className="wire">
            ENTER YOUR SLEEPER USERNAME to print your leagues.{' '}
            {me?.authenticated
              ? <b>It saves to your account for next time.</b>
              : <b>It stays on this device; <a href="/api/auth/login/">sign in</a> to keep it across devices.</b>}
          </p>
        )}

        {data?.leagues?.length === 0 && (
          <p className="wire">NO {data.season} LEAGUES FOUND for <b>{data.username}</b>.</p>
        )}

        {data?.leagues?.length > 0 && (
          <div className="slate two-up">
            {data.leagues.map((lg) => (
              <LeagueCard key={lg.league_id} lg={lg}
                ins={insights.byLeague[lg.league_id]}
                insState={insights.state}
                onReprint={reprint} reprinting={reprinting} />
            ))}
          </div>
        )}
      </section>

      {data?.aggregate?.length > 0 && (
        <section aria-labelledby="sec-combine">
          <Folio sec="THE COMBINE" id="sec-combine" title="All My Players"
            cont={`across ${data.leagues.length} league${data.leagues.length === 1 ? '' : 's'}`} />
          <p className="folio-note">
            Every player you roster anywhere, with this week&rsquo;s points summed
            across leagues. Multi-league players print first.
          </p>
          <div className="tablewrap">
            <table className="stats">
              <thead>
                <tr>
                  <th scope="col" className="txt">PLAYER</th>
                  <th scope="col">POS</th>
                  <th scope="col">TEAM</th>
                  <th scope="col">GAME</th>
                  <th scope="col">LEAGUES</th>
                  <th scope="col">STARTED</th>
                  <th scope="col">WK PTS</th>
                </tr>
              </thead>
              <tbody>
                {data.aggregate.map((p) => (
                  <tr key={p.player_id} className={p.game_state === 'in' ? 'leader' : undefined}>
                    <td className="txt player">{p.name}</td>
                    <td className="team">{p.pos || '–'}</td>
                    <td className="team">{p.team || 'FA'}</td>
                    <td className="n"><GameFlag state={p.game_state} detail={p.game_detail} /></td>
                    <td className="n">{p.leagues}</td>
                    <td className="n">{p.started}</td>
                    <td className="n sortcol">{fmtPts(p.total_points)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Footnotes>
            <p>The Week Room projects every player under each league&rsquo;s own
              scoring rules from Sleeper&rsquo;s weekly stat projections, blended with
              the Desk&rsquo;s season model, and prints the best legal lineup, the
              free agents worth a claim (with the drop), and one-for-one trade ideas
              scored for both sides. It reprints every 12 hours.</p>
            <p>Points are each league&rsquo;s own scoring, as Sleeper reports them;
              the WK PTS column sums a player&rsquo;s points across every league
              that rosters them.</p>
            <p>Highlighted rows are players in live games. The desk refreshes
              them about every 45 seconds.</p>
          </Footnotes>
        </section>
      )}

      <Colophon center="My Leagues · The Standings Desk" />
    </>
  )
}

export default MyLeagues
