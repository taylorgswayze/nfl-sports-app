import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { gameService } from '../api'
import { isNumberLike, figureOrDash } from '../utils'
import { Masthead, Folio, Chip, Footnotes, Colophon } from './Almanac'

const POSITION_GROUPS = {
  'Quarterback': ['QB'],
  'Running Back': ['RB', 'FB'],
  'Wide Receiver': ['WR'],
  'Tight End': ['TE'],
  'Offensive Line': ['OL', 'G', 'T', 'C'],
  'Defensive Line': ['DL', 'DE', 'DT'],
  'Linebacker': ['LB'],
  'Defensive Back': ['DB', 'CB', 'S'],
  'Kicker': ['K'],
  'Punter': ['P'],
  'Special Teams': ['LS'],
};

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
  const result = gameResult(game)
  const teamProb = game.is_home ? game.home_win_prob : game.away_win_prob
  return (
    <article className={`entry${result ? ' final' : ''}`}>
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
          <Chip file={game.opponent_logo} />
          <span className="tname">
            <span className="at">{game.is_home ? 'vs ' : 'at '}</span>
            <Link to={`/team/${game.opponent_id}`}>{game.opponent}</Link>
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
  const [teamStats, setTeamStats] = useState({})
  const [roster, setRoster] = useState([])
  const [selectedSeason, setSelectedSeason] = useState(null)
  const [currentSeason, setCurrentSeason] = useState("2025")

  useEffect(() => {
    if (teamId) {
      setCurrentView("schedule")
      setTeamStats({})
      setRoster([])
      loadSchedule()
      getCurrentSeason()
    }
  }, [teamId])

  const getCurrentSeason = async () => {
    try {
      const data = await gameService.fetchGames()
      if (data.current_week && data.current_week.season) {
        const season = data.current_week.season.toString()
        setCurrentSeason(season)
        setSelectedSeason((prev) => prev ?? season)
      }
    } catch (err) {
      console.error("Failed to get current season:", err)
      setSelectedSeason((prev) => prev ?? "2025")
    }
  }

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

  const loadTeamStats = async () => {
    try {
      const season = selectedSeason || currentSeason
      const data = await gameService.fetchTeamStats(teamId, season)
      setTeamStats(data.stats || {})
    } catch (err) {
      console.error("Failed to load team stats:", err)
    }
  }

  const loadRoster = async () => {
    try {
      const data = await gameService.fetchTeamRoster(teamId)
      setRoster(data.roster || [])
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
    if (view === 'stats' && Object.keys(teamStats).length === 0) {
      await loadTeamStats()
    } else if (view === 'roster' && roster.length === 0) {
      await loadRoster()
    }
  }

  const onSeasonChange = async (e) => {
    const newSeason = e.target.value
    setSelectedSeason(newSeason)
    if (currentView === 'stats') {
      try {
        const data = await gameService.fetchTeamStats(teamId, newSeason)
        setTeamStats(data.stats || {})
      } catch (err) {
        console.error('Error loading team stats:', err)
        setTeamStats({})
      }
    }
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

  const renderRosterTable = (positionGroup) => (
    <div key={positionGroup}>
      <h3 className="subhead">
        {positionGroup} <span className="count num">{groupedRoster[positionGroup].length}</span>
      </h3>
      <div className="tablewrap">
        <table className="stats">
          <thead>
            <tr>
              <th scope="col">No.</th>
              <th scope="col" className="txt">Player</th>
              <th scope="col" className="txt">Position</th>
              <th scope="col">Age</th>
              <th scope="col">Ht</th>
              <th scope="col">Wt</th>
            </tr>
          </thead>
          <tbody>
            {groupedRoster[positionGroup].map(player => (
              <tr key={player.athlete_id}>
                <td className="n">{player.jersey ?? '—'}</td>
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
                </td>
                <td className="txt team">{player.position}</td>
                <td className="n">{player.age ?? '—'}</td>
                <td className="n">{player.height ?? '—'}</td>
                <td className="n">{player.weight ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )

  const seasonValue = selectedSeason || currentSeason
  const results = games.map(gameResult)
  const played = results.filter(Boolean)
  const wins = played.filter((r) => r.won).length

  return (
    <>
      <Masthead
        vol="Sec 2 — Team Desk — Night Ed."
        controls={
          <Link className="ctl" to="/">
            <span className="lbl">RETURN TO</span> <span>THE WEEK SLATE</span>
          </Link>
        }
      />

      <section aria-labelledby="sec-team">
        <Folio
          sec="SEC 2"
          id="sec-team"
          title={teamName || 'Team Desk'}
          cont={TAB_LABELS[currentView]}
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
              The full season, entered in kickoff order. Completed games print on lifted stock
              with the result; upcoming games carry the market line.
            </p>
            {loading ? (
              <p className="wire">PULLING THE SCHEDULE&hellip; <b>stand by</b></p>
            ) : error ? (
              <p className="wire">WIRE FAULT &mdash; <b>{error}</b>. Reload to re-request the feed.</p>
            ) : games.length > 0 ? (
              <div className="slate">
                {games.map((game) => (
                  <ScheduleEntry key={game.event_id} game={game} />
                ))}
              </div>
            ) : (
              <p className="wire">NO GAMES ON FILE for this team.</p>
            )}
          </>
        )}

        {currentView === 'stats' && (
          <>
            <p className="folio-note">
              Season figures with league rank. Any line opens the full league table for that figure.
            </p>
            <div className="controls" style={{ marginBottom: 18 }}>
              <label className="ctl">
                <span className="lbl">SEASON</span>
                <select value={seasonValue} onChange={onSeasonChange} aria-label="Season">
                  <option value="2025">2025</option>
                  <option value="2024">2024</option>
                  <option value="2023">2023</option>
                  <option value="2022">2022</option>
                </select>
                <span className="car" aria-hidden="true">&#9662;</span>
              </label>
            </div>

            {Object.keys(teamStats).length > 0 ? (
              <>
                {seasonValue !== currentSeason && (
                  <p className="notice">
                    Historical data for {seasonValue} may not be available;
                    figures shown may be the current season&rsquo;s ({currentSeason}).
                  </p>
                )}
                <div className="tablewrap">
                  <table className="stats">
                    <thead>
                      <tr>
                        <th scope="col" className="txt">Figure</th>
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
                          <td className="txt player">{(stat.name || key).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ')}</td>
                          <td className="txt team">{stat.category || 'Team'}</td>
                          <td className="n sortcol">{stat.value}</td>
                          <td className="n">{stat.display_rank || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="wire">NO TEAM FIGURES on file for the <b>{seasonValue}</b> season.</p>
            )}
          </>
        )}

        {currentView === 'roster' && (
          <>
            <p className="folio-note">
              The roster by unit and position. Any player opens the league leaders at that position.
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
          <p>Lines are the market&rsquo;s at last update; results post when games go final.</p>
        </Footnotes>
      </section>

      <Colophon center={teamName || null} />
    </>
  )
}

export default TeamSchedule
