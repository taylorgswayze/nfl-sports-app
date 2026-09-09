import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { gameService } from '../api'
import { useMe, rememberSleeperUsername } from '../auth'
import { Masthead, Folio, Footnotes, Colophon, SignInGate } from './Almanac'
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

/* One in-season league: a page-head style header, the GM's note as the
   lead, then the standing line and this week's live matchup. */
function LeagueBlock({ lg, ins, insState, rewriting, onReprint, reprinting }) {
  const [showBench, setShowBench] = useState(false)
  const [showStarters, setShowStarters] = useState(false)
  const m = lg.matchup
  const live = m && (m.starters || []).some((p) => p.game_state === 'in')
  // the note still says pre-draft but the league has drafted: the desk is
  // rewriting it, so print the wait rather than the stale note
  const stale = !!ins && (ins.status === 'pre_draft' || ins.status === 'drafting') && (rewriting || lg.status === 'in_season')
  return (
    <article className={`league${live ? ' live' : ''}`} aria-label={lg.name}>
      <div className="pagehead">
        <span className="kicker">The general manager</span>
        <span className="bigname">{lg.name}</span>
        <span className="meta num">
          {lg.scoring} · {lg.teams || '?'} teams
          {ins?.week ? ` · week ${ins.week}` : ''}
        </span>
      </div>

      {ins && !stale
        ? <WeekRoom ins={ins} onReprint={onReprint} reprinting={reprinting} />
        : insState ? <WeekRoomPending state={stale ? 'generating' : insState} /> : null}

      {lg.error ? (
        <p className="note">{lg.error}.</p>
      ) : (
        <>
          <p className="lg-standing num">
            {lg.record ? `${lg.record.wins}-${lg.record.losses}${lg.record.ties ? `-${lg.record.ties}` : ''}` : ''}
            {lg.rank ? ` · #${lg.rank} of ${lg.teams}` : ''}
            {lg.points_for != null ? ` · ${fmtPts(lg.points_for)} PF` : ''}
          </p>
          {m && (
            <div className="lg-week">
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
              <div className="lg-toggles">
                <button type="button" className="benchtoggle"
                  onClick={() => setShowStarters((b) => !b)} aria-expanded={showStarters}>
                  {showStarters ? 'HIDE STARTERS' : `WEEK ${m.week} STARTERS (${(m.starters || []).length})`}
                </button>
                {m.bench?.length > 0 && (
                  <button type="button" className="benchtoggle"
                    onClick={() => setShowBench((b) => !b)} aria-expanded={showBench}>
                    {showBench ? 'HIDE BENCH' : `BENCH (${m.bench.length})`}
                  </button>
                )}
              </div>
              {showStarters && <StartersTable rows={m.starters} caption={`WEEK ${m.week} STARTERS`} />}
              {showBench && <StartersTable rows={m.bench} caption="BENCH" />}
            </div>
          )}
        </>
      )}
    </article>
  )
}

/* Leagues without a roster yet print as one line each. */
function QuietLeagues({ leagues, byLeague }) {
  if (!leagues.length) return null
  return (
    <>
      <div className="dayhead">
        <h2>Other leagues</h2>
        <span className="rule"></span>
        <span className="n num">{leagues.length} pre-draft</span>
      </div>
      <div className="lgrows">
        {leagues.map((lg) => {
          const ins = byLeague[lg.league_id]
          return (
            <div className="lgrow" key={lg.league_id}>
              <div className="name">{lg.name}<small>{lg.scoring} · {lg.teams || '?'} teams</small></div>
              <div className="stat">{lg.status === 'drafting' ? 'Drafting now' : 'Draft pending'}<small>status</small></div>
              <div className="stat quiet">{ins?.narrative ? 'GM note ready after the draft' : 'No roster yet'}<small>the general manager</small></div>
              <Link className="stat link" to="/draft/advisor">Live advisor<small>open</small></Link>
            </div>
          )
        })}
      </div>
    </>
  )
}


/* THE STARTERS: every player starting for you in any league, one row per
   player and league, grouped by NFL game with the most imminent game first
   (live games, then upcoming by kickoff, then finals, then players with no
   game this week). PROJ is that league's projection for the player and PTS
   what Sleeper has scored so far. */
const ET = 'America/New_York'

function kickoffLabel(g) {
  if (!g?.kickoff) return 'no game this week'
  const d = new Date(g.kickoff)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: ET })
}

