import { useEffect, useState } from 'react'
import { accountService } from './api'

/* One /api/me/ fetch per session, shared by every component that asks.
   `me` is null while loading, then {authenticated: false} or the profile. */
let mePromise = null
let meValue = null
const listeners = new Set()

function loadMe() {
  if (!mePromise) {
    mePromise = accountService.fetchMe()
      .catch(() => ({ authenticated: false }))
      .then((m) => {
        meValue = m
        listeners.forEach((fn) => fn(m))
        return m
      })
  }
  return mePromise
}

/* Push a settings patch and broadcast the fresh profile. */
export async function saveProfile(patch) {
  const m = await accountService.saveMe(patch)
  meValue = m
  listeners.forEach((fn) => fn(m))
  return m
}

export function useMe() {
  const [me, setMe] = useState(meValue)
  useEffect(() => {
    listeners.add(setMe)
    // Re-read after subscribing: the fetch may have resolved between the
    // first render and this effect, which would otherwise never reach us.
    setMe(meValue)
    loadMe()
    return () => listeners.delete(setMe)
  }, [])
  return me
}

/* The Sleeper username to prefill: the signed-in profile wins, the
   anonymous localStorage value is the fallback. */
export function preferredSleeperUsername(me) {
  if (me?.authenticated && me.sleeper_username) return me.sleeper_username
  return localStorage.getItem('sleeper_username') || ''
}

/* After a successful load with a username: persist it locally always, and
   to the signed-in account when it differs from what is saved there. Reads
   the live profile from the store (never a caller's render closure, which
   can be stale on mount-time auto-loads). */
export function rememberSleeperUsername(username) {
  localStorage.setItem('sleeper_username', username)
  const write = (m) => {
    if (m?.authenticated && m.sleeper_username !== username) {
      saveProfile({ sleeper_username: username }).catch(() => {
        /* Losing the remote save is not worth interrupting the page. */
      })
    }
  }
  if (meValue) write(meValue)
  else loadMe().then(write)
}

/* The sign-in trip returns to `next` (a same-site path) after Google. */
export function loginUrl(next) {
  const path = next || (typeof window !== 'undefined' ? window.location.pathname : '/')
  return `/api/auth/login/?next=${encodeURIComponent(path)}`
}
