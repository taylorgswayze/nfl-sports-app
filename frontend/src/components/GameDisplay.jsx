import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { isNumberLike, figureOrDash } from '../utils'
import { Masthead, Chip, Footnotes, Colophon, ProbGauge, TeamsMenu } from './Almanac'

const FALLBACK_SEASONS = ['2026', '2025', '2024', '2023', '2022']

/* "BAL @ CIN" -> { away: 'BAL', home: 'CIN' } */
function abbrsFrom(game) {
  const m = /^\s*(\S{2,5})\s*@\s*(\S{2,5})\s*$/.exec(game.short_name || '')
  if (m) return { away: m[1], home: m[2] }
  return { away: 'AWAY', home: 'HOME' }
}

function isFinalGame(game) {
  const hasScores = isNumberLike(game.home_score) && isNumberLike(game.away_score)
  const statusFinal = /final|post/i.test(String(game.status || ''))
  return hasScores && (statusFinal || !game.status)
}

function TeamLine({ name, abbr, teamId, logo, record, away, poss }) {
  return (
    <div className="trow">
      <Chip file={logo} to={`/team/${teamId}`} label={`View ${name} schedule`} />
      <span className="tname">
        {!away && <span className="at">at </span>}
        <b>{abbr || name}</b>
        {poss && <span className="poss" title="Possession" aria-label="has possession">&#9679;</span>}
      </span>
      <span className="dots"></span>
      <span className="trec num">{record}</span>
    </div>
  )
}

/* Card-level navigation to the game desk. Real links inside the card
   (logo chips) stop propagation, so they keep their own destinations. */
function useCardLink(to) {
  const navigate = useNavigate()
  return {
    role: 'link',
    tabIndex: 0,
    onClick: (e) => {
      if (!e.target.closest('a')) navigate(to)
    },
    onKeyDown: (e) => {
      if (e.key === 'Enter' && !e.target.closest('a')) navigate(to)
    },
  }
}

function GameEntry({ game, index, live }) {
  // A finished game the hourly cron has not caught up with yet: print the
  // live board's final figures rather than a stale "scheduled" card.
  if (live && live.state === 'post') {
    game = {
      ...game,
      home_score: live.home_score ?? game.home_score,
      away_score: live.away_score ?? game.away_score,
      status: /final|post/i.test(String(game.status || ''))
        ? game.status
        : (live.short_detail || 'Final'),
    }
  }
  const parsed = abbrsFrom(game)
  const abbr = {
    away: game.away_team_abbr || parsed.away,
    home: game.home_team_abbr || parsed.home,
  }
  const cardLink = useCardLink(`/game/${game.event_id}`)
  const cardLabel = `${game.away_team} at ${game.home_team}, open the game page`
  const number = `No. ${game.week_num}.${String(index + 1).padStart(2, '0')}`

  if (live && live.state === 'in') {
    const awayScore = Number(live.away_score ?? 0)
    const homeScore = Number(live.home_score ?? 0)
    const poss = live.possession_team_id
    return (
      <article className="entry live link" aria-label={cardLabel} {...cardLink}>
        <div className="entry-head">
          <span className="entry-no num">{number}</span>
          <span className="live-flag">
            <span className="live-dot" aria-hidden="true"></span>LIVE
          </span>
          <span className="entry-time num">
            {live.short_detail || `${live.clock || ''} Q${live.period || ''}`}
          </span>
        </div>
        <div className="matchup">
          <TeamLine away name={game.away_team} abbr={abbr.away} teamId={game.away_team_id}
            logo={game.away_team_logo} record={game.away_team_record}
            poss={poss != null && poss === game.away_team_id} />
          <div className="fig">
            <span className={`fval num ${awayScore >= homeScore ? 'win' : 'lose'}`}>{awayScore}</span>
          </div>
          <TeamLine name={game.home_team} abbr={abbr.home} teamId={game.home_team_id}
            logo={game.home_team_logo} record={game.home_team_record}
            poss={poss != null && poss === game.home_team_id} />
          <div className="fig">
            <span className={`fval num ${homeScore >= awayScore ? 'win' : 'lose'}`}>{homeScore}</span>
          </div>
        </div>
        {(live.down_distance || live.last_play) && (
          <p className="live-sit">
            {live.down_distance && <b>{live.down_distance}</b>}
            {live.down_distance && live.last_play ? ' · ' : ''}
            {live.last_play}
          </p>
        )}
      </article>
    )
  }

  const final = isFinalGame(game)
  const hasProbs = isNumberLike(game.away_win_prob) && isNumberLike(game.home_win_prob)
  const hasEdge = isNumberLike(game.pred_diff) && Number(game.pred_diff) !== 0
  const total = game.over_under ?? game.total ?? null

  if (final) {
    const awayScore = Number(game.away_score)
    const homeScore = Number(game.home_score)
    const awayWon = awayScore > homeScore
    return (
      <article className="entry final link" aria-label={cardLabel} {...cardLink}>
        <div className="entry-head">
          <span className="entry-no num">{number}</span>
          <span className="final-flag">{String(game.status || 'Final')}</span>
          <span className="entry-time num">{game.game_datetime}</span>
        </div>
        <div className="matchup">
          <TeamLine away name={game.away_team} abbr={abbr.away} teamId={game.away_team_id}
            logo={game.away_team_logo} record={game.away_team_record} />
          <div className="fig">
            <span className={`fval num ${awayWon ? 'win' : 'lose'}`}>{awayScore}</span>
          </div>
          <TeamLine name={game.home_team} abbr={abbr.home} teamId={game.home_team_id}
            logo={game.home_team_logo} record={game.home_team_record} />
          <div className="fig">
            <span className={`fval num ${awayWon ? 'lose' : 'win'}`}>{homeScore}</span>
          </div>
        </div>
        <p className="closing">
          {game.odds && game.odds !== 'N/A' && (
            <>Closed <span className="num">{game.odds}</span></>
          )}
          {hasProbs && (
            <>
              {game.odds && game.odds !== 'N/A' ? ' · ' : ''}
              kickoff probability <span className="num">{game.away_win_prob}/{game.home_win_prob}</span> {abbr.away}.
            </>
          )}
        </p>
      </article>
    )
  }

  return (
    <article className="entry link" aria-label={cardLabel} {...cardLink}>
      <div className="entry-head">
        <span className="entry-no num">{number}</span>
        <span className="entry-time num">{game.game_datetime}</span>
      </div>
      <div className="matchup">
        <TeamLine away name={game.away_team} abbr={abbr.away} teamId={game.away_team_id}
          logo={game.away_team_logo} record={game.away_team_record} />
        <div className="fig">
          <span className="flbl">LINE</span>
          <span className={`fval num${game.odds === 'N/A' ? ' dim' : ''}`}>{figureOrDash(game.odds)}</span>
        </div>
        <TeamLine name={game.home_team} abbr={abbr.home} teamId={game.home_team_id}
          logo={game.home_team_logo} record={game.home_team_record} />
        <div className="fig">
          <span className="flbl">TOTAL</span>
          <span className={`fval num${total == null ? ' dim' : ''}`}>
            {total == null ? '-' : `O/U ${total}`}
          </span>
        </div>
      </div>
      {hasProbs ? (
        <ProbGauge awayAbbr={abbr.away} homeAbbr={abbr.home}
          awayPct={game.away_win_prob} homePct={game.home_win_prob} />
      ) : (
        <p className="note">Lines and probabilities post when the market opens.</p>
      )}
      {hasEdge && (
        <span className="edge num">
          <span className="dag">&dagger;</span>
          MODEL EDGE {Number(game.pred_diff) > 0 ? '+' : ''}{Number(game.pred_diff).toFixed(1)}
        </span>
      )}
    </article>
  )
}

function GameDisplay() {
  // The front page opens on the current week's slate; the head's chips
  // and season controls browse everywhere else.
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [weeks, setWeeks] = useState([])
  const [selectedWeek, setSelectedWeek] = useState({})
  const [seasons, setSeasons] = useState([])
  const [selectedSeason, setSelectedSeason] = useState('')
  // Which season type the week strip shows; null follows the shown week.
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
      // Endpoint not available yet: fall back to the known seasons.
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
      if (week.season) {
        setSelectedSeason((prev) => prev || String(week.season))
      }
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
    if (week.week_num) {
      fetchGamesForWeek(week.week_num, selectedSeason || null, week.season_type_id)
    }
  }

  const seasonLabel = selectedSeason || selectedWeek?.season || ''

  // The slate head: the year bracketed by arrows with the season type
  // beside it, and beneath them the week strip, the showing week inked.
  const SEASON_TYPE_LABELS = { 1: 'Preseason', 2: 'Regular Season', 3: 'Postseason' }

  const arrow = (dir) => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {dir === 'prev' ? <path d="M14.5 6 L8.5 12 L14.5 18" /> : <path d="M9.5 6 L15.5 12 L9.5 18" />}
    </svg>
  )

  /* Short chip labels: HOF, P1-P3, W1-W18, WC, DIV, CONF, SB. */
  const chipLabel = (w) => {
    const n = w.name || `Week ${w.week_num}`
    let m
    if (/hof/i.test(n)) return 'HOF'
    if ((m = /^pre.*?(\d+)$/i.exec(n))) return `P${m[1]}`
    if ((m = /^week\s*(\d+)$/i.exec(n))) return `W${m[1]}`
    if (/wild/i.test(n)) return 'WC'
    if (/division/i.test(n)) return 'DIV'
    if (/conference/i.test(n)) return 'CONF'
    if (/super/i.test(n)) return 'SB'
    return n
  }

  const availableTypes = [...new Set(weeks.map((w) => w.season_type_id))].sort()
  const shownType = selectedType ?? selectedWeek?.season_type_id ?? availableTypes[0]
  const typeWeeks = weeks.filter((w) => w.season_type_id === shownType)
  const yearList = [...new Set(seasons.map(Number).filter(Boolean))].sort((a, b) => a - b)
  const yearNum = Number(seasonLabel) || yearList[yearList.length - 1]
  const yearIdx = yearList.indexOf(yearNum)

  const changeSeason = (year) => {
    setSelectedSeason(String(year))
    setSelectedType(null)
    fetchGamesForWeek(null, year)
  }

  const slatehead = (
    <div className="slatehead">
      <div className="slatehead-top" role="toolbar" aria-label="Season">
        <div className="pager yearpager" role="group" aria-label="Season year">
          <button type="button" className="pager-arrow" aria-label="Previous season"
            disabled={yearIdx <= 0}
            onClick={() => changeSeason(yearList[yearIdx - 1])}>
            {arrow('prev')}
          </button>
          <span className="pager-year num">{yearNum || ''}</span>
          <button type="button" className="pager-arrow" aria-label="Next season"
            disabled={yearIdx < 0 || yearIdx >= yearList.length - 1}
            onClick={() => changeSeason(yearList[yearIdx + 1])}>
            {arrow('next')}
          </button>
        </div>
        {availableTypes.length > 0 && (
          <label className="ctl">
            <span className="lbl">TYPE</span>
            <select value={shownType} onChange={(e) => setSelectedType(Number(e.target.value))}
              aria-label="Season type">
              {availableTypes.map((t) => (
                <option key={t} value={t}>{SEASON_TYPE_LABELS[t] || `Type ${t}`}</option>
              ))}
            </select>
            <span className="car" aria-hidden="true">&#9662;</span>
          </label>
        )}
      </div>
      {weeks.length > 0 && (
        <div className="weekstrip" role="group" aria-label="Week">
          {typeWeeks.map((week) => {
            const cur = weekKey(week) === weekKey(selectedWeek)
            return (
              <button key={weekKey(week)} type="button"
                className={`wchip${cur ? ' cur' : ''}`}
                aria-pressed={cur}
                title={week.name}
                onClick={() => goToWeek(week)}>
                {chipLabel(week)}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )

  const hasEdges = games.some((g) => isNumberLike(g.pred_diff) && Number(g.pred_diff) !== 0)
  const liveFor = (g) => liveMap[String(g.event_id)]
  const isLiveNow = (g) => liveFor(g)?.state === 'in'
  const liveCount = games.filter(isLiveNow).length

  // Live games print first; the sort is stable, so everything else keeps
  // kickoff order.
  const orderedGames = [...games].sort((a, b) => Number(isLiveNow(b)) - Number(isLiveNow(a)))

  return (
    <>
      <Masthead
        vol={`Front Page${seasonLabel ? ` · ${seasonLabel} Season` : ''}`}
        controls={null}
      />

      <section aria-label="The Slate">
        {slatehead}
        {liveCount > 0 && (
          <p className="folio-note">
            <b className="live-note">{liveCount} live now</b>, printed first.
          </p>
        )}

        {loading ? (
          <p className="wire">LOADING THE SLATE&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">COULD NOT LOAD THE SLATE: <b>{error}</b>. Reload the page to try again.</p>
        ) : games.length > 0 ? (
          <div className="slate">
            {orderedGames.map((game, i) => (
              <GameEntry key={game.event_id} game={game} index={i} live={liveFor(game)} />
            ))}
          </div>
        ) : (
          <p className="wire">NO GAMES LISTED for this week. <b>Pick another week above.</b></p>
        )}

        <div className="teamsrail">
          <TeamsMenu />
        </div>

        <Footnotes>
          {hasEdges && (
            <p>
              <span className="mark">&dagger;</span> Model edge: the Desk model&rsquo;s predicted
              line differs from the market line by the points shown.
            </p>
          )}
          <p>Records run through the latest completed week.</p>
          <p>Lines come from the betting market; win probabilities come from the Desk&rsquo;s own model.</p>
          <p>Select any game to open its page, with head-to-head figures. Select a team&rsquo;s logo to open its schedule.</p>
        </Footnotes>
      </section>

      <Colophon center={selectedWeek?.name
        ? `${SEASON_TYPE_LABELS[selectedWeek.season_type_id] || ''} ${selectedWeek.name}`.trim()
        : null} />
    </>
  )
}

export default GameDisplay
