import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { isNumberLike } from '../utils'
import { Masthead, Chip, Footnotes, Colophon, TeamsMenu } from './Almanac'

/* THE SLATE, above the fold. One game leads at display size: the live game
   if there is one, else the next kickoff, else the week's last final. Every
   other game prints as one line of a ruled index, grouped by day and
   ordered by kickoff, with the market line, ESPN's FPI line, the win
   probability and the disagreement between model and market. */

const FALLBACK_SEASONS = ['2026', '2025', '2024', '2023', '2022']
const SEASON_TYPE_LABELS = { 1: 'Preseason', 2: 'Regular Season', 3: 'Postseason' }
const ET = 'America/New_York'

/* "BAL @ CIN" -> { away: 'BAL', home: 'CIN' } */
function abbrsFrom(game) {
  const m = /^\s*(\S{2,5})\s*(?:@|vs)\s*(\S{2,5})\s*$/i.exec(game.short_name || '')
  if (m) return { away: m[1], home: m[2] }
  return { away: 'AWAY', home: 'HOME' }
}

function abbrOf(game) {
  const parsed = abbrsFrom(game)
  return { away: game.away_team_abbr || parsed.away, home: game.home_team_abbr || parsed.home }
}

function kickoff(game) {
  const d = game.game_datetime_utc ? new Date(game.game_datetime_utc) : null
  return d && !Number.isNaN(d.getTime()) ? d : null
}

function fmtTime(d) {
  return d ? d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: ET }) : 'TBD'
}

function fmtDay(d) {
  return d ? d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: ET }) : 'Date to be set'
}

function fmtShortDay(d) {
  return d ? d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: ET }) : 'TBD'
}

function dayKey(d) {
  return d ? d.toLocaleDateString('en-CA', { timeZone: ET }) : 'tbd'
}

function isFinalGame(game) {
  const hasScores = isNumberLike(game.home_score) && isNumberLike(game.away_score)
  const statusFinal = /final|post/i.test(String(game.status || ''))
  return hasScores && (statusFinal || !game.status)
}

/* The market line as the app receives it: "SEA -3.5", "EVEN", "N/A". */
function parseMarket(odds, abbr) {
  const m = /^\s*([A-Za-z]{2,4})\s*([+-]?\d+(?:\.\d+)?)\s*$/.exec(String(odds || ''))
  if (!m) return null
  const team = m[1].toUpperCase()
  const pts = Math.abs(Number(m[2]))
  if (team !== abbr.home && team !== abbr.away) return null
  return { fav: team, pts, homeMargin: team === abbr.home ? pts : -pts }
}

/* Every figure the odds columns print, derived once per game. */
function oddsOf(game) {
  const abbr = abbrOf(game)
  const market = parseMarket(game.odds, abbr)
  const hasFpi = isNumberLike(game.pred_diff) && Number(game.pred_diff) !== 0
  const fpiHome = hasFpi ? Number(game.pred_diff) : null
  const fpi = hasFpi ? { fav: fpiHome >= 0 ? abbr.home : abbr.away, pts: Math.abs(fpiHome) } : null
  let edge = null
  if (market && fpi) {
    const diff = fpiHome - market.homeMargin
    edge = { team: diff >= 0 ? abbr.home : abbr.away, pts: Math.abs(diff) }
  }
  const hasProbs = isNumberLike(game.away_win_prob) && isNumberLike(game.home_win_prob)
  return { abbr, market, fpi, edge, hasProbs }
}

function fmtLine(x) {
  return x ? `${x.fav} -${Number.isInteger(x.pts) ? x.pts : x.pts.toFixed(1)}` : '–'
}

/* Card-level navigation to the game desk. Real links inside (logo chips)
   stop propagation, so they keep their own destinations. */
function useCardLink(to) {
  const navigate = useNavigate()
  return {
    role: 'link',
    tabIndex: 0,
    onClick: (e) => { if (!e.target.closest('a')) navigate(to) },
    onKeyDown: (e) => { if (e.key === 'Enter' && !e.target.closest('a')) navigate(to) },
  }
}