function buildGames(data, byLeague) {
  const games = data?.team_games || {}
  const groups = new Map()
  for (const lg of data?.leagues || []) {
    const m = lg.matchup
    if (!m) continue
    const proj = byLeague[lg.league_id]?.roster_proj || {}
    for (const p of m.starters || []) {
      const g = (p.team && games[p.team]) || null
      const key = g?.game_id != null ? `g-${g.game_id}` : 'none'
      if (!groups.has(key)) {
        groups.set(key, { key, game: g, away: g?.away_team ?? null, home: g?.home_team ?? null, rows: [] })
      }
      const pr = proj[p.player_id]?.proj
      groups.get(key).rows.push({
        id: `${p.player_id}-${lg.league_id}`, player_id: p.player_id,
        name: p.name, pos: p.pos, team: p.team,
        league: lg.name, league_id: lg.league_id,
        proj: pr != null ? Number(pr) : null,
        pts: Number(p.points || 0),
        game_state: p.game_state, game_detail: p.game_detail,
      })
    }
  }
  const now = Date.now()
  const rank = (g) => {
    if (!g.game?.kickoff) return [3, 0]
    const live = g.rows.some((r) => r.game_state === 'in') || (g.game.started && !g.game.final)
    if (live) return [0, 0]
    const t = new Date(g.game.kickoff).getTime()
    if (g.game.final || t < now - 4 * 3600 * 1000) return [2, t]
    return [1, t]
  }
  const out = [...groups.values()]
  for (const g of out) {
    g.live = rank(g)[0] === 0
    g.detail = g.rows.find((r) => r.game_state === 'in')?.game_detail
    g.rows.sort((a, b) => ((b.proj ?? -1) - (a.proj ?? -1)) || String(a.name).localeCompare(String(b.name)))
  }
  out.sort((a, b) => { const ra = rank(a), rb = rank(b); return ra[0] - rb[0] || ra[1] - rb[1] })
  return out
}

/* The small heading over each game: away at home, then the kickoff, or the
   clock and score while it plays, or the final. */
function GameHead({ g, cols }) {
  const game = g.game
  const score = game && game.home_score != null && game.away_score != null
    ? `${g.away} ${game.away_score}, ${g.home} ${game.home_score}` : null
  let state
  if (!game) state = 'bye or no team'
  else if (g.live) state = <><span className="live-dot" aria-hidden="true"></span>{[g.detail || 'LIVE', score].filter(Boolean).join(' · ')}</>
  else if (game.final) state = ['Final', score].filter(Boolean).join(' · ')
  else state = kickoffLabel(game)
  return (
    <tr className={`gamerow${g.live ? ' live' : ''}`}>
      <th scope="rowgroup" colSpan={cols}>
        <span className="matchline">
          {game ? <>{g.away}<span className="atword">at</span>{g.home}</> : 'No game this week'}
        </span>
        <span className="kick num">{state}</span>
      </th>
    </tr>
  )
}

