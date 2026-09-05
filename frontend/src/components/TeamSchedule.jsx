import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { gameService, fetchSeasonsCached } from '../api'
import { isNumberLike, figureOrDash } from '../utils'
import { Masthead, Folio, Chip, Footnotes, Colophon } from './Almanac'

const POSITION_GROUPS = {
  'Quarterback': ['QB'],
  'Running Back': ['RB', 'FB'],
  'Wide Receiver': ['WR'],
  'Tight End': ['TE'],
  'Offensive Line': ['OL', 'G', 'OG', 'T', 'OT', 'C'],
  'Defensive Line': ['DL', 'DE', 'DT', 'NT', 'EDGE'],
  'Linebacker': ['LB', 'OLB', 'MLB', 'ILB'],
  'Defensive Back': ['DB', 'CB', 'S', 'FS', 'SS'],
  'Kicker': ['K', 'PK'],
  'Punter': ['P'],
  'Special Teams': ['LS'],
};

const SEASON_TYPE_LABELS = { 1: 'Preseason', 2: 'Regular Season', 3: 'Postseason' }

const TAB_LABELS = { schedule: 'Schedule', stats: 'Team Stats', roster: 'Roster' }

function getPositionGroup(position) {
  if (!position) return 'Special Teams';
  const pos = position.toUpperCase();
  for (const group in POSITION_GROUPS) {
    if (POSITION_GROUPS[group].includes(pos)) {
      return group;
    }
  }
  return 'Special Teams';
}

/* Result of a schedule game from this team's side, when scores are posted. */
function gameResult(game) {
  const hasScores = isNumberLike(game.home_score) && isNumberLike(game.away_score)
  const statusFinal = /final|post/i.test(String(game.status || ''))
  if (!hasScores || (game.status && !statusFinal)) return null
  const teamScore = Number(game.is_home ? game.home_score : game.away_score)
  const oppScore = Number(game.is_home ? game.away_score : game.home_score)
  return { teamScore, oppScore, won: teamScore > oppScore }
}

function ScheduleEntry({ game }) {
  const navigate = useNavigate()
  const result = gameResult(game)
  const teamProb = game.is_home ? game.home_win_prob : game.away_win_prob
  const to = `/game/${game.event_id}`
  const goCard = (e) => {
    if (!e.target.closest('a')) navigate(to)
  }
  return (
    <article
      className={`entry link${result ? ' final' : ''}`}
      role="link"
      tabIndex={0}
      aria-label={`${game.is_home ? 'vs' : 'at'} ${game.opponent}, Week ${game.week_num}, open the game page`}
      onClick={goCard}
      onKeyDown={(e) => { if (e.key === 'Enter') goCard(e) }}
    >
      <div className="entry-head">
        <span className="entry-no num">No. W{String(game.week_num).padStart(2, '0')}</span>
        {result && (
          <span className={`result-flag num ${result.won ? 'w' : 'l'}`}>
            {result.won ? 'WON' : 'LOST'}
          </span>
        )}
        <span className="entry-time num">{game.game_datetime}</span>
      </div>
      <div className="matchup">
        <div className="trow">
          <Chip file={game.opponent_logo} to={`/team/${game.opponent_id}`}
            label={`View ${game.opponent} schedule`} />
          <span className="tname">
            <span className="at">{game.is_home ? 'vs ' : 'at '}</span>
            <b>{game.opponent_abbr || game.opponent}</b>
          </span>
          <span className="dots"></span>
          <span className="trec num">{game.opponent_record}</span>
        </div>
        {result ? (
          <div className="fig">
            <span className={`fval num ${result.won ? 'win' : 'lose'}`}>
              {result.teamScore}&ndash;{result.oppScore}
            </span>
          </div>
        ) : (
          <div className="fig">
            <span className="flbl">LINE</span>
            <span className={`fval num${game.odds === 'N/A' ? ' dim' : ''}`}>{figureOrDash(game.odds)}</span>
          </div>
        )}
      </div>
      {result ? (
        game.odds && game.odds !== 'N/A' && (
          <p className="closing">Closed <span className="num">{game.odds}</span>.</p>
        )
      ) : (
        isNumberLike(teamProb) && (
          <p className="closing">Win probability <span className="num">{teamProb}%</span>.</p>
        )
      )}
    </article>
  )
}

