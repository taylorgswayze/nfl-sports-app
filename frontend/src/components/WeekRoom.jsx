import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Verdict } from './TradeEvaluator'

/* THE GENERAL MANAGER, folded: one bar with the number that matters (points
   on the table), the projected matchup and the buttons; the note itself
   opens as a pop-out. Under the bar, the recommendations as short tables:
   the lineup card, the wire, the phones and, when a proposal is on the
   table, the inbox. A section with nothing to say prints "None".
   Deterministic engine output plus a few sentences, refreshed every 12 hours. */

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

/* The note as a pop-out: the prose, the league, when it printed. */
function NoteModal({ ins, onClose }) {
  const box = useRef(null)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key !== 'Tab' || !box.current) return
      // keep the tab order inside the pop-out while it is open
      const f = box.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
      if (!f.length) return
      const first = f[0]; const last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose])
  const printed = stamp(ins.generated_at)
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={`The GM's note for ${ins.name}`}
        ref={box} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="kicker">The GM&rsquo;s note</span>
            <span className="modal-title">{ins.name}</span>
            <span className="when num">{printed ? `printed ${printed}` : ''}</span>
          </div>
          <button type="button" className="ctl" onClick={onClose} autoFocus>CLOSE</button>
        </div>
        <Prose text={ins.narrative} />
      </div>
    </div>
  )
}

function NoneLine({ children }) {
  return <p className="wr-none">None. <span>{children}</span></p>
}

export default function WeekRoom({ ins }) {
  const [showLineup, setShowLineup] = useState(false)
  const [noteOpen, setNoteOpen] = useState(false)
  const noteBtn = useRef(null)
  const closeNote = useCallback(() => { setNoteOpen(false); noteBtn.current?.focus() }, [])
  if (!ins) return null
  const preDraft = ins.status === 'pre_draft' || ins.status === 'drafting'
  const lu = ins.lineup || {}
  const moves = lu.moves || []
  const waivers = ins.waivers || []
  const trades = ins.trades || []
  const proposals = ins.proposals || []
  const printed = stamp(ins.generated_at)
  const numbersAt = stamp(ins.numbers_at)
  const refreshed = numbersAt && numbersAt !== printed ? numbersAt : null

  if (preDraft || ins.error) {
    return (
      <div className="gm gm-quiet">
        <div className="gm-bar">
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

  // this week's upside: what the open moves are still worth, lineup and wire
  const parts = ins.upside_parts || { lineup: lu.material ? Number(lu.gain) : 0, claim: 0, moves: moves.length }
  const up = ins.upside_week != null ? Number(ins.upside_week) : parts.lineup
  const hot = up >= 0.05
  const bits = []
  if (parts.moves > 0 && parts.lineup >= 0.05) bits.push(`${parts.moves} lineup move${parts.moves === 1 ? '' : 's'}`)
  if (parts.claim >= 0.05) bits.push('a pickup from the wire')
  const lede = fmt(up, true)
  const ledeNote = hot ? `this week, from ${bits.join(' and ') || 'the open moves'}` : 'left to gain this week from open moves'

  return (
    <div className={`gm${hot ? ' hot' : ''}`}>
      <div className="gm-bar">
        <div className={`gm-lede num${hot ? '' : ' quiet'}`}>{lede}<small>{ledeNote}</small></div>
        <div className="gm-foot">
          <button type="button" className="ctl" ref={noteBtn} onClick={() => setNoteOpen(true)}>
            <span className="lbl">READ</span> THE GM&rsquo;S NOTE
          </button>
          <button type="button" className="benchtoggle" onClick={() => setShowLineup((s) => !s)} aria-expanded={showLineup}>
            {showLineup ? 'HIDE THE CARD' : 'FULL LINEUP CARD'}
          </button>
          <span className="when num">{printed ? `note ${printed}` : ''}{refreshed ? ` · numbers ${refreshed}` : ''}{ins.roster_changed ? ' · roster changed since' : ''}</span>
        </div>
      </div>

      <div className="gm-recs">
        <div className="gm-rec">
          <p className="wr-sub">Lineup card <span className="num">{moves.length ? `${moves.length} move${moves.length === 1 ? '' : 's'} to the optimal lineup, ${fmt(lu.gain, true)}` : ''}</span></p>
          {moves.length > 0 ? (
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
          ) : <NoneLine>The card is already the projected optimum.</NoneLine>}
        </div>

        <div className="gm-rec">
          <p className="wr-sub">The wire <span className="num">{waivers.length ? 'one row per move, net gain' : ''}</span></p>
          {waivers.length > 0 ? (
            <div className="tablewrap">
              <table className="stats wr-tbl">
                <thead>
                  <tr>
                    <th scope="col" className="txt">PICK UP</th>
                    <th scope="col" className="txt">DROP</th>
                    <th scope="col">THIS WEEK<span className="was">pts</span></th>
                    <th scope="col">SEASON<span className="was">pts / wk</span></th>
                  </tr>
                </thead>
                <tbody>
                  {waivers.map((w, i) => (
                    <tr key={`w${i}`}>
                      <td className="txt player">{w.add.name} <span className="wr-meta">{[w.add.pos, w.add.team].filter(Boolean).join(', ')}</span></td>
                      <td className="txt">{w.drop.name} <span className="wr-meta">{w.drop.pos}</span></td>
                      <td className={`n${w.best_week && !w.locked ? ' sortcol best' : ''}`}>{w.locked ? <span className="wr-meta">locked</span> : fmt(w.week_gain, true)}</td>
                      <td className={`n${w.best_season ? ' sortcol best' : ''}`}>{fmt(w.gain, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <NoneLine>Nothing available beats the bench.</NoneLine>}
          {ins.waiver?.type && (
            <span className="gm-rules num">
              {ins.waiver.type}{ins.waiver.position ? ` · you claim #${ins.waiver.position}` : ''}
              {ins.waiver.budget_left != null ? ` · $${ins.waiver.budget_left} left` : ''}
              {ins.waiver.runs ? ` · runs ${ins.waiver.runs}` : ''}
            </span>
          )}
        </div>

        <div className="gm-rec">
          <p className="wr-sub">The phones <span className="num">{trades.length ? 'one for one, both sides scored' : ''}</span></p>
          {trades.length > 0 ? (
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
          ) : <NoneLine>No one-for-one that helps both sides.</NoneLine>}
        </div>

        {proposals.length > 0 && (
          <div className="gm-rec">
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
            {proposals.map((pr, i) => <Verdict key={`v${i}`} ev={pr} compact />)}
          </div>
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
        </div>
      )}

      {noteOpen && <NoteModal ins={ins} onClose={closeNote} />}
    </div>
  )
}
