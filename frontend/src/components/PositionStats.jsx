import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { get } from '../api'

function PositionStats({ position: propPosition, selectedPlayerId: propSelectedPlayerId, onBack }) {
  const { position } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const currentPosition = propPosition || position
  const selectedPlayerId = propSelectedPlayerId || location.state?.selectedPlayerId

  const [players, setPlayers] = useState([])
  const [originalPlayers, setOriginalPlayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSeason, setSelectedSeason] = useState("2025")
  const [keyStats, setKeyStats] = useState([])
  const [sortConfig, setSortConfig] = useState({ key: 'rank', direction: 'asc' })

  useEffect(() => {
    if (currentPosition) {
      loadPositionStats()
    }
  }, [currentPosition, selectedSeason])

  const loadPositionStats = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await get(`/position/${currentPosition}/stats/`, { season: selectedSeason })
      const playersData = data.players || []
      setOriginalPlayers(playersData)
      setPlayers(playersData)
      setKeyStats(data.key_stats || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const goBack = () => {
    navigate(-1)
  }

  const formatStatName = (statName) => {
    return statName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  const formatStatValue = (value, statName) => {
    if (statName.includes('pct') || statName.includes('avg')) {
      return parseFloat(value).toFixed(1)
    }
    return Math.round(value)
  }

  const handleSort = (key) => {
    let direction = 'desc'
    if (sortConfig.key === key && sortConfig.direction === 'desc') {
      direction = 'asc'
    }
    
    setSortConfig({ key, direction })
    
    const sortedPlayers = [...players].sort((a, b) => {
      let aValue, bValue
      
      if (key === 'rank') {
        aValue = a.rank
        bValue = b.rank
      } else if (key === 'name') {
        aValue = a.name.toLowerCase()
        bValue = b.name.toLowerCase()
      } else if (key === 'team') {
        aValue = a.team.toLowerCase()
        bValue = b.team.toLowerCase()
      } else {
        // It's a stat
        aValue = parseFloat(a.stats[key] || 0)
        bValue = parseFloat(b.stats[key] || 0)
      }
      
      if (direction === 'asc') {
        return aValue > bValue ? 1 : -1
      } else {
        return aValue < bValue ? 1 : -1
      }
    })
    
    setPlayers(sortedPlayers)
  }

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) {
      return '↕️'
    }
    return sortConfig.direction === 'asc' ? '↑' : '↓'
  }

  return (
    <div className="app">
      <div className="header">
        <button className="home-button" onClick={goBack}>← Back</button>
        <h1>{currentPosition.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} Stats</h1>
      </div>

      <div className="season-selector">
        <label htmlFor="season">Season:</label>
        <select 
          id="season" 
          value={selectedSeason} 
          onChange={(e) => setSelectedSeason(e.target.value)}
        >
          <option value="2025">2025</option>
          <option value="2024">2024</option>
          <option value="2023">2023</option>
          <option value="2022">2022</option>
        </select>
      </div>

      {loading ? (
        <div className="stats-loading">
          <p>Loading {currentPosition} stats...</p>
        </div>
      ) : error ? (
        <div className="stats-loading">
          <p>Error: {error}</p>
        </div>
      ) : players.length > 0 ? (
        <div className="position-stats">
          <table className="stats-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('rank')} className="sortable">
                  Rank {getSortIcon('rank')}
                </th>
                <th onClick={() => handleSort('name')} className="sortable">
                  Player {getSortIcon('name')}
                </th>
                <th onClick={() => handleSort('team')} className="sortable">
                  Team {getSortIcon('team')}
                </th>
                <th>#</th>
                {keyStats.map(stat => (
                  <th key={stat} onClick={() => handleSort(stat)} className="sortable">
                    {formatStatName(stat)} {getSortIcon(stat)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map(player => (
                <tr 
                  key={player.athlete_id}
                  className={selectedPlayerId && player.athlete_id === selectedPlayerId ? 'highlighted-player' : ''}
                >
                  <td>{player.rank}</td>
                  <td className="player-name">{player.name}</td>
                  <td>{player.team}</td>
                  <td>{player.jersey || 'N/A'}</td>
                  {keyStats.map(stat => (
                    <td key={stat}>
                      {formatStatValue(player.stats[stat] || 0, stat)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="stats-loading">
          <p>No stats available for {currentPosition} in {selectedSeason} season.</p>
        </div>
      )}

      <style jsx>{`
        .app {
          max-width: 1200px;
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

        .season-selector {
          margin-bottom: 20px;
          text-align: center;
        }

        .season-selector label {
          margin-right: 10px;
          font-weight: bold;
          color: white;
        }

        .season-selector select {
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
        }

        .position-stats {
          overflow-x: auto;
        }

        .stats-table {
          width: 100%;
          max-width: 900px;
          margin: 0 auto 32px auto;
          border-collapse: separate;
          border-spacing: 0;
          background: linear-gradient(145deg, #1a1a1a, #2d2d2d);
          border-radius: 16px;
          overflow: hidden;
          box-shadow: 
            0 8px 32px rgba(0, 0, 0, 0.3),
            0 2px 8px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }

        .stats-table th {
          padding: 20px 16px;
          text-align: center;
          background: linear-gradient(135deg, #2a2a2a, #1f1f1f);
          font-weight: 600;
          color: #e0e0e0;
          font-size: 14px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stats-table th:first-child {
          border-top-left-radius: 16px;
        }

        .stats-table th:last-child {
          border-top-right-radius: 16px;
        }

        .sortable {
          cursor: pointer;
          user-select: none;
        }

        .sortable:hover {
          background: linear-gradient(135deg, #3a3a3a, #2f2f2f);
        }

        .stats-table td {
          padding: 20px 16px;
          text-align: center;
          background-color: rgba(26, 26, 26, 0.8);
          color: #f0f0f0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          transition: all 0.2s ease;
          font-size: 15px;
        }

        .stats-table tbody tr {
          transition: all 0.3s ease;
        }

        .stats-table tbody tr:hover {
          background: linear-gradient(135deg, rgba(45, 45, 45, 0.9), rgba(35, 35, 35, 0.9));
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .stats-table tbody tr:hover td {
          background-color: transparent;
          color: #ffffff;
        }

        .player-name {
          font-weight: bold;
          text-align: left !important;
        }

        .highlighted-player td {
          background-color: rgba(79, 195, 247, 0.25) !important;
          color: #81d4fa !important;
          font-weight: 600;
        }

        .highlighted-player {
          background: linear-gradient(135deg, rgba(79, 195, 247, 0.25), rgba(33, 150, 243, 0.15)) !important;
          border-left: 4px solid #4fc3f7;
        }

        .highlighted-player:hover {
          background: linear-gradient(135deg, rgba(79, 195, 247, 0.35), rgba(33, 150, 243, 0.25)) !important;
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(79, 195, 247, 0.3), 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .highlighted-player:hover td {
          color: #b3e5fc !important;
          text-shadow: 0 0 8px rgba(79, 195, 247, 0.4);
        }

        .stats-loading {
          text-align: center;
          padding: 40px;
          color: #ccc;
          font-style: italic;
        }
      `}</style>
    </div>
  )
}

export default PositionStats
