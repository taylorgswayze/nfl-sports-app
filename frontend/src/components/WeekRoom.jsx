import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Verdict } from './TradeDesk'

/* THE GENERAL MANAGER: the GM's note for one league, printed as the lead
   of the league's block. Left, the number that matters (points on the
   table), the projected matchup and the prose; right, the lineup card, the
   wire and the phones as tables. Deterministic engine output plus a few
   sentences, refreshed every 12 hours. */

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

function Prose({ text }) {
  if (!text) return null
  return text.split(/\n+/).filter(Boolean).map((para, i) => <p key={i} className="gm-prose">{para}</p>)
}

export function WeekRoomPending({ state }) {
  return (
    <div className="gm gm-pending">
      <p className="wire">
        {state === 'generating'
          ? <>THE GM IS ON THE PHONES: projecting your rosters now. <b>A minute at most.</b></>
          : state === 'error'
            ? <>NO NOTE FROM THE GM for this league. <b>It retries at the next refresh.</b></>
            : <>PULLING THE GM&rsquo;S NOTE…</>}
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
  const proposals = ins.proposals || []
  const printed = stamp(ins.generated_at)

  if (preDraft || ins.error) {
    return (
      <div className="gm gm-quiet">
        <div className="gm-head">
          <span className="kicker">The GM&rsquo;s note</span>
          <span className="when num">{printed ? `printed ${printed}` : ''}</span>
        </div>
        <p className="gm-lede small">{ins.error ? 'No report' : 'Draft pending'}</p>
        <Prose text={ins.narrative} />
        {preDraft && (
          <Link className="ctl advlink" to="/draft/advisor"><span className="lbl">OPEN</span> LIVE ADVISOR</Link>
        )}
      </div>
    )
  }

  const lede = lu.material ? fmt(lu.gain, true) : 'Set'
  const ledeNote = lu.material
    ? `points on the table with ${moves.length} move${moves.length === 1 ? '' : 's'}`
    : 'the card stands as written'

  return (
    <div className={`gm${lu.material ? ' hot' : ''}`}>
      <div className="gm-head">
        <span className="kicker">The GM&rsquo;s note</span>
        <span className="when num">{printed ? `printed ${printed}` : ''}{ins.refresh_hours ? ` · every ${ins.refresh_hours}h` : ''}</span>
      </div>

      <div className="gm-left">
        <div className={`gm-lede num${lu.material ? '' : ' quiet'}`}>{lede}<small>{ledeNote}</small></div>
        {m && (
          <div className="gm-match num">
            {fmt(m.my_total)} <span>to</span> {fmt(m.opp_total)} <span>projected vs {m.opp_name || 'your opponent'}</span>
          </div>
        )}
        <Prose text={ins.narrative} />
        <div className="gm-foot">
          <button type="button" className="benchtoggle" onClick={() => setShowLineup((s) => !s)} aria-expanded={showLineup}>
            {showLineup ? 'HIDE THE CARD' : 'FULL LINEUP CARD'}
          </button>
          {onReprint && (
            <button type="button" className="benchtoggle" onClick={onReprint} disabled={reprinting}>
              {reprinting ? 'REPRINTING…' : 'REPRINT NOW'}
            </button>
          )}
          {ins.waiver?.type && (
            <span className="gm-rules num">
              {ins.waiver.type}{ins.waiver.position ? ` · you claim #${ins.waiver.position}` : ''}
              {ins.waiver.budget_left != null ? ` · $${ins.waiver.budget_left} left` : ''}
              {ins.waiver.runs ? ` · runs ${ins.waiver.runs}` : ''}
            </span>
          )}
        </div>
      </div>

      <div className="gm-right">
        <p className="wr-sub">Lineup card <span className="num">{moves.length ? `${moves.length} move${moves.length === 1 ? '' : 's'} to the optimal lineup` : 'no moves: the card stands'}</span></p>
        {moves.length > 0 && (
          <div className="tablewrap">
            <table className="stats wr-tbl">
              <thead>
                <tr><th scope="col" className="txt">PLAYER</th><th scope="col">POS</th><th scope="col">FROM</th><th scope="col">TO</th><th scope="col">PROJ</th></tr>
              </thead>
              <tbody>
                {moves.map((mv) => (
                  <tr key={mv.player_id} className={mv.to === 'BN' ? 'wr-out' : 'wr-in'}>
                    <td className="txt player">{mv.name}</td>
                    <td className="team">{mv.pos || '–'}</td>
                    <td className="team">{mv.from}</td>
                    <td className="team to">{mv.to}</td>
                    <td className="n">{fmt(mv.proj)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="wr-sub">The wire <span className="num">{waivers.length ? 'claims and releases, with the projected upside' : 'nothing on the wire beats the bench'}</span></p>
        {waivers.length > 0 && (
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
        )}

        {proposals.length > 0 && (
          <>
            <p className="wr-sub">The inbox <span className="num">trade proposals on the table, both sides scored</span></p>
            <div className="tablewrap">
              <table className="stats wr-tbl">
                <thead>
                  <tr>
                    <th scope="col" className="txt">FROM</th>
                    <th scope="col" className="txt">YOU GET</th>
                    <th scope="col" className="txt">YOU SEND</th>
                    <th scope="col">THIS WK</th>
                    <th scope="col">ROS<span className="was">pts / wk</span></th>
                    <th scope="col" className="txt">CALL</th>
                  </tr>
                </thead>
                <tbody>
                  {proposals.map((pr, i) => (
                    <tr key={`p${i}`} className={`v-${String(pr.verdict || '').replace(/\s+/g, '-')}`}>
                      <td className="txt wr-meta">{pr.from_me ? `you, to ${pr.partner}` : pr.partner}</td>
                      <td className="txt player">{(pr.get || []).map((x) => x.name).join(', ') || '–'}</td>
                      <td className="txt player">{(pr.send || []).map((x) => x.name).join(', ') || '–'}</td>
                      <td className="n">{fmt(pr.my_week_delta, true)}</td>
                      <td className="n sortcol">{fmt(pr.my_ros_delta, true)}</td>
                      <td className="txt call">{pr.verdict}{pr.picks ? ' (picks not valued)' : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {trades.length > 0 && (
          <>
            <p className="wr-sub">The phones <span className="num">one for one, both sides scored</span></p>
            <div className="tablewrap">
              <table className="stats wr-tbl">
                <thead>
                  <tr><th scope="col" className="txt">SEND</th><th scope="col" className="txt">GET</th><th scope="col" className="txt">PARTNER</th><th scope="col">YOU / THEM</th></tr>
                </thead>
                <tbody>
                  {trades.map((t, i) => (
                    <tr key={`t${i}`}>
                      <td className="txt player">{t.send[0]?.name}</td>
                      <td className="txt player">{t.receive[0]?.name}</td>
                      <td className="txt wr-meta">{t.partner}</td>
                      <td className="n sortcol">{fmt(t.my_delta, true)} / {fmt(t.their_delta, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {showLineup && lu.lineup?.length > 0 && (
        <div className="gm-card">
          <div className="tablewrap">
            <table className="stats wr-tbl wr-lineup">
              <thead>
                <tr>
                  <th scope="col" className="txt">SLOT</th><th scope="col" className="txt">PLAYER</th><th scope="col">POS</th><th scope="col">TEAM</th><th scope="col">OPP</th><th scope="col">PROJ</th>
                </tr>
              </thead>
              <tbody>
                {lu.lineup.map((p, i) => (
                  <tr key={`${p.slot}-${i}`}>
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
          </div>
          {ins.projection_note && <p className="note wr-note">{ins.projection_note}</p>}
        </div>
      )}
    </div>
  )
}
