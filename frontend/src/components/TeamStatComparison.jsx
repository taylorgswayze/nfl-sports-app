import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { gameService } from '../api'
import { getLogoUrl } from '../utils'
import './TeamStatComparison.css'

function TeamStatComparison() {
  const { statName } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const selectedTeamId = location.state?.selectedTeamId

  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statInfo, setStatInfo] = useState({})

  useEffect(() => {
    if (statName) {
      loadTeamStatComparison()
    }
  }, [statName])

  const loadTeamStatComparison = async () => {
    try {
      setLoading(true)
      const data = await gameService.fetchTeamStatComparison(statName)
      setTeams(data.teams || [])
      setStatInfo({
        name: data.stat_name,
        season: data.season,
        totalTeams: data.total_teams
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const goBack = () => {
    if (selectedTeamId) {
      navigate(`/team/${selectedTeamId}`)
    } else {
      navigate(-1)
    }
  }

  const handleTeamClick = (teamId) => {
    navigate(`/team/${teamId}`)
  }

  const formatStatName = (statName) => {
    return statName.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())
  }

  if (loading) {
    return (
      <div className="app">
        <div className="header">
          <button className="back-button" onClick={goBack}>← Back</button>
          <h1>Loading Team Comparison...</h1>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app">
        <div className="header">
          <button className="back-button" onClick={goBack}>← Back</button>
          <h1>Error Loading Data</h1>
        </div>
        <p>Error: {error}</p>
      </div>
    )
  }

  return (
    <div className="app">
      <div className="header">
        <button className="back-button" onClick={goBack}>← Back</button>
        <h1>{formatStatName(statInfo.name)} - Team Comparison</h1>
      </div>
      
      <div className="stat-comparison-info">
        <p>Season: {statInfo.season} | Teams: {statInfo.totalTeams}</p>
      </div>

      <div className="team-stat-table">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Team</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => (
              <tr 
                key={team.team_id} 
                className={selectedTeamId && parseInt(selectedTeamId) === team.team_id ? 'highlighted-team' : ''}
              >
                <td>{team.display_rank}</td>
                <td>
                  <div className="team-cell">
                    <img 
                      className="team-logo-small" 
                      src={getLogoUrl(team.short_name)} 
                      alt={team.team_name} 
                    />
                    <a 
                      href="#" 
                      className="team-link"
                      onClick={(e) => { 
                        e.preventDefault(); 
                        handleTeamClick(team.team_id);
                      }}
                    >
                      {team.team_name}
                    </a>
                  </div>
                </td>
                <td>{team.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default TeamStatComparison
