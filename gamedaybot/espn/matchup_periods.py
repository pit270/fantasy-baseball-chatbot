import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_num_matchup_periods(league):
    """Get the number of matchup periods from the league schedule."""
    try:
        matchup_ids = set()
        for team in league.teams:
            matchup_ids.update(range(1, len(team.schedule) + 1))
        return len(matchup_ids) if matchup_ids else 21
    except Exception:
        return len(league.settings.matchup_periods) or 21


def get_game_dates(year, espn_s2=None, swid=None):
    """
    Fetch all MLB game dates for a season from ESPN's pro team schedule API.
    Returns a sorted list of date objects.
    """
    url = f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{year}?view=proTeamSchedules_wl'

    cookies = {}
    if espn_s2 and swid:
        cookies = {'espn_s2': espn_s2, 'SWID': swid}

    try:
        resp = requests.get(url, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch pro team schedule: {e}")
        return []

    game_dates = set()
    pro_teams = data.get('settings', {}).get('proTeams', [])
    for team in pro_teams:
        games_by_period = team.get('proGamesByScoringPeriod', {})
        for scoring_period, games in games_by_period.items():
            for game in games:
                epoch_ms = game.get('date', 0)
                if epoch_ms:
                    game_date = datetime.fromtimestamp(epoch_ms / 1000.0).date()
                    game_dates.add(game_date)

    return sorted(game_dates)


def find_allstar_break(game_dates):
    """
    Find the All-Star break: the largest gap of 4+ days where the
    first date is in June or July.
    Returns (gap_start_date, gap_end_date) or (None, None).
    """
    best_gap_start = None
    best_gap_end = None
    best_gap_days = 0

    for i in range(len(game_dates) - 1):
        gap = (game_dates[i + 1] - game_dates[i]).days
        if gap >= 4 and game_dates[i].month in (6, 7):
            if gap > best_gap_days:
                best_gap_days = gap
                best_gap_start = game_dates[i]
                best_gap_end = game_dates[i + 1]

    return best_gap_start, best_gap_end


def build_matchup_period_dates(year, num_weeks, espn_s2=None, swid=None):
    """
    Build matchup period boundaries from MLB game dates.

    Returns a list of (start_date, end_date) tuples, one per matchup period.

    Algorithm:
    - Week 1: starts on the Wednesday on or before Opening Day,
      ends on the first Sunday that gives at least 7 days.
    - All-Star break: if a week contains the break start, extend to 14 days.
    - Regular weeks: Monday through Sunday (7 days).
    """
    game_dates = get_game_dates(year, espn_s2, swid)
    if not game_dates:
        logger.warning("No game dates found, cannot build matchup periods")
        return []

    opening_day = game_dates[0]
    allstar_start, allstar_end = find_allstar_break(game_dates)

    periods = []

    # Week 1: find the Wednesday on or before Opening Day
    # weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    days_since_wed = (opening_day.weekday() - 2) % 7
    week1_start = opening_day - timedelta(days=days_since_wed)

    # Find the first Sunday after week1_start
    days_until_sunday = (6 - week1_start.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    first_sunday = week1_start + timedelta(days=days_until_sunday)

    # If less than 7 days from start to that Sunday, use next Sunday
    if (first_sunday - week1_start).days < 7:
        first_sunday += timedelta(days=7)

    periods.append((week1_start, first_sunday))

    # Build remaining weeks
    current_start = first_sunday + timedelta(days=1)  # Monday after week 1

    for _ in range(1, num_weeks):
        week_end = current_start + timedelta(days=6)  # Sunday

        # Check if this week contains the All-Star break
        if allstar_start and current_start <= allstar_start <= week_end:
            # Extend to 14 days (two Mon-Sun spans merged)
            week_end = current_start + timedelta(days=13)

        periods.append((current_start, week_end))
        current_start = week_end + timedelta(days=1)  # Next Monday

    return periods


def get_current_period_info(league, espn_s2=None, swid=None):
    """
    Get info about the current matchup period.
    Returns a dict with:
      - period: current matchup period number
      - start: start date
      - end: end date
      - days_remaining: days until end of period
      - is_last_day: True if today is the last day of the period
      - is_first_day: True if today is the first day of a new period
    """
    num_weeks = get_num_matchup_periods(league)
    periods = build_matchup_period_dates(league.year, num_weeks, espn_s2, swid)

    if not periods:
        return None

    today = datetime.now().date()
    current_mp = league.currentMatchupPeriod

    # Clamp to valid range
    idx = min(current_mp - 1, len(periods) - 1)
    start, end = periods[idx]

    days_remaining = (end - today).days

    return {
        'period': current_mp,
        'start': start,
        'end': end,
        'days_remaining': days_remaining,
        'is_last_day': today == end,
        'is_first_day': today == start,
        'total_periods': len(periods),
        'all_periods': periods,
    }