function StartersByGame({ data, byLeague }) {
  if (!data?.leagues?.length) return null
  const groups = buildGames(data, byLeague)
  if (!groups.length) return null
  const total = groups.reduce((n, g) => n + g.rows.length, 0)
  const nGames = groups.filter((g) => g.game).length
  return (
    <section aria-labelledby="sec-starters">
      <Folio sec="THE STARTERS" id="sec-starters" title="Every Starter, By Kickoff"
        cont={`${total} starting spot${total === 1 ? '' : 's'} in ${nGames} game${nGames === 1 ? '' : 's'}`} />
      <p className="folio-note">
        Everyone starting for you anywhere this week, grouped by game with the next
        kickoff first: live games, then upcoming, then finals. A player you start in
        two leagues gets a row for each.
      </p>
      <div className="tablewrap">
        <table className="stats starters">
          <thead>
            <tr>
              <th scope="col" className="txt">PLAYER</th>
              <th scope="col">TEAM</th>
              <th scope="col">POS</th>
              <th scope="col" className="txt">LEAGUE</th>
              <th scope="col">PROJ</th>
              <th scope="col">PTS</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => [
              <GameHead key={`h-${g.key}`} g={g} cols={6} />,
              ...g.rows.map((r) => (
                <tr key={`${g.key}-${r.id}`} className={r.game_state === 'in' ? 'leader' : undefined}>
                  <td className="txt player">{r.name}</td>
                  <td className="team">{r.team || 'FA'}</td>
                  <td className="team">{r.pos || '–'}</td>
                  <td className="txt lg"><span className="lgname" title={r.league}>{r.league}</span></td>
                  <td className="n">{r.proj != null ? r.proj.toFixed(1) : '–'}</td>
                  <td className="n sortcol">{r.pts.toFixed(1)}</td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>
      <Footnotes>
        <p>Projections come from the general manager&rsquo;s note (this week&rsquo;s
          projection under that league&rsquo;s scoring) and points from Sleeper as they
          score. Kickoffs are Eastern.</p>
        <p>Highlighted rows are players in live games. The desk refreshes them about
          every 45 seconds.</p>
      </Footnotes>
    </section>
  )
}

function MyLeagues() {
  const me = useMe()
  const [username, setUsername] = useState(() => localStorage.getItem(USER_KEY) || '')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [insights, setInsights] = useState({ state: null, byLeague: {}, generatedAt: null, regenerating: [] })
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
        setInsights({ state: ready ? 'ready' : 'generating', byLeague, generatedAt: d.generated_at,
          regenerating: d.regenerating || [] })
        if (d.generating && insTries.current < 60) {
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
        setInsights({ state: 'loading', byLeague: {}, generatedAt: null, regenerating: [] })
        loadInsights(user)
        stop()
        const anyLive = (d.aggregate || []).some((p) => p.game_state === 'in')
        if (anyLive && !document.hidden) timer.current = setTimeout(() => load(user), 45000)
      })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }

  useEffect(() => () => { stop(); stopIns() }, [])

  /* Signed-in readers only: the saved handle loads the page on arrival. */
  useEffect(() => {
    if (!me?.authenticated || data) return
    const saved = me.sleeper_username || username
    if (saved) {
      setUsername(saved)
      load(saved)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me])

  const anyLive = (data?.aggregate || []).some((p) => p.game_state === 'in')

  const active = (data?.leagues || []).filter((lg) => !(lg.status === 'pre_draft' || lg.status === 'drafting'))
  const quiet = (data?.leagues || []).filter((lg) => lg.status === 'pre_draft' || lg.status === 'drafting')

  if (!me?.authenticated) {
    return (
      <>
        <Masthead />
        <section aria-label="My Leagues">
          <div className="pagehead">
            <span className="kicker">Fantasy</span>
            <span className="bigname">My Leagues</span>
          </div>
          <SignInGate me={me} what="your leagues and the general manager&rsquo;s note" />
        </section>
        <Colophon center="My Leagues · The General Manager" />
      </>
    )
  }

  return (
    <>
      <Masthead />

      <section aria-label="My Leagues">
        <div className="pagehead">
          <span className="kicker">Fantasy</span>
          <span className="bigname">My Leagues</span>
          <span className="meta num">
            {data ? `${data.username} · ${data.leagues.length} league${data.leagues.length === 1 ? '' : 's'} · ${data.season} week ${data.week}` : 'every Sleeper league on one page'}
            {anyLive && <> · <b className="live-note">players live now, refreshing</b></>}
          </span>
          <div className="pagehead-ctl">
            <input className="boardsearch" type="text" placeholder="Sleeper username"
              value={username} onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') load() }}
              aria-label="Sleeper username" />
            <button type="button" className="ctl" onClick={() => load()} disabled={busy}>
              {busy ? 'LOADING…' : 'LOAD LEAGUES'}
            </button>
          </div>
        </div>

        {error && <p className="wire">COULD NOT LOAD LEAGUES: <b>{error}</b></p>}
        {!data && !error && !busy && (
          <p className="wire">
            ENTER YOUR SLEEPER USERNAME to print your leagues. <b>It saves to your account for next time.</b>
          </p>
        )}

        {data?.leagues?.length === 0 && (
          <p className="wire">NO {data.season} LEAGUES FOUND for <b>{data.username}</b>.</p>
        )}

        {active.map((lg) => (
          <LeagueBlock key={lg.league_id} lg={lg}
            ins={insights.byLeague[lg.league_id]}
            insState={insights.state}
            rewriting={(insights.regenerating || []).includes(lg.league_id)}
            onReprint={reprint} reprinting={reprinting} />
        ))}

        <QuietLeagues leagues={quiet} byLeague={insights.byLeague} />
      </section>

      <StartersByGame data={data} byLeague={insights.byLeague} />

      {false && data?.aggregate?.length > 0 && (
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
            <p>The general manager&rsquo;s note projects every player under each
              league&rsquo;s own scoring rules from Sleeper&rsquo;s weekly stat projections,
              blended with the Desk&rsquo;s season model, and prints the lineup card, the
              claims worth making (with the release), and one-for-one trade calls scored
              for both sides. It reprints every 12 hours.</p>
            <p>Points are each league&rsquo;s own scoring, as Sleeper reports them;
              the WK PTS column sums a player&rsquo;s points across every league
              that rosters them.</p>
            <p>Highlighted rows are players in live games. The desk refreshes
              them about every 45 seconds.</p>
          </Footnotes>
        </section>
      )}

      <Colophon center="My Leagues · The General Manager" />
    </>
  )
}

export default MyLeagues
