import { Link } from 'react-router-dom'
import { getLogoUrl } from '../utils'

/* Shared pieces of the almanac page furniture:
   masthead plate, folio section headers, logo chips,
   footnote apparatus and the colophon. */

export function Masthead({ vol, stamp, controls }) {
  return (
    <>
      <div className="plate">
        <span className="vol">{vol || 'Sec 1 — Masthead & Index — Night Ed.'}</span>
        <span className="stamp">
          {stamp ? <>UPDATED <b>{stamp}</b></> : 'NIGHT EDITION'}
        </span>
      </div>
      <header className="masthead">
        <div className="brand">
          <h1>
            <Link to="/" aria-label="Gridiron Desk, front page">
              Gridiron<br /><span className="desk">Desk</span>
            </Link>
          </h1>
          <p>The weekly record of the professional game, set in figures.</p>
        </div>
        {controls ? <div className="controls">{controls}</div> : null}
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
          <span className="sep">&mdash;</span>
          <span className="cont">{cont}</span>
        </>
      ) : null}
      {pg ? <span className="pg num">{pg}</span> : null}
    </header>
  )
}

/* The team mark printed on a lifted chip plate with a pale keyline.
   Logo files are the app's own copyright-safe marks; never substitute.
   With `to` + `label` the chip becomes its own link (to the team desk),
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
      <p className="src">Data: ESPN public API &mdash; refreshed hourly.</p>
    </div>
  )
}

export function Colophon({ center }) {
  return (
    <footer className="colophon">
      <span>Gridiron Desk &mdash; Almanac, Night Edition</span>
      {center ? <span>{center}</span> : null}
      <span>Set in figures nightly</span>
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