function pickLead(games, liveFor) {
  if (!games.length) return null
  const live = games.find((g) => liveFor(g)?.state === 'in')
  if (live) return live
  const now = Date.now()
  const next = games.find((g) => {
    const d = kickoff(g)
    return d && d.getTime() >= now && !isFinalGame(g)
  })
  if (next) return next
  const unfinished = games.find((g) => !isFinalGame(g) && !(liveFor(g)?.state === 'post'))
  return unfinished || games[games.length - 1]
}

/* "New England Patriots" -> ["New England", "Patriots"]: every NFL nickname
   is one word, so the last word is the name the lead prints big. */
function splitName(full) {
  const parts = String(full || '').trim().split(/\s+/)
  if (parts.length < 2) return ['', full || '']
  return [parts.slice(0, -1).join(' '), parts[parts.length - 1]]
}

function LeadStory({ game, live }) {
  const cardLink = useCardLink(`/game/${game.event_id}`)
  const { abbr, market, fpi, edge, hasProbs } = oddsOf(game)
  const d = kickoff(game)
  const state = live?.state === 'in' ? 'live' : (live?.state === 'post' || isFinalGame(game)) ? 'final' : 'next'
  const awayScore = state === 'live' ? Number(live.away_score ?? 0) : Number(game.away_score ?? live?.away_score ?? 0)
  const homeScore = state === 'live' ? Number(live.home_score ?? 0) : Number(game.home_score ?? live?.home_score ?? 0)
  const kicker = state === 'live' ? 'Lead · live now' : state === 'final' ? 'Lead · final' : 'Lead · next kickoff'
  const when = state === 'live'
    ? (live.short_detail || `${live.clock || ''} Q${live.period || ''}`)
    : `${fmtShortDay(d)} · ${fmtTime(d)} ET`

  let story
  if (state === 'live') {
    story = (live.down_distance || live.last_play)
      ? <>{live.down_distance && <b>{live.down_distance}</b>}{live.down_distance && live.last_play ? ' · ' : ''}{live.last_play}</>
      : <>Under way. Scores refresh about every half minute.</>
  } else if (state === 'final') {
    story = market
      ? <>Closed {fmtLine(market)}{fpi ? <>; FPI had {fmtLine(fpi)}</> : null}.</>
      : <>Final.</>
  } else if (market && fpi && edge) {
    story = edge.pts < 0.5
      ? <>Market and model agree within half a point here.</>
      : <>FPI likes <b>{edge.team}</b> by {edge.pts.toFixed(1)} more than the market does.</>
  } else if (!market && !fpi) {
    story = <>Lines and probabilities post when the market opens.</>
  } else {
    story = null
  }

  const awayFig = state === 'next' ? (hasProbs ? `${game.away_win_prob}%` : '–') : awayScore
  const homeFig = state === 'next' ? (hasProbs ? `${game.home_win_prob}%` : '–') : homeScore
  const awayLeads = state === 'next' ? Number(game.away_win_prob) > Number(game.home_win_prob) : awayScore > homeScore
  const homeLeads = state === 'next' ? Number(game.home_win_prob) >= Number(game.away_win_prob) : homeScore >= awayScore

  return (
    <section className={`lead${state === 'live' ? ' is-live' : ''}`} aria-label={`${game.away_team} at ${game.home_team}, the lead game`} {...cardLink}>
      <div className="lead-head">
        <span className="kicker">{state === 'live' && <span className="live-dot" aria-hidden="true"></span>}{kicker}</span>
        <span className="when num">{when}{state !== 'live' && game.venue ? ` · ${game.venue}` : ''}</span>
      </div>
      <div className="lead-match">
        <Chip file={game.away_team_logo} to={`/team/${game.away_team_id}`} label={`View ${game.away_team} schedule`} />
        <div className="team">{splitName(game.away_team)[1]}<small>{splitName(game.away_team)[0] || abbr.away} · {game.away_team_record}</small></div>
        <div className={`fig num${awayLeads ? ' fav' : ''}`}>{awayFig}</div>
        <Chip file={game.home_team_logo} to={`/team/${game.home_team_id}`} label={`View ${game.home_team} schedule`} />
        <div className="team">{splitName(game.home_team)[1]}<small>at {splitName(game.home_team)[0] || abbr.home} · {game.home_team_record}</small></div>
        <div className={`fig num${homeLeads ? ' fav' : ''}`}>{homeFig}</div>
      </div>
      <div className="lead-side">
        <div className="line num">{market ? fmtLine(market) : 'No line yet'} <span>market line</span></div>
        {fpi && (
          <div className="line num sub">{fmtLine(fpi)} <span>FPI line{hasProbs ? ` · ${fpi.fav === abbr.home ? game.home_win_prob : game.away_win_prob}% to win` : ''}</span></div>
        )}
        {story && <p>{story}</p>}
      </div>
      {hasProbs && state !== 'final' && (
        <div className="lead-gauge" style={{ '--split': `${game.away_win_prob}%` }} role="img"
          aria-label={`Win probability: ${abbr.away} ${game.away_win_prob} percent, ${abbr.home} ${game.home_win_prob} percent`}>
          <span className="num">{abbr.away} {game.away_win_prob}</span>
          <span className="bar"></span>
          <span className="num">{abbr.home} {game.home_win_prob}</span>
          <span className="lbl">Win probability</span>
        </div>
      )}
    </section>
  )
}

