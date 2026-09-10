import { useEffect, useState } from 'react'
import { gameService } from '../api'
import { Folio, Footnotes } from './Almanac'

/* THE TRADE EVALUATOR: four steps. Pick the league, the manager you would
   deal with, the players on each side, and the engine scores the deal for
   both sides, this week and the rest of the season, from the same Sleeper
   projections the GM's note runs on. */

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

function Select({ label, value, onChange, children }) {
  return (
    <label className="ctl">
      <span className="lbl">{label}</span>
      <select value={value} onChange={onChange}>{children}</select>
      <span className="car" aria-hidden="true">▾</span>
    </label>
  )
}

export default function TradeEvaluator({ username, leagues }) {
  const active = (leagues || []).filter((lg) => !(lg.status === 'pre_draft' || lg.status === 'drafting'))
  const [leagueId, setLeagueId] = useState(() => active[0]?.league_id || '')
  const [desk, setDesk] = useState(null)
  const [err, setErr] = useState(null)
  const [partner, setPartner] = useState('')
  const [send, setSend] = useState(() => new Set())
  const [get, setGet] = useState(() => new Set())
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!leagueId && active[0]?.league_id) setLeagueId(active[0].league_id)
  }, [active, leagueId])

  useEffect(() => {
    if (!username || !leagueId) return undefined
    let alive = true
    setDesk(null); setErr(null); setResult(null); setSend(new Set()); setGet(new Set())
    gameService.fetchTradeDesk(username, leagueId)
      .then((d) => {
        if (!alive) return
        if (d.error && !d.me) { setErr(d.error); return }
        setDesk(d)
        setPartner(String(d.partners?.[0]?.roster_id ?? ''))
      })
      .catch((e) => { if (alive) setErr(e.message || 'the trade evaluator is unavailable') })
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
      setResult({ error: e.message || 'the trade evaluator is unavailable' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="sec-trades">
      <Folio sec="THE TRADE EVALUATOR" id="sec-trades" title="Score a Trade Before You Make It"
        cont="both sides, this week and rest of season" />
      <p className="folio-note">
        Pick the league, the manager you would deal with, then the players on each side.
        The engine scores the deal for both sides from the same Sleeper projections the
        general manager works from.
      </p>
      {!active.length ? (
        <p className="wire">NO LEAGUE HAS A ROSTER YET. <b>The evaluator opens once a league drafts.</b></p>
      ) : (
        <ol className="steps">
          <li className="step">
            <span className="stepno num" aria-hidden="true">1</span>
            <div className="stepbody">
              <span className="steplbl">League</span>
              <Select label="LEAGUE" value={leagueId} onChange={(e) => setLeagueId(e.target.value)}>
                {active.map((lg) => <option key={lg.league_id} value={lg.league_id}>{lg.name}</option>)}
              </Select>
            </div>
          </li>
          <li className="step">
            <span className="stepno num" aria-hidden="true">2</span>
            <div className="stepbody">
              <span className="steplbl">Trade partner <small>the manager you would deal with</small></span>
              {err ? <p className="note">The desk could not pull this league: {err}.</p>
                : !desk ? <p className="note wr-note">Pulling the rosters…</p>
                  : !desk.partners?.length ? <p className="note">No other rosters in this league yet.</p>
                    : (
                      <Select label="PARTNER" value={partner}
                        onChange={(e) => { setPartner(e.target.value); setGet(new Set()); setResult(null) }}>
                        {desk.partners.map((p) => <option key={p.roster_id} value={String(p.roster_id)}>{p.name}</option>)}
                      </Select>
                    )}
            </div>
          </li>
          <li className="step">
            <span className="stepno num" aria-hidden="true">3</span>
            <div className="stepbody">
              <span className="steplbl">Players <small>tick who you send and who you get; more than one on a side is fine</small></span>
              {desk && them ? (
                <div className="tdesk-cols">
                  <RosterPick title="YOU SEND" players={desk.me.players} picked={send} onToggle={toggle(setSend)} />
                  <RosterPick title={`YOU GET FROM ${them.name}`} players={them.players} picked={get} onToggle={toggle(setGet)} />
                </div>
              ) : <p className="note wr-note">Pick a league and a partner first.</p>}
            </div>
          </li>
          <li className="step">
            <span className="stepno num" aria-hidden="true">4</span>
            <div className="stepbody">
              <span className="steplbl">The verdict</span>
              <div className="tdesk-foot">
                <button type="button" className="ctl" onClick={score} disabled={busy || !desk || !them || (!send.size && !get.size)}>
                  <span className="lbl">{busy ? 'SCORING' : 'RUN'}</span> {busy ? '…' : 'SCORE THE TRADE'}
                </button>
                <Verdict ev={result} />
              </div>
            </div>
          </li>
        </ol>
      )}
      <Footnotes>
        <p>Rest of season is lineup value per week (starters plus a share of the bench)
          from Sleeper&rsquo;s remaining weekly projections through week 17; this week is
          the change in your optimal lineup total. Accept means at least a point a week
          without giving up this week; decline means the deal costs you rest of season.
          Draft picks are listed but not valued.</p>
      </Footnotes>
    </section>
  )
}
