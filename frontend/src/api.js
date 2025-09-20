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
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`GET request failed for ${endpoint}:`, error);
    throw error;
  }
}

export const gameService = {
  fetchGames(weekNum = null) {
    const endpoint = weekNum ? `/games/${weekNum}/` : "/games/"
    return get(endpoint)
  },
  fetchTeamSchedule(teamId) {
    return get(`/team-schedule/${teamId}/`)
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
