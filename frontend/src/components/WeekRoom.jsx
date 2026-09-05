import { useState } from 'react'
import { Link } from 'react-router-dom'

/* THE WEEK ROOM: the Desk's roster note for one league, printed at the top
   of its card. Deterministic engine output (optimal lineup, waiver claims
   with the drop named, trade ideas with both sides' deltas) plus a few
   sentences of prose, refreshed every 12 hours. */

function fmt(v, signed = false) {
  if (v == null) return '–'
  const n = Number(v)
  const s = Math.abs(n).toFixed(1)
  if (!signed) return s
  return n < 0 ? `-${s}` : `+${s}`
}

function stamp(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

function who(p) {
  if (!p) return '–'
  const bits = [p.pos, p.team || 'FA'].filter(Boolean).join(', ')
  return <><b>{p.name}</b> <span className="wr-meta num">({bits})</span></>
}

function Tag({ kind, children }) {
  return <span className={`wr-tag ${kind}`}>{children}</span>
}

function Prose({ text }) {
  if (!text) return null
  return text.split(/\n+/).filter(Boolean).map((para, i) => <p key={i} className="wr-prose">{para}</p>)
}

export function WeekRoomPending({ state }) {
  return (
    <div className="wr wr-pending">
      <div className="wr-head">
        <span className="wr-kicker">THE GENERAL MANAGER</span>
      </div>
      <p className="wire wr-wire">
        {state === 'generating'
          ? <>THE GM IS ON THE PHONES: projecting your rosters now. <b>A minute at most.</b></>
          : state === 'error'
            ? <>NO NOTE FROM THE GM for this league. <b>It retries at the next refresh.</b></>
            : <>PULLING THE GM'S NOTE…</>}
      </p>
    </div>
  )
}

export default function WeekRoom({ ins, onReprint, reprinting }) {
  const [showLineup, setShowLineup] = useState(false)
  if (!ins) return null
  const preDraft = ins.status === 'pre_draft' || ins.status === 'drafting'
  const lu = ins.lineup || {}
  const m = ins.matchup
  const moves = lu.moves || []
  const waivers = ins.waivers || []
  const trades = ins.trades || []
  const printed = stamp(ins.generated_at)

  let lede
  if (ins.error) lede = 'NO REPORT'
  else if (preDraft) lede = 'DRAFT PENDING'
  else if (lu.material) lede = `${fmt(lu.gain, true)} POINTS ON THE TABLE`
  else lede = 'THE CARD STANDS'

  return (
    <div className={`wr${lu.material ? ' hot' : ''}`}>
      <div className="wr-head">
        <span className="wr-kicker">THE GENERAL MANAGER{ins.week ? ` · WEEK ${ins.week}` : ''}</span>
        <span className="wr-stamp num">
          {printed ? `printed ${printed}` : ''}{ins.refresh_hours ? ` · every ${ins.refresh_hours}h` : ''}
        </span>
      </div>

      <p className="wr-lede num">{lede}</p>
      {m && (
        <p className="wr-match num">
          Projects <b>{fmt(m.my_total)}</b> to <b>{fmt(m.opp_total)}</b> against {m.opp_name || 'your opponent'}
          {m.my_current != null && m.my_total != null && Math.abs(m.my_total - m.my_current) >= 0.75
            ? <> (<b>{fmt(m.my_current)}</b> as set)</> : null}.
        </p>
      )}

      <Prose text={ins.narrative} />

      {preDraft && (
        <Link className="ctl advlink" to="/draft/advisor">
          <span className="lbl">OPEN</span> LIVE ADVISOR
        </Link>
      )}

      {moves.length > 0 && (
        <>
          <p className="wr-sub">LINEUP CARD <span className="num">{moves.length} move{moves.length === 1 ? '' : 's'} to the optimal lineup</span></p>
          <div className="tablewrap">
            <table className="stats wr-tbl">
              <thead>
                <tr>
                  <th scope="col" className="txt">PLAYER</th>
                  <th scope="col">POS</th>
                  <th scope="col">FROM</th>
                  <th scope="col">TO</th>
                  <th scope="col">PROJ</th>
                </tr>
              </thead>
              <tbody>
                {moves.map((m) => (
                  <tr key={m.player_id} className={m.to === 'BN' ? 'wr-out' : 'wr-in'}>
                    <td className="txt player">{m.name}</td>
                    <td className="team">{m.pos || '–'}</td>
                    <td className="team">{m.from}</td>
                    <td className="team to">{m.to}</td>
                    <td className="n">{fmt(m.proj)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {waivers.length > 0 && (
        <>
          <p className="wr-sub">THE WIRE <span className="num">claims and releases, with the projected upside</span></p>
          <div className="tablewrap">
            <table className="stats wr-tbl">
              <thead>
                <tr>
                  <th scope="col" className="txt">CLAIM</th>
                  <th scope="col" className="txt">RELEASE</th>
                  <th scope="col">THIS WK<span className="was">pts</span></th>
                  <th scope="col">ROS<span className="was">pts / wk</span></th>
                  <th scope="col" className="txt">NOTE</th>
                </tr>
              </thead>
              <tbody>
                {waivers.map((w, i) => (
                  <tr key={`w${i}`}>
                    <td className="txt player">{w.add.name} <span className="wr-meta">{[w.add.pos, w.add.team].filter(Boolean).join(', ')}</span></td>
                    <td className="txt">{w.drop.name} <span className="wr-meta">{w.drop.pos}</span></td>
                    <td className="n">{fmt(w.week_gain, true)}</td>
                    <td className="n sortcol">{fmt(w.gain, true)}</td>
                    <td className="txt wr-meta">{w.starts ? 'starts now' : 'depth'}{w.trending ? ` · ${Number(w.trending).toLocaleString()} adds` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {trades.length > 0 && (
        <>
          <p className="wr-sub">THE PHONES <span className="num">one for one, both sides scored</span></p>
          <ul className="wr-moves">
            {trades.map((t, i) => (
              <li key={`t${i}`} className="wr-move">
                <Tag kind="send">SEND</Tag> {who(t.send[0])}
                <> <Tag kind="get">GET</Tag> {who(t.receive[0])}</>
                <span className="wr-at">to {t.partner}</span>
                <span className="wr-delta num">{fmt(t.my_delta, true)} you · {fmt(t.their_delta, true)} them</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {!preDraft && !ins.error && (
        <div className="wr-foot">
          <button type="button" className="benchtoggle" onClick={() => setShowLineup((s) => !s)} aria-expanded={showLineup}>
            {showLineup ? 'HIDE THE CARD' : 'FULL LINEUP CARD'}
          </button>
          {onReprint && (
            <button type="button" className="benchtoggle" onClick={onReprint} disabled={reprinting}>
              {reprinting ? 'REPRINTING…' : 'REPRINT NOW'}
            </button>
          )}
          {ins.waiver?.type && (
            <span className="wr-rules num">
              {ins.waiver.type}{ins.waiver.position ? ` · you claim #${ins.waiver.position}` : ''}
              {ins.waiver.budget_left != null ? ` · $${ins.waiver.budget_left} left` : ''}
              {ins.waiver.runs ? ` · runs ${ins.waiver.runs}` : ''}
            </span>
          )}
        </div>
      )}

      {showLineup && lu.lineup?.length > 0 && (
        <div className="tablewrap">
          <table className="stats wr-lineup">
            <thead>
              <tr>
                <th scope="col" className="txt">SLOT</th>
                <th scope="col" className="txt">PLAYER</th>
                <th scope="col">POS</th>
                <th scope="col">TEAM</th>
                <th scope="col">OPP</th>
                <th scope="col">PROJ</th>
              </tr>
            </thead>
            <tbody>
              {lu.lineup.map((p, i) => (
                <tr key={`${p.slot}-${i}`} className={p.injury ? 'wr-flag' : undefined}>
                  <td className="txt team">{p.slot}</td>
                  <td className="txt player">{p.name}{p.injury ? <span className="mark"> {p.injury[0]}</span> : null}</td>
                  <td className="team">{p.pos || '–'}</td>
                  <td className="team">{p.team || 'FA'}</td>
                  <td className="team">{p.opp || '–'}</td>
                  <td className="n sortcol">{fmt(p.proj)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {ins.projection_note && <p className="note wr-note">{ins.projection_note}</p>}
        </div>
      )}
    </div>
  )
}
