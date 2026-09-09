import { useEffect, useState } from 'react'
import { gameService } from '../api'

/* THE TRADE DESK: build a trade against any roster in the league and have
   the engine score it for both sides, this week and the rest of the season,
   from the same Sleeper projections the GM's note runs on. */

function fmt(v, signed = false) {
  if (v == null) return '–'
  const n = Number(v)
  const s = Math.abs(n).toFixed(1)
  if (!signed) return s
  return n < 0 ? `-${s}` : `+${s}`
}

function RosterPick({ title, players, picked, onToggle }) {
  return (
    <div className="tablewrap">
      <table className="stats wr-tbl tdesk-tbl">
        <thead>
          <tr>
            <th scope="col" className="pick"><span className="sr">Pick</span></th>
            <th scope="col" className="txt">{title}</th>
            <th scope="col">POS</th>
            <th scope="col">PROJ</th>
            <th scope="col">ROS<span className="was">pts / wk</span></th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => {
            const on = picked.has(p.player_id)
            return (
              <tr key={p.player_id} className={on ? 'picked' : undefined} onClick={() => onToggle(p.player_id)}>
                <td className="pick">
                  <input type="checkbox" checked={on} onChange={() => onToggle(p.player_id)}
                    onClick={(e) => e.stopPropagation()} aria-label={`${on ? 'Remove' : 'Add'} ${p.name}`} />
                </td>
                <td className="txt player">{p.name}{p.injury ? <span className="mark"> {p.injury[0]}</span> : null}
                  <span className="wr-meta"> {p.team || 'FA'}</span></td>
                <td className="team">{p.pos || '–'}</td>
                <td className="n">{fmt(p.proj)}</td>
                <td className="n sortcol">{fmt(p.ros)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function Verdict({ ev, compact = false }) {
  if (!ev) return null
  if (ev.error) return <p className="note">{ev.error}.</p>
  const slug = String(ev.verdict || '').replace(/\s+/g, '-')
  return (
    <div className={`tdesk-verdict v-${slug}`}>
      <span className="call">{ev.verdict}</span>
      <span className="line num">you <b>{fmt(ev.my_ros_delta, true)}</b> a week rest of season · <b>{fmt(ev.my_week_delta, true)}</b> this week</span>
      <span className="line num">{ev.partner ? ev.partner : 'them'} <b>{fmt(ev.their_ros_delta, true)}</b> · <b>{fmt(ev.their_week_delta, true)}</b></span>
      {!compact && ev.my_cuts?.length > 0 && (
        <span className="line">you would release {ev.my_cuts.map((c) => c.name).join(', ')}</span>
      )}
      {!compact && ev.picks > 0 && <span className="line">{ev.picks} draft pick{ev.picks === 1 ? '' : 's'} in the deal, not valued</span>}
    </div>
  )
}

export default function TradeDesk({ username, leagueId }) {
  const [desk, setDesk] = useState(null)
  const [err, setErr] = useState(null)
  const [partner, setPartner] = useState('')
  const [send, setSend] = useState(() => new Set())
  const [get, setGet] = useState(() => new Set())
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    setDesk(null); setErr(null); setResult(null)
    gameService.fetchTradeDesk(username, leagueId)
      .then((d) => {
        if (!alive) return
        if (d.error && !d.me) { setErr(d.error); return }
        setDesk(d)
        setPartner(String(d.partners?.[0]?.roster_id ?? ''))
      })
      .catch((e) => { if (alive) setErr(e.message || 'trade desk unavailable') })
    return () => { alive = false }
  }, [username, leagueId])

  const toggle = (setter) => (pid) => {
    setResult(null)
    setter((s) => { const n = new Set(s); if (n.has(pid)) n.delete(pid); else n.add(pid); return n })
  }
  const them = desk?.partners?.find((p) => String(p.roster_id) === partner)

  async function score() {
    setBusy(true); setResult(null)
    try {
      const d = await gameService.fetchTradeDesk(username, leagueId, {
        partner, send: [...send].join(','), get: [...get].join(','),
      })
      setResult(d.evaluation || { error: d.error || 'no evaluation' })
    } catch (e) {
      setResult({ error: e.message || 'trade desk unavailable' })
    } finally {
      setBusy(false)
    }
  }

  if (err) return <p className="note">The trade desk is closed: {err}.</p>
  if (!desk) return <p className="note wr-note">Opening the trade desk…</p>
  if (!desk.partners?.length) return <p className="note">No other rosters in this league yet.</p>

  return (
    <div className="tdesk">
      <p className="wr-sub">Trade desk <span className="num">pick what you send and what you get; the engine scores both sides, this week and rest of season</span></p>
      <label className="ctl">
        <span className="lbl">PARTNER</span>
        <select value={partner} onChange={(e) => { setPartner(e.target.value); setGet(new Set()); setResult(null) }}>
          {desk.partners.map((p) => <option key={p.roster_id} value={String(p.roster_id)}>{p.name}</option>)}
        </select>
        <span className="car" aria-hidden="true">▾</span>
      </label>
      <div className="tdesk-cols">
        <RosterPick title="YOU SEND" players={desk.me.players} picked={send} onToggle={toggle(setSend)} />
        {them && <RosterPick title={`YOU GET FROM ${them.name}`} players={them.players} picked={get} onToggle={toggle(setGet)} />}
      </div>
      <div className="tdesk-foot">
        <button type="button" className="benchtoggle" onClick={score} disabled={busy || (!send.size && !get.size)}>
          {busy ? 'SCORING…' : 'SCORE THE TRADE'}
        </button>
        <Verdict ev={result} />
        <p className="note wr-note">Rest of season is lineup value per week (starters plus a share of the bench) from
          Sleeper&rsquo;s remaining weekly projections; this week is the change in your optimal lineup total.
          Draft picks are not valued.</p>
      </div>
    </div>
  )
}
