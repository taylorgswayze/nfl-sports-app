import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { gameService } from '../api'
import { Masthead, Folio, Chip, Footnotes, Colophon } from './Almanac'

/* THE STANDINGS: the league table, conference by conference, division by
   division, straight from the wire with a five-minute cache. */

function DivisionTable({ division }) {
  const navigate = useNavigate()
  return (
    <div>
      <h3 className="subhead">
        {division.name} <span className="count num">{division.teams.length}</span>
      </h3>
      <div className="tablewrap">
        <table className="stats">
          <thead>
            <tr>
              <th scope="col" className="txt">Team</th>
              <th scope="col">W</th>
              <th scope="col">L</th>
              <th scope="col">T</th>
              <th scope="col">PCT</th>
              <th scope="col">PF</th>
              <th scope="col">PA</th>
              <th scope="col">DIFF</th>
              <th scope="col">STRK</th>
            </tr>
          </thead>
          <tbody>
            {division.teams.map((team, i) => (
              <tr key={team.abbr} className={`clickable${i === 0 ? ' leader' : ''}`}
                tabIndex={0}
                onClick={() => navigate(`/team/${team.team_id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/team/${team.team_id}`)
                  }
                }}>
                <td className="txt player standings-team">
                  <Chip file={team.logo} />
                  <b>{team.abbr}</b>
                  <span className="team standings-name">{team.name}</span>
                </td>
                <td className="n">{team.wins ?? '0'}</td>
                <td className="n">{team.losses ?? '0'}</td>
                <td className="n">{team.ties ?? '0'}</td>
                <td className="n">{team.pct ?? '-'}</td>
                <td className="n">{team.points_for ?? '-'}</td>
                <td className="n">{team.points_against ?? '-'}</td>
                <td className="n">{team.differential ?? '-'}</td>
                <td className="n">{team.streak ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Standings() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    gameService.fetchStandings()
      .then((d) => { if (alive) setData(d) })
      .catch((err) => { if (alive) setError(err.message) })
    return () => { alive = false }
  }, [])

  return (
    <>
      <Masthead vol="The Standings" controls={null} />

      <section aria-labelledby="sec-standings">
        <Folio sec="STANDINGS" id="sec-standings" title="The League Table"
          cont={data?.season ? `${data.season} Season` : null} />
        <p className="folio-note">
          Every division's table, updated as games go final. The green band
          leads its division. Select any row to open that team's desk.
        </p>

        {error ? (
          <p className="wire">COULD NOT LOAD THE STANDINGS: <b>{error}</b>. Reload the page to try again.</p>
        ) : !data ? (
          <p className="wire">LOADING THE STANDINGS&hellip; <b>stand by</b></p>
        ) : (
          data.conferences.map((conference) => (
            <div key={conference.name}>
              <Folio sec="CONFERENCE" title={conference.name} />
              <div className="standings-grid">
                {conference.divisions.map((division) => (
                  <DivisionTable key={division.name} division={division} />
                ))}
              </div>
            </div>
          ))
        )}

        <Footnotes>
          <p>Records, points and streaks come from the league wire and refresh about every five minutes.</p>
        </Footnotes>
      </section>

      <Colophon center={data?.season ? `${data.season} Season` : null} />
    </>
  )
}

export default Standings
