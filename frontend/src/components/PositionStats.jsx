import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { get, fetchSeasonsCached } from '../api'
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
  const [seasons, setSeasons] = useState([])
  const [selectedSeason, setSelectedSeason] = useState(null)
  const [keyStats, setKeyStats] = useState([])
  const [sortConfig, setSortConfig] = useState({ key: 'rank', direction: 'asc' })

  useEffect(() => {
    fetchSeasonsCached()
      .then((data) => {
        setSeasons((data.seasons || []).map(String))
        setSelectedSeason((prev) => prev ?? String(data.current_season || '2026'))
      })
      .catch(() => setSelectedSeason((prev) => prev ?? '2026'))
  }, [])

  useEffect(() => {
    if (currentPosition && selectedSeason) {
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
        vol="Position Leaders"
        controls={
          <>
            <button className="ctl" type="button" onClick={goBack}>
              <span className="lbl">RETURN</span> <span>PREVIOUS PAGE</span>
            </button>
            <label className="ctl">
              <span className="lbl">SEASON</span>
              <select
                value={selectedSeason || ''}
                onChange={(e) => setSelectedSeason(e.target.value)}
                aria-label="Season"
              >
                {(seasons.length ? seasons : [selectedSeason].filter(Boolean)).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <span className="car" aria-hidden="true">&#9662;</span>
            </label>
          </>
        }
      />

      <section aria-labelledby="sec-leaders">
        <Folio
          sec="LEADERS"
          id="sec-leaders"
          title={positionTitle}
          cont={selectedSeason ? `${selectedSeason} Season` : null}
        />
        <p className="folio-note">
          Players ranked by combined production. The small line under a stat header
          names the stat as the data feed keeps it. Select any header to sort the table.
        </p>

        {loading ? (
          <p className="wire">LOADING THE LEADERS&hellip; <b>stand by</b></p>
        ) : error ? (
          <p className="wire">COULD NOT LOAD THE LEADERS: <b>{error}</b>. Reload the page to try again.</p>
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
                      <td className="n">{player.jersey || '–'}</td>
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
            NO STATS ON FILE for <b>{positionTitle}</b> in the <b>{selectedSeason}</b> season.{' '}
            <b>Pick another season above.</b>
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
