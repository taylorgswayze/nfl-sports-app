import { useEffect, useMemo, useState } from 'react'
import { gameService } from '../api'
import { Masthead, Folio, Footnotes, Colophon } from './Almanac'

/* The Draft Desk board: the model's player values printed as an almanac
   table. Data comes from the federated Draft Room service; the v1/v2
   toggle switches which model orders the board and which value column
   prints in the final position. */

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE']

function DraftBoard() {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState(null)
  const [model, setModel] = useState('v1')
  const [pos, setPos] = useState('ALL')
  const [query, setQuery] = useState('')

  useEffect(() => {
    let alive = true
    gameService.fetchDraftBoard()
      .then((d) => { if (alive) setBoard(d) })
      .catch((err) => { if (alive) setError(err.message) })
    return () => { alive = false }
  }, [])

  const players = useMemo(() => {
    if (!board?.players) return []
    let rows = [...board.players]
    if (model === 'v2') {
      rows.sort((a, b) => (a.v2_rank ?? 999) - (b.v2_rank ?? 999))
    } else {
      rows.sort((a, b) => (a.board_rank ?? 999) - (b.board_rank ?? 999))
    }
    if (pos !== 'ALL') rows = rows.filter((p) => p.pos === pos)
    const q = query.trim().toLowerCase()
    if (q) rows = rows.filter((p) => p.name.toLowerCase().includes(q))
    return rows
  }, [board, model, pos, query])

  const engineControl = (
    <label className="ctl">
      <span className="lbl">ENGINE</span>
      <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model">
        <option value="v1">V1 · POINTS</option>
        <option value="v2">V2 · ROSTER VALUE</option>
      </select>
      <span className="car" aria-hidden="true">&#9662;</span>
    </label>
  )

  return (
    <>
      <Masthead vol="The Draft Desk" stamp={board?.generated} controls={null} />

      <section aria-labelledby="sec-board">
        <Folio sec="THE DRAFT DESK" id="sec-board" title="The Board"
          cont={board ? `${board.season} · ${board.scoring}${board.generated ? ` · values as of ${board.generated}` : ''}` : null} />
        <p className="folio-note">
          {board?.models?.[model] || 'Model-driven player values for the coming season.'}
        </p>

        <div className="boardbar">
          <div className="posset" role="group" aria-label="Position filter">
            {POSITIONS.map((p) => (
              <button key={p} type="button"
                className={p === pos ? 'cur' : undefined}
                aria-pressed={p === pos}
                onClick={() => setPos(p)}>{p}</button>
            ))}
          </div>
          <input className="boardsearch" type="search" placeholder="Search player&hellip;"
            value={query} onChange={(e) => setQuery(e.target.value)}
            aria-label="Search player" />
          {engineControl}
        </div>

        {error ? (
          <p className="wire">COULD NOT LOAD THE BOARD: <b>{error}</b>. Reload the page to try again.</p>
        ) : !board ? (
          <p className="wire">LOADING THE BOARD&hellip; <b>stand by</b></p>
        ) : (
          <div className="tablewrap">
            <table className="stats">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col" className="txt">PLAYER</th>
                  <th scope="col">POS</th>
                  <th scope="col">POS#</th>
                  <th scope="col">MARKET</th>
                  <th scope="col">PROJ PPG</th>
                  <th scope="col">PROJ TOTAL</th>
                  <th scope="col">RANGE P10&ndash;P90</th>
                  <th scope="col">EXP G</th>
                  <th scope="col">{model === 'v2' ? 'VALUE (EV)' : 'VALUE (VBD)'}</th>
                </tr>
              </thead>
              <tbody>
                {players.map((p) => (
                  <tr key={p.name}>
                    <td className="n">{model === 'v2' ? p.v2_rank : p.board_rank}</td>
                    <td className="txt player">{p.name}</td>
                    <td className="team">{p.pos}</td>
                    <td className="n">{p.pos}{p.pos_rank}</td>
                    <td className="n">{p.ecr ?? '–'}</td>
                    <td className="n">{p.proj_ppg}</td>
                    <td className="n">{p.proj_total}</td>
                    <td className="n">{p.ml_p10} to {p.ml_p90}</td>
                    <td className="n">{p.exp_games}</td>
                    <td className="n sortcol">{model === 'v2' ? p.v2_ev : p.vbd_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Footnotes>
          {board?.backtest && <p>{board.backtest}</p>}
          <p>Market is the consensus rank. Range prints the model&rsquo;s 10th to 90th
            percentile season outcomes; EXP G is expected games available.</p>
        </Footnotes>
      </section>

      <Colophon center="The Draft Desk · The Board" />
    </>
  )
}

export default DraftBoard
