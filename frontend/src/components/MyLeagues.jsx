import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { gameService } from '../api'
import { useMe, rememberSleeperUsername } from '../auth'
import { Masthead, Folio, Footnotes, Colophon, SignInGate } from './Almanac'
import WeekRoom, { WeekRoomPending } from './WeekRoom'
import TradeEvaluator from './TradeEvaluator'

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

/* One in-season league: a band with the league's name and standing, the
   live score, the general manager folded to one bar with his
   recommendations under it, then the starters and bench behind toggles. */
function LeagueBlock({ lg, ins, insState, rewriting, onReprint, reprinting }) {
  const [showBench, setShowBench] = useState(false)
  const [showStarters, setShowStarters] = useState(false)
  const m = lg.matchup
  const live = m && (m.starters || []).some((p) => p.game_state === 'in')
  // the note still says pre-draft but the league has drafted: the desk is
  // rewriting it, so print the wait rather than the stale note
  const stale = !!ins && (ins.status === 'pre_draft' || ins.status === 'drafting') && (rewriting || lg.status === 'in_season')
  const rec = lg.record ? `${lg.record.wins}-${lg.record.losses}${lg.record.ties ? `-${lg.record.ties}` : ''}` : ''
  const mp = ins && !stale ? ins.matchup : null
  return (
    <article className={`league${live ? ' live' : ''}`} aria-label={lg.name}>
      <header className="lg-band">
        <span className="kicker">League</span>
        <h2 className="bigname">{lg.name}</h2>
        <span className="meta num">
          {lg.scoring} · {lg.teams || '?'} teams{ins?.week ? ` · week ${ins.week}` : ''}
          {rec ? ` · ${rec}` : ''}{lg.rank ? ` · #${lg.rank} of ${lg.teams}` : ''}
          {lg.points_for != null ? ` · ${fmtPts(lg.points_for)} PF` : ''}
        </span>
      </header>

      {lg.error ? (
        <p className="note">{lg.error}.</p>
      ) : (
        <>
          {m && (
            <div className="lg-score">
              <span className="side me">
                <span className="who">{lg.my_team_name || 'MY TEAM'}</span>
                <span className={`fval num ${Number(m.my_points) >= Number(m.opp_points) ? 'win' : 'lose'}`}>{fmtPts(m.my_points)}</span>
                {mp && <span className="proj num">proj {fmtPts(mp.my_total)}</span>}
              </span>
              <span className="gd-at">vs</span>
              <span className="side opp">
                <span className="who">{m.opp_name || 'OPPONENT'}</span>
                <span className={`fval num ${Number(m.opp_points) > Number(m.my_points) ? 'win' : 'lose'}`}>{fmtPts(m.opp_points)}</span>
                {mp && <span className="proj num">proj {fmtPts(mp.opp_total)}</span>}
              </span>
            </div>
          )}

          {ins && !stale
            ? <WeekRoom ins={ins} onReprint={onReprint} reprinting={reprinting} />
            : insState ? <WeekRoomPending state={stale ? 'generating' : insState} /> : null}

          {m && (
            <div className="lg-week">
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


/* THE STARTERS: two lists. First the NFL games you have a starter in, in
   kickoff order (date, time, how many of your starters play in it). Then
   every starter in any league as one flat list in the same game order, one
   row per player and league: team code, position, league, that league's
   projection and points so far. Rows tint green while the game plays and
   amber once it is final. */
const ET = 'America/New_York'

function kickoffLabel(g, withDate = false) {
  if (!g?.kickoff) return 'no game this week'
  const d = new Date(g.kickoff)
  if (Number.isNaN(d.getTime())) return ''
  const opts = withDate
    ? { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: ET }
    : { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: ET }
  return d.toLocaleString('en-US', opts)
}

/* 'live' | 'final' | 'upcoming' | 'none' for one game and the starters in it */
function gameState(g, now) {
  if (!g.game?.kickoff) return 'none'
  if (g.rows.some((r) => r.game_state === 'in') || (g.game.started && !g.game.final)) return 'live'
  const t = new Date(g.game.kickoff).getTime()
  if (g.game.final || t < now - 4 * 3600 * 1000) return 'final'
  return 'upcoming'
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
  const out = [...groups.values()]
  for (const g of out) {
    g.state = gameState(g, now)
    g.t = g.game?.kickoff ? new Date(g.game.kickoff).getTime() : Infinity
    g.detail = g.rows.find((r) => r.game_state === 'in')?.game_detail
    g.score = g.game && g.game.home_score != null && g.game.away_score != null
      ? `${g.away} ${g.game.away_score}, ${g.home} ${g.game.home_score}` : null
    g.rows.sort((a, b) => ((b.proj ?? -1) - (a.proj ?? -1)) || String(a.name).localeCompare(String(b.name)))
  }
  // kickoff order, first to last; starters with no game close the list
  out.sort((a, b) => (a.t === b.t ? 0 : a.t < b.t ? -1 : 1))
  return out
}

/* The clock for a game: kickoff (with the date when asked), the clock and
   score while it plays, or the final. */
function GameClock({ g, withDate = false }) {
  if (g.state === 'live') {
    return (
      <span className="kick live">
        <span className="live-dot" aria-hidden="true"></span>
        {[g.detail || 'LIVE', withDate ? g.score : null].filter(Boolean).join(' · ')}
      </span>
    )
  }
  if (g.state === 'final') return <span className="kick final">{['Final', withDate ? g.score : null].filter(Boolean).join(' · ')}</span>
  if (g.state === 'none') return <span className="kick">bye</span>
  return <span className="kick">{kickoffLabel(g.game, withDate)}</span>
}

function StartersByKickoff({ data, byLeague }) {
  if (!data?.leagues?.length) return null
  const groups = buildGames(data, byLeague)
  if (!groups.length) return null
  const games = groups.filter((g) => g.game)
  const rows = groups.flatMap((g) => g.rows.map((r) => ({ ...r, g })))
  const nl = data.leagues.length
  return (
    <section aria-labelledby="sec-starters">
      <Folio sec="THE STARTERS" id="sec-starters" title="Every Starter, By Kickoff"
        cont={`${rows.length} starting spot${rows.length === 1 ? '' : 's'} in ${games.length} game${games.length === 1 ? '' : 's'}`} />

      <div className="dayhead">
        <h2>Your games</h2>
        <span className="rule"></span>
        <span className="n num">{games.length} this week</span>
      </div>
      <div className="tablewrap">
        <table className="stats starters games">
          <thead>
            <tr>
              <th scope="col" className="txt">GAME</th>
              <th scope="col" className="txt">KICKOFF</th>
              <th scope="col">STARTERS</th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.key} className={`state-${g.state}`}>
                <td className="txt player">{g.away}<span className="atword">at</span>{g.home}</td>
                <td className="txt"><GameClock g={g} withDate /></td>
                <td className="n sortcol">{g.rows.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="dayhead">
        <h2>Your starters</h2>
        <span className="rule"></span>
        <span className="n num">{rows.length} across {nl} league{nl === 1 ? '' : 's'}</span>
      </div>
      <div className="tablewrap">
        <table className="stats starters players">
          <thead>
            <tr>
              <th scope="col" className="txt">PLAYER</th>
              <th scope="col">TEAM</th>
              <th scope="col">POS</th>
              <th scope="col" className="txt">LEAGUE</th>
              <th scope="col">GAME</th>
              <th scope="col">PROJ</th>
              <th scope="col">PTS</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={`state-${r.g.state}`}>
                <td className="txt player">{r.name}</td>
                <td className="team">{r.team || 'FA'}</td>
                <td className="team">{r.pos || '–'}</td>
                <td className="txt lg"><span className="lgname" title={r.league}>{r.league}</span></td>
                <td className="n"><GameClock g={r.g} /></td>
                <td className="n">{r.proj != null ? r.proj.toFixed(1) : '–'}</td>
                <td className="n sortcol">{r.pts.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/* STATUS REPORT: every starter, in any league, whose listed status could
   keep him from playing (questionable, doubtful, out, IR, PUP, suspended
   and the rest) or who has no game this week: the players to move out of
   the lineup before kickoff, worst first. */
const STATUS_RANK = { out: 0, ir: 0, pup: 0, sus: 0, na: 0, cov: 0, dnr: 0, bye: 0, doubtful: 1, questionable: 2 }
const STATUS_LABEL = {
  out: 'Out', ir: 'Injured reserve', pup: 'PUP', sus: 'Suspended', na: 'Not active', cov: 'COVID list',
  dnr: 'Did not report', bye: 'Bye week', doubtful: 'Doubtful', questionable: 'Questionable',
}

function buildStatus(data, byLeague) {
  const games = data?.team_games || {}
  const haveSchedule = Object.keys(games).length > 0
  const rows = []
  for (const lg of data?.leagues || []) {
    const m = lg.matchup
    if (!m) continue
    const proj = byLeague[lg.league_id]?.roster_proj || {}
    for (const p of m.starters || []) {
      const listed = p.injury || proj[p.player_id]?.injury || ''
      const key = listed.toLowerCase()
      const bye = haveSchedule && p.team && !games[p.team]
      if (!listed && !bye) continue
      const rank = listed ? (STATUS_RANK[key] ?? 1) : 0
      rows.push({
        id: `${p.player_id}-${lg.league_id}`, name: p.name, pos: p.pos, team: p.team, league: lg.name,
        status: listed ? (STATUS_LABEL[key] || listed) : STATUS_LABEL.bye,
        extra: listed && bye ? 'and no game this week' : '',
        rank, proj: proj[p.player_id]?.proj, game: (p.team && games[p.team]) || null,
      })
    }
  }
  rows.sort((a, b) => a.rank - b.rank || String(a.name).localeCompare(String(b.name)))
  return rows
}

function StatusReport({ data, byLeague }) {
  if (!data?.leagues?.length) return null
  const rows = buildStatus(data, byLeague)
  return (
    <section aria-labelledby="sec-status">
      <Folio sec="STATUS REPORT" id="sec-status" title="Starters in Doubt"
        cont={rows.length ? `${rows.length} to check before kickoff` : 'every starter healthy, with a game'} />
      {rows.length === 0 ? (
        <p className="wr-none">None. <span>Every starter is listed healthy and has a game this week.</span></p>
      ) : (
        <div className="tablewrap">
          <table className="stats starters status">
            <thead>
              <tr>
                <th scope="col" className="txt">PLAYER</th>
                <th scope="col">TEAM</th>
                <th scope="col">POS</th>
                <th scope="col" className="txt">LEAGUE</th>
                <th scope="col" className="txt">STATUS</th>
                <th scope="col">GAME</th>
                <th scope="col">PROJ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={`sev-${r.rank}`}>
                  <td className="txt player">{r.name}</td>
                  <td className="team">{r.team || 'FA'}</td>
                  <td className="team">{r.pos || '–'}</td>
                  <td className="txt lg"><span className="lgname" title={r.league}>{r.league}</span></td>
                  <td className="txt status">{r.status}{r.extra ? <span className="wr-meta"> {r.extra}</span> : null}</td>
                  <td className="n"><span className="kick">{r.game ? kickoffLabel(r.game) : 'no game'}</span></td>
                  <td className="n sortcol">{r.proj != null ? Number(r.proj).toFixed(1) : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

const VIEW_TITLE = { leagues: 'My Leagues', starters: 'My Starters', trades: 'Trade Evaluator' }

function MyLeagues() {
  const me = useMe()
  const { view: viewParam } = useParams()
  const view = viewParam === 'starters' || viewParam === 'trades' ? viewParam : 'leagues'
  const [username, setUsername] = useState(() => localStorage.getItem(USER_KEY) || '')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [insights, setInsights] = useState({ state: null, byLeague: {}, generatedAt: null, regenerating: [] })
  const [reprinting, setReprinting] = useState(false)
  const [editing, setEditing] = useState(false)
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
        setEditing(false)
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
          <h1 className="bigname">{VIEW_TITLE[view]}</h1>
          <span className="meta num">
            {data ? `${data.username} · ${data.leagues.length} league${data.leagues.length === 1 ? '' : 's'} · ${data.season} week ${data.week}` : 'every Sleeper league on one page'}
            {anyLive && <> · <b className="live-note">players live now, refreshing</b></>}
          </span>
          <div className="pagehead-ctl">
            {data && !editing ? (
              <button type="button" className="benchtoggle" onClick={() => setEditing(true)}>CHANGE SLEEPER HANDLE</button>
            ) : (
              <>
                <input className="boardsearch" type="text" placeholder="Sleeper username"
                  value={username} onChange={(e) => setUsername(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') load(); if (e.key === 'Escape' && data) setEditing(false) }}
                  aria-label="Sleeper username" autoFocus={editing} />
                <button type="button" className="ctl" onClick={() => load()} disabled={busy}>
                  {busy ? 'LOADING…' : 'LOAD LEAGUES'}
                </button>
              </>
            )}
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

        {data && view === 'leagues' && (
          <>
            {active.map((lg) => (
              <LeagueBlock key={lg.league_id} lg={lg}
                ins={insights.byLeague[lg.league_id]}
                insState={insights.state}
                rewriting={(insights.regenerating || []).includes(lg.league_id)}
                onReprint={reprint} reprinting={reprinting} />
            ))}
            <QuietLeagues leagues={quiet} byLeague={insights.byLeague} />
            <Footnotes>
              <p>The general manager runs on Sleeper&rsquo;s own projections, scored under each
                league&rsquo;s rules: this week&rsquo;s projection sets the lineup card, and the
                average of Sleeper&rsquo;s remaining weekly projections through week 17 (rest of
                season) scores the wire and the phones. The numbers refresh every three hours
                from fresh projections; the note itself reprints every 12 hours, or on demand.</p>
              <p>The lineup card lists every move to the projected optimum. The wire is one row
                per move, at most three, ordered by season gain with the best play for this week
                always included; the bold figures mark the best of each column, and a zero this
                week means the pickup does not crack this week&rsquo;s lineup. The phones are
                one-for-one deals scored for both sides. Scores and records are Sleeper&rsquo;s,
                live during games.</p>
            </Footnotes>
          </>
        )}
      </section>

      {data && view === 'starters' && (
        <>
          <StatusReport data={data} byLeague={insights.byLeague} />
          <StartersByKickoff data={data} byLeague={insights.byLeague} />
          <Footnotes>
            <p>Statuses are Sleeper&rsquo;s listings, refreshed with the general manager&rsquo;s
              note; the lineup card on the Leagues view already benches anyone listed out.
              Projections are that league&rsquo;s this-week number from the note and points are
              Sleeper&rsquo;s as they score. A player you start in two leagues gets a row for each.</p>
            <p>Green rows are in a live game and refresh about every 45 seconds; amber rows have
              played. Kickoffs are Eastern.</p>
          </Footnotes>
        </>
      )}

      {data && view === 'trades' && <TradeEvaluator username={data.username} leagues={data.leagues} />}

      <Colophon center="My Leagues · The General Manager" />
    </>
  )
}

export default MyLeagues
