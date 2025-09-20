import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { getLogoUrl } from '../utils'
import './TeamSchedule.css'

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
        if (selectedSeason === null) {
          setSelectedSeason(season)
        }
      }
    } catch (err) {
      console.error("Failed to get current season:", err)
      if (selectedSeason === null) {
        setSelectedSeason("2025")
      }
    }
  }

  const loadSchedule = async () => {
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

  const goBack = () => {
    navigate('/')
  }

  const handleTeamClick = (team_id) => {
    navigate(`/team/${team_id}`)
  }

  const handlePlayerClick = (player, positionGroup) => {
    const positionKey = positionGroup.toLowerCase().replace(' ', '_')
    navigate(`/position/${positionKey}/stats`, { 
      state: { selectedPlayerId: player.athlete_id } 
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
    console.log('Original stats:', Object.keys(stats))
    
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
    <div key={positionGroup} className="position-group">
      <h3>{positionGroup}</h3>
      <table className="roster-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Position</th>
            <th>Age</th>
            <th>Height</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {groupedRoster[positionGroup].map(player => (
            <tr key={player.athlete_id}>
              <td>{player.jersey || 'N/A'}</td>
              <td>
                <a 
                  href="#" 
                  className="player-link"
                  onClick={(e) => { 
                    e.preventDefault(); 
                    handlePlayerClick(player, positionGroup);
                  }}
                >
                  {player.display_name || `${player.first_name} ${player.last_name}`}
                </a>
              </td>
              <td>{player.position}</td>
              <td>{player.age || 'N/A'}</td>
              <td>{player.height || 'N/A'}</td>
              <td>{player.weight || 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="app">
      <div className="header">
        <button className="home-button" onClick={goBack}>🏠 Home</button>
        <h1>{teamName}</h1>
      </div>
      
      <div className="team-nav">
        <button 
          className={`nav-btn ${currentView === 'schedule' ? 'active' : ''}`}
          onClick={() => switchView('schedule')}
        >
          Schedule
        </button>
        <button 
          className={`nav-btn ${currentView === 'stats' ? 'active' : ''}`}
          onClick={() => switchView('stats')}
        >
          Team Stats
        </button>
        <button 
          className={`nav-btn ${currentView === 'roster' ? 'active' : ''}`}
          onClick={() => switchView('roster')}
        >
          Roster
        </button>
      </div>

      {currentView === 'schedule' && (
        <div className="game-list">
          {loading ? (
            <p>Loading games...</p>
          ) : error ? (
            <p>Error: {error}</p>
          ) : games.length > 0 ? (
            <ul>
              {games.map((game) => (
                <div key={game.event_id} className="game-card">
                  <li>
                    <div className="team-row">
                      <div className="team-box">
                        <a href="#" onClick={(e) => { e.preventDefault(); handleTeamClick(game.opponent_id); }}>
                          <img className="team-logo" src={getLogoUrl(game.opponent_logo)} alt={game.opponent} />
                        </a>
                        <div className="team-name">
                          <a href="#" onClick={(e) => { e.preventDefault(); handleTeamClick(game.opponent_id); }}>
                            {game.opponent}
                          </a>
                        </div>
                        <div className="win-prob">
                          ({game.opponent_record})<br />
                        </div>
                      </div>
                      <div className="team-box">
                        {game.game_datetime}<br />
                        Week {game.week_num}<br />
                        {game.is_home ? 'vs' : '@'} {game.is_home ? teamName : game.opponent}
                      </div>
                    </div>
                  </li>
                </div>
              ))}
            </ul>
          ) : (
            <p>No games found for this team.</p>
          )}
        </div>
      )}

      {currentView === 'stats' && (
        <div className="team-stats">
          <div className="season-selector">
            <label htmlFor="season">Season:</label>
            <select id="season" value={selectedSeason || currentSeason} onChange={onSeasonChange}>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
              <option value="2023">2023</option>
              <option value="2022">2022</option>
            </select>
          </div>
          
          {Object.keys(teamStats).length > 0 ? (
            <div className="stats-table">
              {(selectedSeason || currentSeason) !== currentSeason && (
                <div className="historical-data-notice" style={{
                  backgroundColor: '#fff3cd',
                  border: '1px solid #ffeaa7',
                  borderRadius: '4px',
                  padding: '10px',
                  marginBottom: '15px',
                  color: '#856404'
                }}>
                  <strong>Note:</strong> Historical data for {selectedSeason || currentSeason} may not be available. 
                  Showing current season ({currentSeason}) data.
                </div>
              )}
              <table>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Stat</th>
                    <th>Value</th>
                    <th>Rank</th>
                  </tr>
                </thead>
                <tbody>
                  {getOrderedStats(teamStats).map(([key, stat]) => (
                    <tr key={key}>
                      <td>{stat.category || 'Team'}</td>
                      <td>{stat.name || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                      <td>{stat.value}</td>
                      <td>{stat.display_rank || 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="stats-loading">
              <p>No team stats available for {selectedSeason || currentSeason} season.</p>
            </div>
          )}
        </div>
      )}

      {currentView === 'roster' && (
        <div className="roster">
          {Object.keys(groupedRoster).length > 0 ? (
            <>
              <div className="position-super-group">
                <h2 className="super-group-title">Offense</h2>
                {orderedGroups.offense.map(renderRosterTable)}
              </div>

              <div className="position-super-group">
                <h2 className="super-group-title">Defense</h2>
                {orderedGroups.defense.map(renderRosterTable)}
              </div>

              <div className="position-super-group">
                <h2 className="super-group-title">Special Teams</h2>
                {orderedGroups.special.map(renderRosterTable)}
              </div>
            </>
          ) : (
            <div className="roster-loading">
              <p>No roster information available.</p>
            </div>
          )}
        </div>
      )}

      <button className="back-button" onClick={goBack}>← Back to Games</button>
    </div>
  )
}

export default TeamSchedule
