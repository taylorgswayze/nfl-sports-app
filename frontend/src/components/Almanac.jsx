import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getLogoUrl } from '../utils'
import { gameService } from '../api'
import { useMe } from '../auth'

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

export function TeamsMenu() {
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

/* The paper's sections, set as bound index tabs: each tab is a ruled box
   with the section's name and its job, and the open section is the inked
   tab (ink field, paper text) carrying the green needle on its top edge.
   The rail sticks to the top of the viewport so the paper's index is
   always in hand. */
const SECTIONS = [
  {
    to: '/', label: 'Slate', job: "This week's games",
    match: (p) => p === '/' || p.startsWith('/game') || p.startsWith('/team') || p.startsWith('/position') || p.startsWith('/team-stat'),
  },
  {
    to: '/standings', label: 'Standings', job: 'The league table',
    match: (p) => p.startsWith('/standings'),
  },
  {
    to: '/leagues', label: 'Fantasy', job: 'My leagues + players',
    match: (p) => p.startsWith('/leagues'),
  },
  {
    to: '/draft', label: 'Draft Desk', job: 'Advisor + board',
    match: (p) => p.startsWith('/draft'),
  },
]

/* Desks with more than one page get a printed sub-index under the rail. */
const SUBNAVS = {
  '/draft': [
    { to: '/draft', label: 'THE BOARD', exact: true },
    { to: '/draft/advisor', label: 'LIVE ADVISOR' },
  ],
}

function SectionNav() {
  const { pathname } = useLocation()
  const openSection = SECTIONS.find((s) => s.match(pathname))
  const subnav = openSection ? SUBNAVS[openSection.to] : null
  return (
    <div className="secrail">
      <nav className="secnav" aria-label="Sections">
        {SECTIONS.map((s) => {
          const cur = s === openSection
          return (
            <Link key={s.to} to={s.to}
              className={cur ? 'tab cur' : 'tab'}
              aria-current={cur ? 'page' : undefined}>
              <span className="tab-name">{s.label}</span>
              <span className="tab-job">{s.job}</span>
            </Link>
          )
        })}
      </nav>
      {subnav && (
        <nav className="subnav" aria-label={`${openSection.label} pages`}>
          {subnav.map((s) => {
            const cur = s.exact ? pathname === s.to : pathname.startsWith(s.to)
            return (
              <Link key={s.to} to={s.to}
                className={cur ? 'cur' : undefined}
                aria-current={cur ? 'page' : undefined}>
                {s.label}
              </Link>
            )
          })}
        </nav>
      )}
    </div>
  )
}

/* The bottom gutter: the paper's sections in the thumb zone on phones,
   in the same dual-nav pattern as the Envelopes app (desktop keeps the
   index-tab rail; the gutter replaces it under 680px). Icons are thin
   strokes in the Desk mark's instrument voice, inheriting the link color
   so the active tint covers icon and label together. Mounted once in
   App.jsx, outside .page, so it runs full-bleed. */
const GUTTER_ICONS = {
  '/': (
    // The field plate: the Desk mark's rules, without the needle.
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" />
      <line x1="7" y1="9" x2="17" y2="9" />
      <line x1="7" y1="12" x2="17" y2="12" />
      <line x1="7" y1="15" x2="17" y2="15" />
    </svg>
  ),
  '/standings': (
    // The table: three bars stepping down, the division order.
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="15" y2="12" />
      <line x1="4" y1="18" x2="10" y2="18" />
    </svg>
  ),
  '/draft': (
    // The board: ranked rows, tick first.
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="4" y1="6" x2="6" y2="6" />
      <line x1="10" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="6" y2="12" />
      <line x1="10" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="6" y2="18" />
      <line x1="10" y1="18" x2="20" y2="18" />
    </svg>
  ),
  '/leagues': (
    // The pennant.
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="6" y1="3" x2="6" y2="21" />
      <path d="M6 4 L19 7.5 L6 11" />
    </svg>
  ),
}

export function BottomGutter() {
  const { pathname } = useLocation()
  return (
    <nav className="gutter" aria-label="Primary">
      {SECTIONS.map((s) => {
        const cur = s.match(pathname)
        return (
          <Link key={s.to} to={s.to}
            className={cur ? 'on' : undefined}
            aria-current={cur ? 'page' : undefined}>
            {GUTTER_ICONS[s.to]}
            <span>{s.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

/* The account corner: a sign-in link for the anonymous reader, and the
   subscriber's plate (name, saved Sleeper handle, sign out) once signed
   in. Sign-in is a full-page trip to Google and back. */
function AccountControl() {
  const me = useMe()
  if (!me) return null
  if (!me.authenticated) {
    return (
      <a className="ctl acct-in" href="/api/auth/login/">
        <span className="lbl">ACCOUNT</span>
        <span>SIGN IN</span>
      </a>
    )
  }
  const first = (me.name || me.email || '').split(' ')[0]
  return (
    <details className="acct">
      <summary className="ctl">
        <span className="lbl">SIGNED IN</span>
        <span className="acct-name">{first}</span>
        <span className="car" aria-hidden="true">&#9662;</span>
      </summary>
      <div className="acct-card">
        <p className="acct-who">{me.name}<br /><span>{me.email}</span></p>
        <p className="acct-sleeper">
          Sleeper handle:{' '}
          {me.sleeper_username
            ? <b className="num">{me.sleeper_username}</b>
            : <>none saved yet; load <Link to="/leagues">My Leagues</Link> once to save it</>}
        </p>
        <a className="acct-out" href="/api/auth/logout/">SIGN OUT</a>
      </div>
    </details>
  )
}

export function Masthead({ vol, stamp, controls }) {
  return (
    <>
      <div className="plate">
        <span className="vol">{vol || 'Front Page'}</span>
        <AccountControl />
      </div>
      <header className="masthead">
        <div className="brand">
          <Link className="brand-lock" to="/" aria-label="Gridiron Desk, front page">
            <DeskMark />
            <h1>Gridiron<br /><span className="desk">Desk</span></h1>
          </Link>
        </div>
        {controls && <div className="controls">{controls}</div>}
      </header>
      <div className="rule-double" role="presentation"></div>
      <SectionNav />
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
      <p className="src">Data: ESPN public API. Live scores and boxscores refresh about every half minute during games; odds and season stats hourly.</p>
    </div>
  )
}

export function Colophon({ center }) {
  return (
    <footer className="colophon">
      <span className="colo-brand">
        <DeskMark className="mark-colo" />
        Gridiron Desk
      </span>
      {center ? <span>{center}</span> : null}
      <span>Live during games, hourly otherwise</span>
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
