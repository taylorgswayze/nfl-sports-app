export async function get(endpoint, params = null) {
  try {
    let url = `/api${endpoint}`;

    if (params) {
      const queryString = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== null && value !== undefined) {
          queryString.append(key, value);
        }
      }
      if (queryString.toString()) {
        url += `?${queryString.toString()}`;
      }
    }

    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const err = new Error(response.status === 401 ? 'sign in required' : `API error: ${response.status}`);
      err.status = response.status;
      throw err;
    }

    return await response.json();
  } catch (error) {
    console.error(`GET request failed for ${endpoint}:`, error);
    throw error;
  }
}

// Seasons rarely change within a session; share one request across pages.
let seasonsPromise = null

export function fetchSeasonsCached() {
  if (!seasonsPromise) {
    seasonsPromise = get("/seasons/").catch((error) => {
      seasonsPromise = null
      throw error
    })
  }
  return seasonsPromise
}

/* Account endpoints. Sign-in itself is a full-page redirect to
   /api/auth/login/ (Google), so only me-reads and settings-writes live here. */
export const accountService = {
  fetchMe() {
    return get("/me/")
  },
  async saveMe(patch) {
    const response = await fetch("/api/me/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
    if (!response.ok) throw new Error(`API error: ${response.status}`)
    return response.json()
  },
}

export const gameService = {
  fetchGamesWindow() {
    return get("/games/window/")
  },
  fetchGames(weekNum = null, season = null, seasonType = null) {
    const endpoint = weekNum ? `/games/${weekNum}/` : "/games/"
    const params = {}
    if (season) params.season = season
    if (seasonType) params.season_type = seasonType
    return get(endpoint, Object.keys(params).length ? params : null)
  },
  fetchSeasons() {
    return fetchSeasonsCached()
  },
  fetchTeams() {
    return get("/teams/")
  },
  fetchTeamSchedule(teamId) {
    return get(`/team-schedule/${teamId}/`)
  },
  fetchMatchup(eventId) {
    return get(`/matchup/${eventId}/`)
  },
  fetchLive() {
    return get("/live/")
  },
  fetchStandings() {
    return get("/standings/")
  },
  fetchBoxscore(eventId) {
    return get(`/game/${eventId}/boxscore/`)
  },
  fetchDraftBoard() {
    return get("/draft/board/")
  },
  fetchDraftLeagues(username) {
    return get("/draft/leagues/", { username })
  },
  fetchAdvise(leagueId, username, model) {
    return get("/draft/advise/", { league_id: leagueId, username, model })
  },
  fetchFantasyOverview(username) {
    return get("/fantasy/overview/", { username })
  },
  fetchFantasyInsights(username, refresh = false) {
    return get("/fantasy/insights/", refresh ? { username, refresh: 1 } : { username })
  },
  fetchTeamStats(teamId, season) {
    return get(`/teams/${teamId}/stats/`, { season })
  },
  fetchTeamRoster(teamId) {
    return get(`/teams/${teamId}/roster/`)
  },
  fetchTeamStatComparison(statName) {
    return get(`/team-stat/${statName}/`)
  },
};