function TeamSchedule() {
  const { id: teamId } = useParams()
  const navigate = useNavigate()

  const [games, setGames] = useState([])
  const [teamName, setTeamName] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentView, setCurrentView] = useState("schedule")
  const [teamStats, setTeamStats] = useState([])
  const [statsStatus, setStatsStatus] = useState("idle")
  const [roster, setRoster] = useState([])
  const [statsSeason, setStatsSeason] = useState(null)
  const [seasons, setSeasons] = useState([])
  const [selectedSeason, setSelectedSeason] = useState(null)

  useEffect(() => {
    if (teamId) {
      setCurrentView("schedule")
      setTeamStats([])
      setStatsStatus("idle")
      setRoster([])
      loadSchedule()
    }
  }, [teamId])

  useEffect(() => {
    fetchSeasonsCached()
      .then((data) => {
        setSeasons((data.seasons || []).map(String))
        if (data.current_season) {
          setSelectedSeason((prev) => prev ?? String(data.current_season))
        }
      })
      .catch(() => { /* the stats call falls back to the current season */ })
  }, [])

  const loadSchedule = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await gameService.fetchTeamSchedule(teamId)
      setGames(data.schedule)
      setTeamName(data.team)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadTeamStats = async (season) => {
    setStatsStatus("loading")
    try {
      const data = await gameService.fetchTeamStats(teamId, season || null)
      setTeamStats(data.stats || [])
      // The backend names the season it actually served; trust it.
      if (data.season) setSelectedSeason((prev) => prev ?? String(data.season))
      setStatsStatus("ready")
    } catch (err) {
      console.error("Failed to load team stats:", err)
      setStatsStatus("error")
    }
  }

  const loadRoster = async () => {
    try {
      const data = await gameService.fetchTeamRoster(teamId)
      setRoster(data.roster || [])
      setStatsSeason(data.stats_season || null)
    } catch (err) {
      console.error("Failed to load roster:", err)
    }
  }

  const handlePlayerClick = (player, positionGroup) => {
    const positionKey = positionGroup.toLowerCase().replace(' ', '_')
    navigate(`/position/${positionKey}/stats`, {
      state: { selectedPlayerId: player.athlete_id }
    })
  }

  const handleStatClick = (statName) => {
    navigate(`/team-stat/${statName}`, {
      state: { selectedTeamId: teamId }
    })
  }

  const switchView = async (view) => {
    setCurrentView(view)
    if (view === 'stats' && statsStatus === 'idle') {
      await loadTeamStats(selectedSeason)
    } else if (view === 'roster' && roster.length === 0) {
      await loadRoster()
    }
  }

  const onSeasonChange = async (e) => {
    const newSeason = e.target.value
    setSelectedSeason(newSeason)
    await loadTeamStats(newSeason)
  }

  // Order stats by importance for NFL team analysis
  const getOrderedStats = (stats) => {
    // Deduplicate stats by name, keeping the first occurrence
    const deduped = {}
    Object.entries(stats).forEach(([key, stat]) => {
      const statName = stat.name || key
      if (!deduped[statName]) {
        deduped[statName] = [key, stat]
      }
    })

    const statOrder = [
      // Tier 1: Game-Winning Fundamentals (Most Critical)
      'TotalPointsPerGame',
      'TotalPoints',
      'TurnOverDifferential',
      'ThirdDownConvPct',
      'RedzoneScoringPct',

      // Tier 2: Yards Efficiency & Production (Second Priority)
      'YardsPerCompletion',
      'YardsPerPassAttempt',
      'NetYardsPerPassAttempt',
      'YardsPerRushAttempt',
      'TotalYards',
      'YardsPerGame',
      'PassingYards',
      'PassingYardsPerGame',
      'RushingYards',
      'RushingYardsPerGame',

      // Tier 3: Offensive Production
      'TotalTouchdowns',
      'PassingTouchdowns',
      'RushingTouchdowns',
      'CompletionPct',
      'QBRating',
      'QuarterbackRating',

      // Tier 4: Turnover Details
      'TotalTakeaways',
      'TotalGiveaways',
      'Interceptions',
      'FumblesRecovered',
      'FumblesLost',

      // Tier 5: Defensive Impact
      'Sacks',
      'TacklesForLoss',
      'PassesDefended',
      'TotalTackles',
      'SoloTackles',

      // Tier 6: Situational Performance
      'RedzoneEfficiencyPct',
      'FourthDownConvPct',
      'FirstDowns',
      'FirstDownsPerGame',

      // Tier 7: Special Teams
      'FieldGoalPct',
      'ExtraPointPct',
      'NetAvgPuntYards',
      'YardsPerKickReturn',
      'YardsPerPuntReturn',

      // Tier 8: Discipline & Control
      'TotalPenalties',
      'TotalPenaltyYards',
      'PossessionTimeSeconds',

      // Tier 9: Volume Stats
      'TotalOffensivePlays',
      'PassingAttempts',
      'RushingAttempts',
      'Completions'
    ]

    const orderedEntries = []
    const remainingStats = { ...deduped }

    // Add stats in priority order
    statOrder.forEach(statKey => {
      if (remainingStats[statKey]) {
        orderedEntries.push(remainingStats[statKey])
        delete remainingStats[statKey]
      }
    })

    // Add any remaining stats at the end
    Object.values(remainingStats).forEach(entry => {
      orderedEntries.push(entry)
    })

    return orderedEntries
  }

  const groupRosterByPosition = (roster) => {
    const grouped = {}
    roster.forEach(player => {
      const group = getPositionGroup(player.position_abbreviation)
      if (!grouped[group]) grouped[group] = []
      grouped[group].push(player)
    })
    return grouped
  }

  const getOrderedPositionGroups = (groupedRoster) => {
    const offenseOrder = ['Quarterback', 'Running Back', 'Wide Receiver', 'Tight End', 'Offensive Line']
    const defenseOrder = ['Defensive Line', 'Linebacker', 'Defensive Back']
    const specialOrder = ['Kicker', 'Punter', 'Special Teams']

    const offense = offenseOrder.filter(pos => groupedRoster[pos])
    const defense = defenseOrder.filter(pos => groupedRoster[pos])
    const special = specialOrder.filter(pos => groupedRoster[pos])

    return { offense, defense, special }
  }

  const groupedRoster = groupRosterByPosition(roster)
  const orderedGroups = getOrderedPositionGroups(groupedRoster)

  /* Depth order inside each group: starters (rank 1, green band with the
     dagger) first, then the chart's backups, then unranked reserves. Skill
     positions swap the bio columns for season-to-date key figures. */
  const renderRosterTable = (positionGroup) => {
    const players = [...groupedRoster[positionGroup]].sort((a, b) =>
      ((a.depth_rank ?? 99) - (b.depth_rank ?? 99))
      || String(a.position || '').localeCompare(String(b.position || ''))
      || ((a.jersey ?? 999) - (b.jersey ?? 999)))
    const statCols = players.find((p) => p.key_stats?.length)?.key_stats.map((s) => s.label) || []
    return (
      <div key={positionGroup}>
        <h3 className="subhead">
          {positionGroup} <span className="count num">{players.length}</span>
        </h3>
        <div className="tablewrap">
          <table className="stats">
            <thead>
              <tr>
                <th scope="col">No.</th>
                <th scope="col" className="txt">Player</th>
                <th scope="col" className="txt">Position</th>
                <th scope="col">Depth</th>
                {statCols.length > 0 ? (
                  <>
                    <th scope="col">GP</th>
                    {statCols.map((label) => <th scope="col" key={label}>{label}</th>)}
                  </>
                ) : (
                  <>
                    <th scope="col">Age</th>
                    <th scope="col">Ht</th>
                    <th scope="col">Wt</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {players.map(player => (
                <tr key={player.athlete_id} className={player.starter ? 'leader' : undefined}>
                  <td className="n">{player.jersey ?? '-'}</td>
                  <td className="txt player">
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        handlePlayerClick(player, positionGroup);
                      }}
                    >
                      {player.display_name || `${player.first_name} ${player.last_name}`}
                    </a>
                    {player.starter && <span className="mark" title="Projected starter">&dagger;</span>}
                    {player.status && player.status !== 'Active' && (
                      <span className="team"> · {player.status}</span>
                    )}
                  </td>
                  <td className="txt team">{player.position}</td>
                  <td className="n">{player.depth_rank ?? '-'}</td>
                  {statCols.length > 0 ? (
                    <>
                      <td className="n">{player.games_played ?? 0}</td>
                      {statCols.map((label) => (
                        <td className="n" key={label}>
                          {player.key_stats?.find((s) => s.label === label)?.value ?? '-'}
                        </td>
                      ))}
                    </>
                  ) : (
                    <>
                      <td className="n">{player.age ?? '-'}</td>
                      <td className="n">{player.height ?? '-'}</td>
                      <td className="n">{player.weight ?? '-'}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const seasonValue = selectedSeason || ''
  const seasonOptions = seasons.length
    ? seasons
    : (seasonValue ? [seasonValue] : [])
  const results = games.map(gameResult)
  const played = results.filter(Boolean)

  // Games arrive in kickoff order, so season types are contiguous: one
  // pass yields the Preseason / Regular Season / Postseason sections.
  const scheduleSections = []
  for (const game of games) {
    const last = scheduleSections[scheduleSections.length - 1]
    if (!last || last.seasonTypeId !== game.season_type_id) {
      scheduleSections.push({ seasonTypeId: game.season_type_id, games: [game] })
    } else {
      last.games.push(game)
    }
  }
  const wins = played.filter((r) => r.won).length

  return (
    <>
      <Masthead
        vol="Team Desk"
        controls={
          <Link className="ctl" to="/">
            <span className="lbl">BACK TO</span> <span>FRONT PAGE</span>
          </Link>
        }
      />

      <section aria-labelledby="sec-team">
        <Folio
          sec="TEAM"
          id="sec-team"
          title={teamName || 'Team Desk'}
          cont={currentView === 'stats' && seasonValue
            ? `Team Stats · ${seasonValue} Season`
            : TAB_LABELS[currentView]}
          pg={played.length ? `${wins}-${played.length - wins} played` : null}
        />

        <div className="tabs" role="tablist" aria-label="Team desk pages">
          {Object.entries(TAB_LABELS).map(([view, label]) => (
            <button
              key={view}
              role="tab"
              aria-selected={currentView === view}
              onClick={() => switchView(view)}
            >
              {label}
            </button>
          ))}
        </div>

        {currentView === 'schedule' && (
          <>
            <p className="folio-note">
              The full season, in kickoff order. Finished games show the result; upcoming
              games show the market line. Select any game to open its page; select an
              opponent&rsquo;s logo to open their schedule.
            </p>
            {loading ? (
              <p className="wire">LOADING THE SCHEDULE&hellip; <b>stand by</b></p>
            ) : error ? (
              <p className="wire">COULD NOT LOAD THE SCHEDULE: <b>{error}</b>. Reload the page to try again.</p>
            ) : games.length > 0 ? (
              scheduleSections.map((sec) => {
                const secResults = sec.games.map(gameResult).filter(Boolean)
                const wins = secResults.filter((r) => r.won).length
                const losses = secResults.filter((r) => !r.won && r.teamScore !== r.oppScore).length
                const ties = secResults.length - wins - losses
                const record = secResults.length
                  ? `${wins}-${losses}${ties > 0 ? `-${ties}` : ''}`
                  : `${sec.games.length} game${sec.games.length === 1 ? '' : 's'}`
                return (
                  <div key={sec.seasonTypeId}>
                    <div className="weekdiv" role="heading" aria-level="3">
                      <span className="wk-type">{SEASON_TYPE_LABELS[sec.seasonTypeId] || 'Season'}</span>
                      <span className="wk-rule" role="presentation"></span>
                      <span className="wk-season num">{record}</span>
                    </div>
                    <div className="slate">
                      {sec.games.map((game) => (
                        <ScheduleEntry key={game.event_id} game={game} />
                      ))}
                    </div>
                  </div>
                )
              })
            ) : (
              <p className="wire">NO GAMES ON FILE for this team yet.</p>
            )}
          </>
        )}

        {currentView === 'stats' && (
          <>
            <p className="folio-note">
              Season statistics with league rank. Select any row to open the full league
              table for that statistic.
            </p>
            <div className="controls" style={{ marginBottom: 18 }}>
              <label className="ctl">
                <span className="lbl">SEASON</span>
                <select value={seasonValue} onChange={onSeasonChange} aria-label="Season for team stats">
                  {seasonOptions.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <span className="car" aria-hidden="true">&#9662;</span>
              </label>
            </div>

            {statsStatus === 'loading' ? (
              <p className="wire">LOADING TEAM STATS&hellip; <b>stand by</b></p>
            ) : statsStatus === 'error' ? (
              <p className="wire">COULD NOT LOAD TEAM STATS. <b>Reload the page to try again.</b></p>
            ) : Object.keys(teamStats).length > 0 ? (
              <div className="tablewrap">
                <table className="stats">
                  <thead>
                    <tr>
                      <th scope="col" className="txt">Statistic</th>
                      <th scope="col" className="txt">Category</th>
                      <th scope="col">Value</th>
                      <th scope="col">Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getOrderedStats(teamStats).map(([key, stat]) => (
                      <tr
                        key={key}
                        className="clickable"
                        tabIndex={0}
                        onClick={() => handleStatClick(stat.name || key)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            handleStatClick(stat.name || key)
                          }
                        }}
                      >
                        <td className="txt player">{(stat.name || key).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())}</td>
                        <td className="txt team">{stat.category || 'Team'}</td>
                        <td className="n sortcol">{stat.value}</td>
                        <td className="n">{stat.display_rank || '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="wire">
                NO STATS ON FILE for the <b>{seasonValue}</b> season. <b>Pick another season above.</b>
              </p>
            )}
          </>
        )}

        {currentView === 'roster' && (
          <>
            <p className="folio-note">
              The roster by unit and position, depth-chart order: the green band with
              the {' '}<span className="mark">&dagger;</span> is the projected starter.
              {statsSeason && <> Key figures are season-to-date from the <b className="num">{statsSeason}</b> regular season.</>}
              {' '}Select any player to open the league leaders at that position.
            </p>
            {Object.keys(groupedRoster).length > 0 ? (
              <>
                {[['Offense', orderedGroups.offense], ['Defense', orderedGroups.defense], ['Special Teams', orderedGroups.special]]
                  .filter(([, groups]) => groups.length > 0)
                  .map(([unit, groups]) => (
                    <div key={unit}>
                      <Folio sec="UNIT" title={unit} />
                      {groups.map(renderRosterTable)}
                    </div>
                  ))}
              </>
            ) : (
              <p className="wire">NO ROSTER on file for this team.</p>
            )}
          </>
        )}

        <Footnotes>
          <p>Lines are the betting market&rsquo;s latest numbers; results post when games go final.</p>
        </Footnotes>
      </section>

      <Colophon center={teamName || null} />
    </>
  )
}

export default TeamSchedule
