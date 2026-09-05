import { useEffect, useRef, useState } from 'react'
import { gameService } from '../api'
import { useMe, rememberSleeperUsername } from '../auth'
import { Masthead, Folio, Footnotes, Colophon } from './Almanac'

/* The live advisor desk. Draft night is latency-first: the current
   recommendation is the lead story, alternatives print as a ledger with
   survival odds, and the page re-polls every 5 seconds while the draft is
   live. The Sleeper username is shared with MY LEAGUES via localStorage. */

const USER_KEY = 'sleeper_username'

function SurvBar({ p }) {
  const pct = Math.round((p ?? 0) * 100)
  return (
    <span className="survwrap">
      <span className="survbar" style={{ '--pct': `${pct}%` }} aria-hidden="true"></span>
      <span className="num">{pct}%</span>
    </span>
  )
}

function DraftAdvisor() {
  const me = useMe()
  const [username, setUsername] = useState(() => localStorage.getItem(USER_KEY) || '')
  const [leagues, setLeagues] = useState(null)
  const [leagueId, setLeagueId] = useState('')
  const [model, setModel] = useState('v1')
  const [advice, setAdvice] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  const loadLeagues = () => {
    const name = username.trim()
    if (!name) return
    setError(null)
    setLeagues(null)
    setAdvice(null)
    gameService.fetchDraftLeagues(name)
      .then((d) => {
        rememberSleeperUsername(name)
        setLeagues(d.leagues || [])
        if ((d.leagues || []).length === 1) setLeagueId(d.leagues[0].league_id)
      })
      .catch((err) => setError(err.message))
  }

  /* The signed-in profile's saved handle fills the field on arrival. */
  useEffect(() => {
    if (!username && me?.authenticated && me.sleeper_username) {
      setUsername(me.sleeper_username)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me])

  const stopPolling = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null }
  }

  const advise = () => {
    const name = username.trim()
    if (!name || !leagueId) return
    setError(null)
    setBusy(true)
    gameService.fetchAdvise(leagueId, name, model)
      .then((d) => {
        setAdvice(d)
        stopPolling()
        if (d.draft_status === 'drafting') {
          timer.current = setTimeout(advise, 5000)
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }

  useEffect(() => () => stopPolling(), [])
  useEffect(() => {
    if (username && !leagues) loadLeagues()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const live = advice?.draft_status === 'drafting'

  return (
    <>
      <Masthead vol="The Draft Desk" controls={null} />

      <section aria-labelledby="sec-advisor">
        <Folio sec="THE DRAFT DESK" id="sec-advisor" title="Live Advisor"
          cont={live ? 'Draft in progress' : null} />
        <p className="folio-note">
          Sleeper-connected. During a live draft this desk re-figures every five
          seconds: it tracks every pick, knows the roster slots you still need,
          adapts to your league&rsquo;s exact scoring, and prints the odds each
          alternative survives until your next turn.
        </p>

        <div className="advbar">
          <input className="boardsearch" type="text" placeholder="Sleeper username"
            value={username} onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') loadLeagues() }}
            aria-label="Sleeper username" />
          <button type="button" className="ctl" onClick={loadLeagues}>LOAD LEAGUES</button>
          <label className="ctl">
            <span className="lbl">LEAGUE</span>
            <select value={leagueId} onChange={(e) => setLeagueId(e.target.value)}
              aria-label="League" disabled={!leagues?.length}>
              <option value="">{leagues ? 'CHOOSE' : 'LOAD LEAGUES FIRST'}</option>
              {(leagues || []).map((l) => (
                <option key={l.league_id} value={l.league_id}>
                  {l.name}{l.superflex ? ' (SF)' : ''}
                </option>
              ))}
            </select>
            <span className="car" aria-hidden="true">&#9662;</span>
          </label>
          <label className="ctl">
            <span className="lbl">ENGINE</span>
            <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Engine">
              <option value="v1">V1 · POINTS</option>
              <option value="v2">V2 · ROSTER VALUE</option>
            </select>
            <span className="car" aria-hidden="true">&#9662;</span>
          </label>
          <button type="button" className="ctl advgo" onClick={advise} disabled={!leagueId || busy}>
            {busy ? 'FIGURING…' : 'ADVISE'}
          </button>
        </div>

        {error && <p className="wire">ADVISOR WIRE DOWN: <b>{error}</b></p>}

        {advice && !advice.error && (
          <>
            <p className="folio-note">
              <span className="num">{advice.picks_made ?? 0}</span> picks made
              · draft {String(advice.draft_status || 'unknown')}
              {advice.my_slot ? <> · your slot <span className="num">{advice.my_slot}</span></> : null}
              {live && <> · <b className="live-note">re-figuring every 5s</b></>}
            </p>

            <article className="entry live rec-lead">
              <div className="entry-head">
                <span className="entry-no num">THE PICK</span>
                {live && <span className="live-flag"><span className="live-dot" aria-hidden="true"></span>LIVE</span>}
                <span className="entry-time num">{model.toUpperCase()}</span>
              </div>
              <div className="rec-name">
                {advice.recommendation}
                <span className="rec-pos">{advice.position}</span>
                {advice.proj != null && <span className="rec-proj num">proj {advice.proj}</span>}
              </div>
              {advice.why && <p className="closing">{advice.why}</p>}
              {advice.needs && (
                <p className="live-sit">
                  Still to fill:{' '}
                  {Object.entries(advice.needs.starters || {})
                    .filter(([, v]) => v > 0)
                    .map(([k, v]) => `${k} ${v}`).join(', ') || 'core starters set'}
                  {advice.needs.K > 0 && `, K ${advice.needs.K}`}
                  {advice.needs.DEF > 0 && `, DEF ${advice.needs.DEF}`}
                </p>
              )}
            </article>

            {advice.candidates?.length > 0 && (
              <>
                <p className="subhead">Alternatives <span className="count">odds each survives to your next pick</span></p>
                <div className="tablewrap">
                  <table className="stats">
                    <thead>
                      <tr>
                        <th scope="col" className="txt">PLAYER</th>
                        <th scope="col">POS</th>
                        <th scope="col">PROJ</th>
                        <th scope="col">MARKET</th>
                        <th scope="col">SURVIVES</th>
                      </tr>
                    </thead>
                    <tbody>
                      {advice.candidates.map((c) => (
                        <tr key={c.name} className={c.name === advice.recommendation ? 'leader' : undefined}>
                          <td className="txt player">{c.name}</td>
                          <td className="team">{c.pos}</td>
                          <td className="n">{c.proj}</td>
                          <td className="n">{c.market_rank}</td>
                          <td className="n"><SurvBar p={c.survives_to_next_pick} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {advice.my_roster?.length > 0 && (
              <>
                <p className="subhead">Your roster so far <span className="count">{advice.my_roster.length} picks</span></p>
                <p className="closing">
                  {advice.my_roster.map((p) => `${p.name} (${p.pos})`).join(' · ')}
                </p>
              </>
            )}
          </>
        )}
        {advice?.error && <p className="wire">{String(advice.error).toUpperCase()}</p>}

        <Footnotes>
          <p>The engine simulates thousands of draft continuations from the live
            state (MCTS) and prices scarcity, your roster needs, and how likely
            each alternative is to come back around.</p>
          <p>Nothing is written to your Sleeper account; the desk only reads the
            public draft feed.</p>
        </Footnotes>
      </section>

      <Colophon center="The Draft Desk · Live Advisor" />
    </>
  )
}

export default DraftAdvisor
