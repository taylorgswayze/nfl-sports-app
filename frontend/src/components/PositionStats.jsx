import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { get } from '../api'
import { Masthead, Folio, Footnotes, Colophon } from './Almanac'

function PositionStats({ position: propPosition, selectedPlayerId: propSelectedPlayerId }) {
  const { position } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const currentPosition = propPosition || position
  const selectedPlayerId = propSelectedPlayerId || location.state?.selectedPlayerId

  const [players, setPlayers] = useState([])
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
      setPlayers(data.players || [])
      setKeyStats(data.key_stats || [])
      setSortConfig({ key: 'rank', direction: 'asc' })
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
    return Math.round(value).toLocaleString('en-US')
  }

  const handleSort = (key) => {
    let direction = 'desc'
    if (key === 'rank' || key === 'name' || key === 'team') direction = 'asc'
    if (sortConfig.key === key && sortConfig.direction === direction) {
      direction = direction === 'desc' ? 'asc' : 'desc'
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

  const sortCar = (key) => {
    if (sortConfig.key !== key) return null
    return (
      <span className="sort-car" aria-hidden="true">
        {sortConfig.direction === 'asc' ? '▲' : '▼'}
      </span>
    )
  }

  const ariaSort = (key) => {
    if (sortConfig.key !== key) return undefined
    return sortConfig.direction === 'asc' ? 'ascending' : 'descending'
  }

  const positionTitle = currentPosition
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())

  const SortableTh = ({ colKey, children, txt, sourceKey }) => (
    <th
      scope="col"
      className={`${txt ? 'txt ' : ''}${sortConfig.key === colKey ? 'sorted' : ''}`.trim() || undefined}
      aria-sort={ariaSort(colKey)}
    >
      <button type="button" onClick={() => handleSort(colKey)}>
        {children} {sortCar(colKey)}
      </button>
      {sourceKey ? <span className="was">{sourceKey}</span> : null}
    </th>
  )

  return (
    <>
      <Masthead
        vol="Sec 3 — Position Leaders — Night Ed."
        controls={
          <>
            <button className="ctl" type="button" onClick={goBack}>
              <span className="lbl">RETURN</span> <span>ONE PAGE BACK</span>
            </button>
            <label className="ctl">
              <span className="lbl">SEASON</span>
              <select
                value={selectedSeason}
                onChange={(e) => setSelectedSeason(e.target.value)}
                aria-label="Season"
              >
                <option value="2025">2025</option>
                <option value="2024">2024</option>
                <option value="2023">2023</option>
                <option value="2022">2022</option>
              </select>
              <span className="car" aria-hidden="true">&#9662;</span>
            </label>
          </>
        }
      />

      <section aria-labelledby="sec-leaders">
        <Folio
          sec="SEC 3"
          id="sec-leaders"
          title={`Position Leaders — ${positionTitle}`}
          cont={`${selectedSeason} Season`}
        />
        <p className="folio-note">
          Raw feed keys are translated to printed labels; the mono line under each header
          names its source key. Click a header to re-sort the table.
        </p>

        {loading ? (
          <p className="wire">RANKING THE LEAGUE&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">WIRE FAULT &mdash; <b>{error}</b>. Reload to re-request the feed.</p>
        ) : players.length > 0 ? (
          <div className="tablewrap">
            <table className="stats">
              <thead>
                <tr>
                  <SortableTh colKey="rank">Rk</SortableTh>
                  <SortableTh colKey="name" txt>Player</SortableTh>
                  <SortableTh colKey="team" txt>Team</SortableTh>
                  <th scope="col">No.</th>
                  {keyStats.map(stat => (
                    <SortableTh key={stat} colKey={stat} sourceKey={stat}>
                      {formatStatName(stat)}
                    </SortableTh>
                  ))}
                </tr>
              </thead>
              <tbody>
                {players.map(player => {
                  const isLeader = player.rank === 1
                  const isSelected = selectedPlayerId && player.athlete_id === selectedPlayerId
                  return (
                    <tr
                      key={player.athlete_id}
                      className={isLeader ? 'leader' : undefined}
                      style={isSelected ? { outline: '1px solid var(--green)', outlineOffset: '-1px' } : undefined}
                    >
                      <td className={`n${sortConfig.key === 'rank' ? ' sortcol' : ''}`}>{player.rank}</td>
                      <td className="txt player">
                        {player.name}
                        {isLeader && <span className="mark" title="League leader">*</span>}
                      </td>
                      <td className="txt team">{player.team}</td>
                      <td className="n">{player.jersey || '—'}</td>
                      {keyStats.map(stat => (
                        <td key={stat} className={`n${sortConfig.key === stat ? ' sortcol' : ''}`}>
                          {formatStatValue(player.stats[stat] || 0, stat)}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="wire">
            NO FIGURES on file for <b>{positionTitle}</b> in the <b>{selectedSeason}</b> season.
          </p>
        )}

        <Footnotes>
          <p><span className="mark">*</span> League leader at the position, {selectedSeason} season to date.</p>
        </Footnotes>
      </section>

      <Colophon center={positionTitle} />
    </>
  )
}

export default PositionStats