function IndexRow({ game, live, hot }) {
  const navigate = useNavigate()
  const { abbr, market, fpi, edge, hasProbs } = oddsOf(game)
  const d = kickoff(game)
  const isLive = live?.state === 'in'
  const final = live?.state === 'post' || isFinalGame(game)
  const awayScore = isLive ? live.away_score : (game.away_score ?? live?.away_score)
  const homeScore = isLive ? live.home_score : (game.home_score ?? live?.home_score)
  const open = () => navigate(`/game/${game.event_id}`)
  return (
    <tr className={isLive ? 'live' : final ? 'final' : undefined} tabIndex={0} role="link"
      aria-label={`${game.away_team} at ${game.home_team}, open the game page`}
      onClick={open} onKeyDown={(e) => { if (e.key === 'Enter') open() }}>
      <td className="teams">
        {abbr.away}<span className="at">at</span>{abbr.home}
        {isLive ? (
          <span className="kick live num"><span className="live-dot" aria-hidden="true"></span>{live.short_detail || 'LIVE'} · {awayScore}-{homeScore}</span>
        ) : final ? (
          <span className="kick num">Final · {awayScore}-{homeScore}</span>
        ) : (
          <span className="kick num">{fmtTime(d)}</span>
        )}
      </td>
      <td className="rec num">{game.away_team_record} · {game.home_team_record}</td>
      <td className="line num">{fmtLine(market)}</td>
      <td className="model num">{fmtLine(fpi)}</td>
      <td className="prob">
        {hasProbs ? (
          <span className="pbar" style={{ '--split': `${game.away_win_prob}%` }}>
            <span className="num">{abbr.away} {game.away_win_prob}</span><i></i><b className="num">{abbr.home} {game.home_win_prob}</b>
          </span>
        ) : <span className="pbar none">–</span>}
      </td>
      <td className={`delta num${hot ? ' hot' : ''}`}>{edge ? `${edge.team} +${edge.pts.toFixed(1)}` : '–'}</td>
    </tr>
  )
}

