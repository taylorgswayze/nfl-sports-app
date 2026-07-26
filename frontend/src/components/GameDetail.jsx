import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { gameService } from '../api'
import { isNumberLike } from '../utils'
import { Masthead, Folio, Chip, Footnotes, Colophon, ProbGauge } from './Almanac'

/* The game desk: one game's almanac page. Header prints the matchup as an
   oversized entry; below it, the head-to-head ledger: away figures left,
   the measure down the spine, home figures right, the leading side set in
   bone-bold with a green tick toward the spine. */

function TeamPlate({ team, side }) {
  return (
    <div className={`gd-team ${side}`}>
      <Chip lg file={team.logo} to={`/team/${team.team_id}`}
        label={`View ${team.name} schedule`} />
      <div className="gd-id">
        <span className="gd-abbr">{team.abbr}</span>
        <span className="gd-name">{team.name}</span>
        {team.record && <span className="gd-rec num">{team.record}</span>}
      </div>
    </div>
  )
}

function H2HRow({ row, mixedScope }) {
  const awayLeads = row.better === 'away'
  const homeLeads = row.better === 'home'
  return (
    <tr>
      <td className={`v away${awayLeads ? ' lead' : ''}`}>
        {row.away}
        <span className="tick" aria-hidden={awayLeads ? undefined : 'true'}>
          {awayLeads ? '✓' : ''}
        </span>
      </td>
      <th scope="row" className="lbl">
        {row.label}
        {mixedScope && row.scope === 'to_kickoff' && <span className="mark">&deg;</span>}
      </th>
      <td className={`v home${homeLeads ? ' lead' : ''}`}>
        <span className="tick" aria-hidden={homeLeads ? undefined : 'true'}>
          {homeLeads ? '✓' : ''}
        </span>
        {row.home}
      </td>
    </tr>
  )
}

function GameDetail() {
  const { eventId } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    setData(null)
    gameService.fetchMatchup(eventId)
      .then((d) => { if (alive) setData(d) })
      .catch((err) => { if (alive) setError(err.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [eventId])

  const controls = (
    <Link className="ctl" to="/">
      <span className="lbl">BACK TO</span> <span>FRONT PAGE</span>
    </Link>
  )

  if (loading || error || !data) {
    return (
      <>
        <Masthead vol="Game Desk" controls={controls} />
        {loading ? (
          <p className="wire" style={{ marginTop: 42 }}>LOADING THE GAME&hellip; <b>stand by</b></p>
        ) : (
          <p className="wire" style={{ marginTop: 42 }}>
            COULD NOT LOAD THIS GAME: <b>{error || 'no game data'}</b>. Reload the page to try again.
          </p>
        )}
        <Colophon />
      </>
    )
  }

  const away = data.away_team
  const home = data.home_team
  const final = data.status === 'final'
    && isNumberLike(data.away_score) && isNumberLike(data.home_score)
  const awayScore = Number(data.away_score)
  const homeScore = Number(data.home_score)
  const awayWon = final && awayScore > homeScore
  const homeWon = final && homeScore > awayScore
  const hasProbs = isNumberLike(data.away_win_prob) && isNumberLike(data.home_win_prob)
  const hasOdds = data.odds && data.odds !== 'N/A'
  const rows = data.h2h || []
  const mixedScope = data.stats_scope === 'to_kickoff'
  const seasonNote = data.stats_note || ''
  const weekLabel = data.season_type_id === 3
    ? `Postseason, Round ${data.week_num}`
    : `Week ${data.week_num}`

  return (
    <>
      <Masthead vol="Game Desk" controls={controls} />

      <section aria-labelledby="sec-game">
        <Folio
          sec="THE GAME"
          id="sec-game"
          title={`${away.abbr} at ${home.abbr}`}
          cont={`${weekLabel} · ${data.season} Season`}
        />
        <p className="folio-note">
          {final
            ? <>Final. Kicked off {data.game_datetime}{hasOdds && <>; the line closed <span className="num">{data.odds}</span></>}.</>
            : <>Kickoff {data.game_datetime}{hasOdds && <>; current line <span className="num">{data.odds}</span></>}.</>}
        </p>

        <div className="gd-head">
          <TeamPlate team={away} side="away" />
          <div className="gd-mid">
            {final ? (
              <>
                <span className="final-flag">{String(data.status || 'Final').toUpperCase()}</span>
                <div className="gd-score num" aria-label={`Final score ${away.abbr} ${awayScore}, ${home.abbr} ${homeScore}`}>
                  <span className={awayWon ? 'win' : 'lose'}>{awayScore}</span>
                  <span className="gd-dash">&ndash;</span>
                  <span className={homeWon ? 'win' : 'lose'}>{homeScore}</span>
                </div>
              </>
            ) : (
              <>
                <span className="gd-at">at</span>
                {hasOdds && (
                  <div className="gd-fig">
                    <span className="flbl">LINE</span>
                    <span className="fval num">{data.odds}</span>
                  </div>
                )}
              </>
            )}
          </div>
          <TeamPlate team={home} side="home" />
        </div>
        {hasProbs && !final && (
          <div className="gd-prob">
            <ProbGauge awayAbbr={away.abbr} homeAbbr={home.abbr}
              awayPct={data.away_win_prob} homePct={data.home_win_prob} />
          </div>
        )}
      </section>

      <section aria-labelledby="sec-h2h">
        <Folio sec="THE LEDGER" id="sec-h2h" title="Head to Head" cont={seasonNote} />
        <p className="folio-note">
          Figures cover the {seasonNote}. The leading side of each measure is set
          in bold with a green tick.
        </p>

        {rows.length > 0 ? (
          <div className="tablewrap h2h-wrap">
            <table className="h2h">
              <thead>
                <tr>
                  <th scope="col" className="side away">
                    <span className="h2h-team">
                      <Chip file={away.logo} to={`/team/${away.team_id}`}
                        label={`View ${away.name} schedule`} />
                      <span className="num">{away.abbr}</span>
                    </span>
                  </th>
                  <th scope="col" className="lblhead"><span>Measure</span></th>
                  <th scope="col" className="side home">
                    <span className="h2h-team">
                      <span className="num">{home.abbr}</span>
                      <Chip file={home.logo} to={`/team/${home.team_id}`}
                        label={`View ${home.name} schedule`} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <H2HRow key={row.key} row={row} mixedScope={mixedScope} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="wire">
            NO FIGURES ON FILE for either side in the {data.stats_season} season.
          </p>
        )}

        <Footnotes>
          {mixedScope && (
            <p>
              <span className="mark">&deg;</span> Figured from final scores only, using
              games completed before this kickoff in the {data.stats_season} season.
              Records include the postseason.
            </p>
          )}
          {!mixedScope && rows.length > 0 && (
            <p>
              Neither side had completed a {data.season} game before kickoff, so all
              figures come from the full {data.stats_season} season. Records include
              the postseason.
            </p>
          )}
          <p>
            Season statistics come from the ESPN feed for the {data.stats_season} season.
            A measure missing a real figure on either side is left out of the table,
            never estimated.
          </p>
        </Footnotes>
      </section>

      <Colophon center={`${away.abbr} at ${home.abbr} · ${weekLabel}, ${data.season}`} />
    </>
  )
}

export default GameDetail
