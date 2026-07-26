import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getLogoUrl } from '../utils'
import { gameService } from '../api'

/* Shared pieces of the almanac page furniture:
   the Desk mark, masthead plate, teams menu, folio section headers,
   logo chips, footnote apparatus and the colophon. */

/* The Desk mark: a square field plate ruled with three yard lines and one
   green needle set off-center, the same instrument language as the win
   gauge's needle and the ledger's leading-side tick. Reads at 16px. */
export function DeskMark({ className = 'mark-plate' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect x="2" y="2" width="28" height="28" fill="none" stroke="var(--ink)" strokeWidth="2.5" />
      <line x1="7" y1="10" x2="25" y2="10" stroke="var(--ink)" strokeWidth="2" />
      <line x1="7" y1="16" x2="25" y2="16" stroke="var(--ink)" strokeWidth="2" />
      <line x1="7" y1="22" x2="25" y2="22" stroke="var(--ink)" strokeWidth="2" />
      <line x1="20" y1="6" x2="20" y2="26" stroke="var(--green)" strokeWidth="2.5" />
    </svg>
  )
}

/* Masthead teams menu: a native select dressed as a printed control, so it
   works with a thumb on a phone and a keyboard anywhere. Selecting a team
   opens that team's page. The list is fetched once per session. */
let teamsCache = null

function TeamsMenu() {
  const navigate = useNavigate()
  const [teams, setTeams] = useState(teamsCache || [])

  useEffect(() => {
    if (teamsCache) return undefined
    let alive = true
    gameService.fetchTeams()
      .then((data) => {
        teamsCache = data.teams || []
        if (alive) setTeams(teamsCache)
      })
      .catch(() => { /* menu simply stays absent if the list fails */ })
    return () => { alive = false }
  }, [])

  if (teams.length === 0) return null

  return (
    <label className="ctl">
      <span className="lbl">TEAMS</span>
      <select
        value=""
        aria-label="Open a team's page"
        onChange={(e) => { if (e.target.value) navigate(`/team/${e.target.value}`) }}
      >
        <option value="">CHOOSE</option>
        {teams.map((t) => (
          <option key={t.team_id} value={t.team_id}>{t.name}</option>
        ))}
      </select>
      <span className="car" aria-hidden="true">&#9662;</span>
    </label>
  )
}

export function Masthead({ vol, stamp, controls }) {
  return (
    <>
      <div className="plate">
        <span className="vol">{vol || 'Front Page'}</span>
        <span className="stamp">
          {stamp ? <>UPDATED <b>{stamp}</b></> : 'NIGHT EDITION'}
        </span>
      </div>
      <header className="masthead">
        <div className="brand">
          <Link className="brand-lock" to="/" aria-label="Gridiron Desk, front page">
            <DeskMark />
            <h1>Gridiron<br /><span className="desk">Desk</span></h1>
          </Link>
          <p>The weekly record of pro football, set in figures.</p>
        </div>
        <div className="controls">
          <TeamsMenu />
          {controls}
        </div>
      </header>
      <div className="rule-double" role="presentation"></div>
    </>
  )
}

export function Folio({ sec, title, cont, pg, id }) {
  return (
    <header className="folio">
      <span className="sec">{sec}</span>
      <span className="title" id={id}>{title}</span>
      {cont ? (
        <>
          <span className="sep">&middot;</span>
          <span className="cont">{cont}</span>
        </>
      ) : null}
      {pg ? <span className="pg num">{pg}</span> : null}
    </header>
  )
}

/* The team mark printed on a lifted chip plate with a pale keyline.
   Logo files are the app's own copyright-safe marks; never substitute.
   With `to` + `label` the chip becomes its own link (to the team page),
   focusable and sealed off from any clickable card around it. */
export function Chip({ file, alt = '', to, label, lg = false }) {
  const img = file ? <img src={getLogoUrl(file)} alt={alt} /> : null
  const cls = `chip${lg ? ' chip-lg' : ''}`
  if (to) {
    return (
      <Link
        className={`${cls} chip-link`}
        to={to}
        aria-label={label}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        {img}
      </Link>
    )
  }
  return (
    <span className={cls} aria-hidden={alt === '' ? 'true' : undefined}>
      {img}
    </span>
  )
}

export function Footnotes({ children }) {
  return (
    <div className="footnotes">
      {children}
      <p className="src">Data: ESPN public API. Scores, odds, and team stats refresh hourly; player stats every six hours.</p>
    </div>
  )
}

export function Colophon({ center }) {
  return (
    <footer className="colophon">
      <span className="colo-brand">
        <DeskMark className="mark-colo" />
        Gridiron Desk &middot; Almanac, Night Edition
      </span>
      {center ? <span>{center}</span> : null}
      <span>Updated hourly</span>
    </footer>
  )
}

/* Inked win-probability gauge with needle tick. Split is the away share. */
export function ProbGauge({ awayAbbr, homeAbbr, awayPct, homePct }) {
  const split = `${awayPct}%`
  return (
    <div className="prob">
      <div className="prob-labels">
        <span className="pl away num">{awayAbbr} {awayPct}%</span>
        <span className="cap">WIN PROBABILITY</span>
        <span className="pl home num">{homeAbbr} {homePct}%</span>
      </div>
      <div
        className="gauge"
        style={{ '--split': split }}
        role="img"
        aria-label={`Win probability: ${awayAbbr} ${awayPct} percent, ${homeAbbr} ${homePct} percent`}
      >
        <span className="scale"></span>
        <span className="needle"></span>
      </div>
    </div>
  )
}