function DayGroup({ day, games, liveFor, hotKeys }) {
  return (
    <>
      <div className="dayhead">
        <h2>{day}</h2>
        <span className="rule"></span>
        <span className="n num">{games.length} game{games.length === 1 ? '' : 's'}</span>
      </div>
      <div className="tablewrap plain">
        <table className="index">
          <thead>
            <tr>
              <th scope="col">Matchup<small>kickoff, ET</small></th>
              <th scope="col" className="rec">Records</th>
              <th scope="col" className="r">Line<small>market, favorite by</small></th>
              <th scope="col" className="r model">FPI line<small>model, favorite by</small></th>
              <th scope="col" className="prob">Win probability<small>FPI</small></th>
              <th scope="col" className="r">Edge<small>model vs market</small></th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <IndexRow key={g.event_id} game={g} live={liveFor(g)} hot={hotKeys.has(g.event_id)} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function GameDisplay() {
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [weeks, setWeeks] = useState([])
  const [selectedWeek, setSelectedWeek] = useState({})
  const [seasons, setSeasons] = useState([])
  const [selectedSeason, setSelectedSeason] = useState('')
  const [selectedType, setSelectedType] = useState(null)
  const [liveMap, setLiveMap] = useState({})

  useEffect(() => {
    fetchGamesForWeek()
    loadSeasons()
  }, [])

  /* The live board: polled while the page is open. The server caches the
     upstream feed for ~20s, so polling stays cheap no matter how many
     readers are on the page. */
  useEffect(() => {
    let alive = true
    const tick = () => {
      if (document.hidden) return
      gameService.fetchLive()
        .then((d) => {
          if (!alive) return
          const map = {}
          for (const g of d.games || []) map[String(g.event_id)] = g
          setLiveMap(map)
        })
        .catch(() => { /* the live board is a bonus; the page works without it */ })
    }
    tick()
    const id = setInterval(tick, 40000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const loadSeasons = async () => {
    try {
      const data = await gameService.fetchSeasons()
      const list = (Array.isArray(data) ? data : data.seasons || []).map(String)
      setSeasons(list.length ? list : FALLBACK_SEASONS)
    } catch {
      setSeasons(FALLBACK_SEASONS)
    }
  }

  const fetchGamesForWeek = async (weekNum = null, season = null, seasonType = null) => {
    setLoading(true)
    setError(null)
    try {
      const data = await gameService.fetchGames(weekNum, season, seasonType)
      setGames(data.games || [])
      setWeeks(data.weeks || [])
      const week = data.current_week || (data.weeks || [])[0] || {}
      setSelectedWeek(week)
      setSelectedType(week.season_type_id ?? null)
      if (week.season) setSelectedSeason((prev) => prev || String(week.season))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  /* Week identity is (season type, week number): week numbers repeat across
     preseason, regular season and the playoffs. */
  const weekKey = (w) => (w ? `${w.season_type_id}:${w.week_num}` : '')

  const goToWeek = (week) => {
    if (!week) return
    setSelectedWeek(week)
    if (week.week_num) fetchGamesForWeek(week.week_num, selectedSeason || null, week.season_type_id)
  }

  const changeSeason = (year) => {
    setSelectedSeason(String(year))
    setSelectedType(null)
    fetchGamesForWeek(null, year)
  }

  const changeType = (t) => {
    setSelectedType(t)
    const first = weeks.find((w) => w.season_type_id === t)
    if (first) goToWeek(first)
  }

  const seasonLabel = selectedSeason || selectedWeek?.season || ''
  const availableTypes = [...new Set(weeks.map((w) => w.season_type_id))].sort()
  const shownType = selectedType ?? selectedWeek?.season_type_id ?? availableTypes[0]
  const typeWeeks = weeks.filter((w) => w.season_type_id === shownType)
  const weekIdx = typeWeeks.findIndex((w) => weekKey(w) === weekKey(selectedWeek))
  const yearList = [...new Set(seasons.map(Number).filter(Boolean))].sort((a, b) => a - b)

  const liveFor = (g) => liveMap[String(g.event_id)]
  const ordered = [...games].sort((a, b) => (kickoff(a)?.getTime() || 0) - (kickoff(b)?.getTime() || 0))
  const lead = pickLead(ordered, liveFor)
  const rest = ordered.filter((g) => g !== lead)
  const liveCount = ordered.filter((g) => liveFor(g)?.state === 'in').length

  // the three largest model-vs-market disagreements of the week carry green
  const hotKeys = new Set(
    [...ordered]
      .map((g) => ({ id: g.event_id, e: oddsOf(g).edge }))
      .filter((x) => x.e)
      .sort((a, b) => b.e.pts - a.e.pts)
      .slice(0, 3)
      .map((x) => x.id)
  )

  const days = []
  const byDay = new Map()
  for (const g of rest) {
    const k = dayKey(kickoff(g))
    if (!byDay.has(k)) { byDay.set(k, { day: fmtDay(kickoff(g)), games: [] }); days.push(k) }
    byDay.get(k).games.push(g)
  }

  const dates = ordered.map(kickoff).filter(Boolean)
  const span = dates.length
    ? `${dates[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: ET })} to ${dates[dates.length - 1].toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: ET })}`
    : ''
  const hasOdds = ordered.some((g) => oddsOf(g).market || oddsOf(g).fpi)

  const arrow = (dir) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {dir === 'prev' ? <path d="M14.5 6 L8.5 12 L14.5 18" /> : <path d="M9.5 6 L15.5 12 L9.5 18" />}
    </svg>
  )

  return (
    <>
      <Masthead />

      <section aria-label="The Slate">
        <div className="pagehead">
          <span className="kicker">The slate</span>
          <label className="bigselect">
            <select value={weekKey(selectedWeek)} aria-label="Week"
              onChange={(e) => goToWeek(typeWeeks.find((w) => weekKey(w) === e.target.value))}>
              {typeWeeks.map((w) => (
                <option key={weekKey(w)} value={weekKey(w)}>{w.name || `Week ${w.week_num}`}</option>
              ))}
              {typeWeeks.length === 0 && selectedWeek?.week_num && (
                <option value={weekKey(selectedWeek)}>{selectedWeek.name || `Week ${selectedWeek.week_num}`}</option>
              )}
            </select>
            <span className="car" aria-hidden="true">&#9662;</span>
          </label>
          <span className="meta num">
            {span}{span ? ' · ' : ''}{(SEASON_TYPE_LABELS[shownType] || '').toLowerCase()}{ordered.length ? ` · ${ordered.length} games` : ''}
            {liveCount > 0 && <> · <b className="live-note">{liveCount} live now</b></>}
          </span>
          <div className="pagehead-ctl" role="toolbar" aria-label="Season and week">
            <label className="ctl">
              <span className="lbl">SEASON</span>
              <select value={seasonLabel} aria-label="Season" onChange={(e) => changeSeason(e.target.value)}>
                {yearList.map((y) => <option key={y} value={String(y)}>{y}</option>)}
                {!yearList.includes(Number(seasonLabel)) && seasonLabel && <option value={seasonLabel}>{seasonLabel}</option>}
              </select>
              <span className="car" aria-hidden="true">&#9662;</span>
            </label>
            {availableTypes.length > 1 && (
              <label className="ctl">
                <span className="lbl">TYPE</span>
                <select value={shownType} aria-label="Season type" onChange={(e) => changeType(Number(e.target.value))}>
                  {availableTypes.map((t) => <option key={t} value={t}>{SEASON_TYPE_LABELS[t] || `Type ${t}`}</option>)}
                </select>
                <span className="car" aria-hidden="true">&#9662;</span>
              </label>
            )}
            <span className="arrows">
              <button type="button" aria-label="Previous week" disabled={weekIdx <= 0}
                onClick={() => goToWeek(typeWeeks[weekIdx - 1])}>{arrow('prev')}</button>
              <button type="button" aria-label="Next week" disabled={weekIdx < 0 || weekIdx >= typeWeeks.length - 1}
                onClick={() => goToWeek(typeWeeks[weekIdx + 1])}>{arrow('next')}</button>
            </span>
          </div>
        </div>

        {loading ? (
          <p className="wire">LOADING THE SLATE&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">COULD NOT LOAD THE SLATE: <b>{error}</b>. Reload the page to try again.</p>
        ) : ordered.length === 0 ? (
          <p className="wire">NO GAMES ON THIS SLATE. Pick another week above.</p>
        ) : (
          <>
            {lead && <LeadStory game={lead} live={liveFor(lead)} />}
            {days.map((k) => (
              <DayGroup key={k} day={byDay.get(k).day} games={byDay.get(k).games} liveFor={liveFor} hotKeys={hotKeys} />
            ))}
          </>
        )}

        <div className="teamsrail">
          <TeamsMenu />
        </div>

        <Footnotes>
          {hasOdds && (
            <p>
              How to read the odds columns. <b>Line</b> is the betting market&rsquo;s point spread,
              printed for the favorite: DET -7 means the market has Detroit winning by seven.
              <b> FPI line</b> is the same idea from ESPN&rsquo;s Football Power Index, the model
              behind the win probabilities: DET -6.8 means the model has Detroit by 6.8.
              <b> Edge</b> is where the two disagree, printed for the team the model likes more
              than the market does; the week&rsquo;s three largest print in green.
            </p>
          )}
          <p>The lead is the live game when one is on, otherwise the next kickoff. Records run through the latest completed week.</p>
          <p>Select any game to open its page, with head-to-head figures. Select a team&rsquo;s logo to open its schedule.</p>
        </Footnotes>
      </section>

      <Colophon center={`${SEASON_TYPE_LABELS[shownType] || 'Season'} ${selectedWeek?.name || (selectedWeek?.week_num ? `Week ${selectedWeek.week_num}` : '')}`} />
    </>
  )
}

export default GameDisplay
