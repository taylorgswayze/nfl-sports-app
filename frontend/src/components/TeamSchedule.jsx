import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

function TeamSchedule({ teamId: propTeamId, onBack }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const teamId = propTeamId || id

  const [games, setGames] = useState([])
  const [teamName, setTeamName] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentView, setCurrentView] = useState("schedule")
  const [teamStats, setTeamStats] = useState([])
  const [roster, setRoster] = useState([])
  const [selectedSeason, setSelectedSeason] = useState("2024")

  useEffect(() => {
    if (teamId) {
      console.log('Received teamId:', teamId)
      loadSchedule()
    }
  }, [teamId])

  const loadSchedule = async () => {
    try {
      const response = await fetch(`http://localhost:8000/team-schedule/${teamId}/`)
      if (!response.ok) throw new Error("Failed to fetch team schedule")
      const data = await response.json()
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
      const response = await fetch(`http://localhost:8000/teams/${teamId}/stats/?season=${selectedSeason}`)
      if (response.ok) {
        const data = await response.json()
        setTeamStats(data.stats || [])
      }
    } catch (err) {
      console.error("Failed to load team stats:", err)
    }
  }

  const loadRoster = async () => {
    try {
      const response = await fetch(`http://localhost:8000/teams/${teamId}/roster/`)
      if (response.ok) {
        const data = await response.json()
        setRoster(data.roster || [])
      }
    } catch (err) {
      console.error("Failed to load roster:", err)
    }
  }

  const goBack = () => {
    if (onBack) {
      onBack()
    } else {
      navigate('/')
    }
  }

  const handleTeamClick = (team_id) => {
    if (onBack) {
      onBack()
    } else {
      navigate(`/team/${team_id}`)
    }
  }

  const handlePlayerClick = (player, positionGroup) => {
    const positionKey = positionGroup.toLowerCase().replace(' ', '_')
    navigate(`/position/${positionKey}/stats`, { 
      state: { selectedPlayerId: player.athlete_id } 
    })
  }

  const switchView = async (view) => {
    setCurrentView(view)
    if (view === 'stats' && teamStats.length === 0) {
      await loadTeamStats()
    } else if (view === 'roster' && roster.length === 0) {
      await loadRoster()
    }
  }

  const onSeasonChange = async (e) => {
    setSelectedSeason(e.target.value)
    if (currentView === 'stats') {
      await loadTeamStats()
    }
  }

  const getPositionGroup = (position) => {
    if (!position) return 'Special Teams'
    const pos = position.toLowerCase()
    
    if (pos.includes('quarterback')) return 'Quarterback'
    if (pos.includes('running') || pos.includes('fullback')) return 'Running Back'
    if (pos.includes('wide receiver')) return 'Wide Receiver'
    if (pos.includes('tight end')) return 'Tight End'
    if ((pos.includes('guard') || pos.includes('tackle') || pos.includes('center')) && 
        !pos.includes('defensive')) {
      return 'Offensive Line'
    }
    if (pos.includes('offensive') && (pos.includes('line') || pos.includes('guard') || pos.includes('tackle') || pos.includes('center'))) {
      return 'Offensive Line'
    }
    if (pos.includes('defensive') && (pos.includes('line') || pos.includes('end') || pos.includes('tackle'))) {
      return 'Defensive Line'
    }
    if (pos.includes('linebacker')) return 'Linebacker'
    if (pos.includes('cornerback') || pos.includes('safety') || pos.includes('defensive back')) {
      return 'Defensive Back'
    }
    if (pos.includes('kicker') || pos.includes('place kicker')) return 'Kicker'
    if (pos.includes('punter')) return 'Punter'
    if (pos.includes('long snapper')) return 'Special Teams'
    
    return 'Special Teams'
  }

  const groupRosterByPosition = (roster) => {
    const grouped = {}
    roster.forEach(player => {
      const group = getPositionGroup(player.position)
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
                          <img className="team-logo" src={`./logos/${game.opponent_logo}`} alt={game.opponent} />
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
                        {game.is_home ? 'vs' : '@'} {game.opponent}
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
            <select id="season" value={selectedSeason} onChange={onSeasonChange}>
              <option value="2024">2024</option>
              <option value="2023">2023</option>
              <option value="2022">2022</option>
            </select>
          </div>
          
          {teamStats.length > 0 ? (
            <div className="stats-table">
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
                  {Object.entries(teamStats).map(([key, value]) => (
                    <tr key={key}>
                      <td>Team</td>
                      <td>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                      <td>{value}</td>
                      <td>N/A</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="stats-loading">
              <p>No team stats available for {selectedSeason} season.</p>
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

      <style jsx>{`
        .app {
          max-width: 1000px;
          margin: 0 auto;
          padding: 20px;
          font-family: Arial, sans-serif;
        }

        .header {
          position: relative;
          margin-bottom: 20px;
        }

        .home-button {
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          background-color: #007cba;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
        }

        .home-button:hover {
          background-color: #005a87;
        }

        h1 {
          text-align: center;
          color: white;
          margin-bottom: 20px;
        }

        .team-nav {
          display: flex;
          justify-content: center;
          margin-bottom: 30px;
          border-bottom: 2px solid #eee;
        }

        .nav-btn {
          background: none;
          border: none;
          padding: 12px 24px;
          margin: 0 5px;
          cursor: pointer;
          font-size: 16px;
          color: #666;
          border-bottom: 3px solid transparent;
          transition: all 0.3s ease;
        }

        .nav-btn:hover {
          color: white;
          background-color: #444;
        }

        .nav-btn.active {
          color: #007cba;
          border-bottom-color: #007cba;
          font-weight: bold;
        }

        .season-selector {
          margin-bottom: 20px;
          text-align: center;
        }

        .season-selector label {
          margin-right: 10px;
          font-weight: bold;
        }

        .season-selector select {
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
        }

        .roster table.roster-table {
          width: 100%;
          max-width: 800px;
          margin: 0 auto 20px auto;
          border-collapse: separate;
          border-spacing: 2px;
          background-color: #333;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .roster table.roster-table th {
          padding: 12px;
          text-align: center;
          border: 2px solid white;
          background-color: #f5f5f5;
          font-weight: bold;
          color: #333;
        }

        .roster table.roster-table td {
          padding: 12px;
          text-align: center;
          border: 2px solid white;
          background-color: #333;
          color: white;
        }

        .stats-table {
          width: 100%;
          max-width: 800px;
          margin: 0 auto 20px auto;
          border-collapse: separate;
          border-spacing: 0;
          background-color: #333;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          border: 2px solid white;
        }

        .stats-table th {
          padding: 12px;
          text-align: center;
          border: 2px solid white;
          background-color: #f5f5f5;
          font-weight: bold;
          color: #333;
        }

        .stats-table td {
          padding: 12px;
          text-align: center;
          border: 2px solid white;
          background-color: #333;
          color: white;
        }

        .stats-table tr:hover td, .roster-table tr:hover td {
          background-color: #444;
        }

        .roster {
          max-width: 1000px;
          margin: 0 auto;
        }

        .position-super-group {
          margin-bottom: 40px;
        }

        .super-group-title {
          color: #007cba;
          font-size: 24px;
          text-align: center;
          margin-bottom: 25px;
          padding-bottom: 10px;
          border-bottom: 3px solid #007cba;
          font-weight: bold;
        }

        .position-group {
          margin-bottom: 30px;
        }

        .position-group h3 {
          color: white;
          margin-bottom: 15px;
          padding-bottom: 5px;
          border-bottom: 1px solid #666;
          text-align: center;
          font-size: 18px;
        }

        .stats-loading, .roster-loading {
          text-align: center;
          padding: 40px;
          color: #ccc;
          font-style: italic;
        }

        .back-button {
          background-color: #007cba;
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 5px;
          cursor: pointer;
          font-size: 16px;
          margin-top: 30px;
          display: block;
          margin-left: auto;
          margin-right: auto;
        }

        .back-button:hover {
          background-color: #005a87;
        }

        ul {
          list-style: none;
          padding: 0;
        }

        li {
          margin-bottom: 10px;
        }

        .player-link {
          color: #007cba;
          text-decoration: none;
          font-weight: bold;
        }

        .player-link:hover {
          text-decoration: underline;
          color: #005a87;
        }
      `}</style>
    </div>
  )
}

export default TeamSchedule
