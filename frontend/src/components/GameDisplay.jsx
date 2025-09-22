import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { getLogoUrl } from '../utils'
import './GameDisplay.css'

function GameDisplay() {
  const navigate = useNavigate()
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [weeks, setWeeks] = useState([])
  const [currentWeek, setCurrentWeek] = useState({})
  const [selectedWeek, setSelectedWeek] = useState({})

  useEffect(() => {
    fetchGamesForWeek()
  }, [])

  const fetchGamesForWeek = async (weekNum = null) => {
    setLoading(true)
    setError(null)

    try {
      const data = await gameService.fetchGames(weekNum)
      console.log("Fetched data:", data)

      setGames(data.games || [])
      setWeeks(data.weeks || [])
      setCurrentWeek(data.current_week || {})
      setSelectedWeek(data.current_week || data.weeks[0] || {})
    } catch (err) {
      console.error("Error fetching games:", err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleWeekChange = (event) => {
    const selectedWeekName = event.target.value
    const week = weeks.find((w) => w.name === selectedWeekName)
    setSelectedWeek(week)
    console.log("Selected week:", week)

    if (week && week.week_num) {
      fetchGamesForWeek(week.week_num)
    }
  }

  const handleTeamClick = (team_id) => {
    navigate(`/team/${team_id}`)
  }

  return (
    <div className="app">
      <div className="header">
        <h1>Games for {selectedWeek?.name || 'Loading...'}</h1>
      </div>

      <div className="week-selector">
        <label htmlFor="week">Select Week:</label>
        <select
          id="week"
          value={selectedWeek.name || ''}
          onChange={handleWeekChange}
        >
          {weeks.map((week) => (
            <option
              key={week.name}
              value={week.name}
            >
              {week.name}
            </option>
          ))}
        </select>
      </div>

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
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          handleTeamClick(game.away_team_id)
                        }}
                      >
                        <img
                          className="team-logo"
                          src={getLogoUrl(game.away_team_logo)}
                          alt={game.away_team}
                        />
                      </a>
                      <div className="team-name">
                        <a
                          href="#"
                          onClick={(e) => {
                            e.preventDefault()
                            handleTeamClick(game.away_team_id)
                          }}
                        >
                          {game.away_team}
                        </a>
                      </div>
                      <div className="win-prob">
                        ({game.away_team_record})<br />
                        Win Prob: {game.away_win_prob}%
                      </div>
                    </div>

                    <div className="team-box">
                      {game.game_datetime}<br />{game.odds}<br />
                      <sup>Last updated: {game.odds_last_updated}</sup>
                    </div>

                    <div className="team-box">
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          handleTeamClick(game.home_team_id)
                        }}
                      >
                        <img
                          className="team-logo"
                          src={getLogoUrl(game.home_team_logo)}
                          alt={game.home_team}
                        />
                      </a>
                      <div className="team-name">
                        <a
                          href="#"
                          onClick={(e) => {
                            e.preventDefault()
                            handleTeamClick(game.home_team_id)
                          }}
                        >
                          {game.home_team}
                        </a>
                      </div>
                      <div className="win-prob">
                        ({game.home_team_record})<br />
                        Win Prob: {game.home_win_prob}%
                      </div>
                    </div>
                  </div>
                </li>
              </div>
            ))}
          </ul>
        ) : (
          <p>No games available.</p>
        )}
      </div>
    </div>
  )
}

export default GameDisplay
