import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { gameService } from '../api'
import { getTeamLogoFile } from '../utils'
import { Masthead, Folio, Chip, Footnotes, Colophon } from './Almanac'

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

  const formatStatName = (name) => {
    if (!name) return 'Team Figure'
    return name.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, str => str.toUpperCase())
  }

  const printedName = formatStatName(statInfo.name || statName)

  return (
    <>
      <Masthead
        vol="Sec 4 — League Table — Night Ed."
        controls={
          <button className="ctl" type="button" onClick={goBack}>
            <span className="lbl">RETURN TO</span> <span>THE TEAM DESK</span>
          </button>
        }
      />

      <section aria-labelledby="sec-league">
        <Folio
          sec="SEC 4"
          id="sec-league"
          title={`League Table — ${printedName}`}
          cont={statInfo.season ? `${statInfo.season} Season` : null}
          pg={statInfo.totalTeams ? `${statInfo.totalTeams} clubs` : null}
        />
        <p className="folio-note">
          Every club ranked by <span className="num">{printedName}</span>.
          The first line holds the league lead{selectedTeamId ? '; your club is ruled in green' : ''}.
        </p>

        {loading ? (
          <p className="wire">RANKING THE LEAGUE&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">WIRE FAULT &mdash; <b>{error}</b>. Reload to re-request the feed.</p>
        ) : (
          <div className="tablewrap">
            <table className="stats">
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col" className="txt">Team</th>
                  <th scope="col">
                    Value
                    <span className="was">{statInfo.name || statName}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {teams.map((team) => {
                  const isSelected = selectedTeamId && parseInt(selectedTeamId) === team.team_id
                  const isLeader = team.rank === 1 || team.display_rank === '1st'
                  return (
                    <tr
                      key={team.team_id}
                      className={isLeader ? 'leader' : undefined}
                      style={isSelected ? { outline: '1px solid var(--green)', outlineOffset: '-1px' } : undefined}
                    >
                      <td className="n">{team.display_rank}</td>
                      <td className="txt player">
                        <span className="cell-chip">
                          <Chip file={getTeamLogoFile(team.team_id)} />
                          <Link to={`/team/${team.team_id}`}>
                            {team.team_name}
                            {isLeader && <span className="mark" title="League leader">*</span>}
                          </Link>
                        </span>
                      </td>
                      <td className="n sortcol">{team.value}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <Footnotes>
          <p><span className="mark">*</span> League leader in {printedName.toLowerCase()}, {statInfo.season || 'current'} season to date.</p>
        </Footnotes>
      </section>

      <Colophon center={printedName} />
    </>
  )
}

export default TeamStatComparison
