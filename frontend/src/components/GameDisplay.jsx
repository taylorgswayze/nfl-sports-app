import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { isNumberLike, figureOrDash } from '../utils'
import { Masthead, Folio, Chip, Footnotes, Colophon, ProbGauge } from './Almanac'

const FALLBACK_SEASONS = ['2025', '2024', '2023', '2022']

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

function TeamLine({ name, abbr, teamId, logo, record, away }) {
  return (
    <div className="trow">
      <Chip file={logo} to={`/team/${teamId}`} label={`View ${name} schedule`} />
      <span className="tname">
        {!away && <span className="at">at </span>}
        <b>{abbr || name}</b>
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

function GameEntry({ game, index }) {
  const parsed = abbrsFrom(game)
  const abbr = {
    away: game.away_team_abbr || parsed.away,
    home: game.home_team_abbr || parsed.home,
  }
  const cardLink = useCardLink(`/game/${game.event_id}`)
  const cardLabel = `${game.away_team} at ${game.home_team} — open game detail`
  const number = `No. ${game.week_num}.${String(index + 1).padStart(2, '0')}`
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
              kickoff prob. <span className="num">{game.away_win_prob}/{game.home_win_prob}</span> {abbr.away}.
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
            {total == null ? '—' : `O/U ${total}`}
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
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [weeks, setWeeks] = useState([])
  const [selectedWeek, setSelectedWeek] = useState({})
  const [seasons, setSeasons] = useState([])
  const [selectedSeason, setSelectedSeason] = useState('')

  useEffect(() => {
    fetchGamesForWeek()
    loadSeasons()
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

  const fetchGamesForWeek = async (weekNum = null, season = null) => {
    setLoading(true)
    setError(null)
    try {
      const data = await gameService.fetchGames(weekNum, season)
      setGames(data.games || [])
      setWeeks(data.weeks || [])
      const week = data.current_week || (data.weeks || [])[0] || {}
      setSelectedWeek(week)
      if (week.season) {
        setSelectedSeason((prev) => prev || String(week.season))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const weekIndex = weeks.findIndex((w) => w.name === selectedWeek?.name)

  const goToWeek = (week) => {
    if (!week) return
    setSelectedWeek(week)
    if (week.week_num) {
      fetchGamesForWeek(week.week_num, selectedSeason || null)
    }
  }

  const handleWeekSelect = (event) => {
    goToWeek(weeks.find((w) => w.name === event.target.value))
  }

  const handleSeasonChange = (event) => {
    const season = event.target.value
    setSelectedSeason(season)
    fetchGamesForWeek(selectedWeek?.week_num || null, season)
  }

  const stamp = games.map((g) => g.odds_last_updated).find((t) => t && t !== 'N/A')
  const seasonLabel = selectedSeason || selectedWeek?.season || ''
  const weekNo = selectedWeek?.week_num

  const controls = (
    <>
      <label className="ctl">
        <span className="lbl">SEASON</span>
        <select value={seasonLabel} onChange={handleSeasonChange} aria-label="Season">
          {seasons.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
          {seasonLabel && !seasons.includes(String(seasonLabel)) && (
            <option value={seasonLabel}>{seasonLabel}</option>
          )}
        </select>
        <span className="car" aria-hidden="true">&#9662;</span>
      </label>
      {weeks.length > 0 && (
      <div className="weekset" role="group" aria-label="Week">
        <button type="button" aria-label="Previous week"
          disabled={weekIndex <= 0}
          onClick={() => goToWeek(weeks[weekIndex - 1])}>&#8249;</button>
        <span className="cur">
          <select value={selectedWeek?.name || ''} onChange={handleWeekSelect} aria-label="Select week">
            {weeks.map((week) => (
              <option key={week.name} value={week.name}>{week.name}</option>
            ))}
          </select>
        </span>
        <button type="button" aria-label="Next week"
          disabled={weekIndex < 0 || weekIndex >= weeks.length - 1}
          onClick={() => goToWeek(weeks[weekIndex + 1])}>&#8250;</button>
      </div>
      )}
    </>
  )

  const hasEdges = games.some((g) => isNumberLike(g.pred_diff) && Number(g.pred_diff) !== 0)

  return (
    <>
      <Masthead
        vol={`Sec 1 — Masthead & Index${seasonLabel ? ` — ${seasonLabel} Season` : ''} — Night Ed.`}
        stamp={stamp}
        controls={controls}
      />

      <section aria-labelledby="sec-slate">
        <Folio
          sec="SEC 2"
          id="sec-slate"
          title={`${selectedWeek?.name || 'Week'} Slate`}
          cont={seasonLabel ? `${seasonLabel} Season` : null}
          pg={weekNo ? `p. ${String(weekNo).padStart(2, '0')}` : null}
        />
        <p className="folio-note">
          {games.length > 0
            ? `${games.length} game${games.length === 1 ? '' : 's'}, entered in kickoff order. Lines are closing where final. Probabilities are the Desk model's.`
            : 'Entries print in kickoff order as the schedule posts.'}
        </p>

        {loading ? (
          <p className="wire">SETTING THE SLATE&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">WIRE FAULT &mdash; <b>{error}</b>. Reload to re-request the feed.</p>
        ) : games.length > 0 ? (
          <div className="slate">
            {games.map((game, i) => (
              <GameEntry key={game.event_id} game={game} index={i} />
            ))}
          </div>
        ) : (
          <p className="wire">NO GAMES ON THE BOOKS for this week. <b>Pick another week above.</b></p>
        )}

        <Footnotes>
          {hasEdges && (
            <p>
              <span className="mark">&dagger;</span> Model edge: the Desk model&rsquo;s line differs
              from the market by the figure shown, in points.
            </p>
          )}
          <p>Records print through the latest completed week. Lines are the market&rsquo;s; probabilities are the Desk model&rsquo;s.</p>
          <p>Any entry opens that game&rsquo;s desk, with the head-to-head figures. A team&rsquo;s mark opens its schedule.</p>
        </Footnotes>
      </section>

      <Colophon center={weekNo ? `Week ${weekNo} of ${weeks.filter((w) => w.season_type_id === 2).length || 18}` : null} />
    </>
  )
}

export default GameDisplay
