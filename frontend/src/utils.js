export function getLogoUrl(logoFileName) {
  return `/static/logos/${logoFileName}`;
}

// Mirror of the backend logo map (backend/utils/helpers.py get_team_logo),
// for endpoints that return a team_id but no logo filename.
const TEAM_LOGO_FILES = {
  1: 'nfl-atlanta-falcons-team-logo-2-300x300.png',
  2: 'nfl-buffalo-bills-team-logo-2-300x300.png',
  3: 'nfl-chicago-bears-team-logo-2-300x300.png',
  4: 'nfl-cincinnati-bengals-team-logo-300x300.png',
  5: 'nfl-cleveland-browns-team-logo-2-300x300.png',
  6: 'nfl-dallas-cowboys-team-logo-2-300x300.png',
  7: 'nfl-denver-broncos-team-logo-2-300x300.png',
  8: 'nfl-detroit-lions-team-logo-2-300x300.png',
  9: 'nfl-green-bay-packers-team-logo-2-300x300.png',
  10: 'nfl-tennessee-titans-team-logo-2-300x300.png',
  11: 'nfl-indianapolis-colts-team-logo-2-300x300.png',
  12: 'nfl-kansas-city-chiefs-team-logo-2-300x300.png',
  13: 'nfl-oakland-raiders-team-logo-300x300.png',
  14: 'los-angeles-rams-2020-logo-300x300.png',
  15: 'Miami-Dolphins-Logo-300x300.png',
  16: 'nfl-minnesota-vikings-team-logo-2-300x300.png',
  17: 'nfl-new-england-patriots-team-logo-2-300x300.png',
  18: 'nfl-new-orleans-saints-team-logo-2-300x300.png',
  19: 'nfl-new-york-giants-team-logo-2-300x300.png',
  20: 'New-York-Jets-logo-2024-300x300.png',
  21: 'nfl-philadelphia-eagles-team-logo-2-300x300.png',
  22: 'nfl-arizona-cardinals-team-logo-2-300x300.png',
  23: 'nfl-pittsburgh-steelers-team-logo-2-300x300.png',
  24: 'nfl-los-angeles-chargers-team-logo-2-300x300.png',
  25: 'nfl-san-francisco-49ers-team-logo-2-300x300.png',
  26: 'nfl-seattle-seahawks-team-logo-2-300x300.png',
  27: 'tampa-bay-buccaneers-2020-logo-300x300.png',
  28: 'washington-commanders-logo-300x300.png',
  29: 'nfl-carolina-panthers-team-logo-2-300x300.png',
  30: 'nfl-jacksonville-jaguars-team-logo-2-300x300.png',
  33: 'nfl-baltimore-ravens-team-logo-2-300x300.png',
  34: 'nfl-houston-texans-team-logo-2-300x300.png',
};

export function getTeamLogoFile(teamId) {
  return TEAM_LOGO_FILES[Number(teamId)] || null;
}

// True when the API sent a usable numeric value (it uses 'N/A' for missing).
export function isNumberLike(value) {
  if (value === null || value === undefined || value === '' || value === 'N/A') return false;
  return Number.isFinite(Number(value));
}

// Print a figure or an em dash when the feed has nothing.
export function figureOrDash(value) {
  return value === null || value === undefined || value === '' || value === 'N/A'
    ? '—'
    : value;
}
