from apscheduler.schedulers.blocking import BlockingScheduler
from gamedaybot.espn.espn_bot import espn_bot
from gamedaybot.espn.env_vars import get_env_vars
from gamedaybot.espn.matchup_periods import get_current_period_info
from espn_api.baseball import League
import logging

logger = logging.getLogger(__name__)


def _get_league(data):
    """Create a League instance from env var data."""
    swid = data.get('swid', '{1}')
    espn_s2 = data.get('espn_s2', '1')
    league_id = data['league_id']
    year = data.get('year', 2026)

    if swid == '{1}' or espn_s2 == '1':
        return League(league_id=league_id, year=year), None, None
    else:
        return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid), espn_s2, swid


_last_matchup_period = None


def check_matchup_period_change():
    """
    Periodic check for matchup period transitions.
    When a new matchup period starts, send recap of the previous period
    and announce new matchups.
    """
    global _last_matchup_period

    try:
        data = get_env_vars()
        league, espn_s2, swid = _get_league(data)
        current_mp = league.currentMatchupPeriod

        if _last_matchup_period is None:
            # First run - just record the current period
            _last_matchup_period = current_mp
            logger.info(f"Initial matchup period: {current_mp}")
            return

        if current_mp != _last_matchup_period:
            logger.info(f"Matchup period changed: {_last_matchup_period} -> {current_mp}")
            _last_matchup_period = current_mp

            # Send recap of previous period
            espn_bot("get_final")
            espn_bot("get_standings")

            # Send new matchups
            espn_bot("get_matchups")

    except Exception as e:
        logger.error(f"Error checking matchup period: {e}")


def check_period_ending():
    """
    Check if we're on the last day of a matchup period.
    If so, send close scores alert.
    """
    try:
        data = get_env_vars()
        league, espn_s2, swid = _get_league(data)
        info = get_current_period_info(league, espn_s2, swid)

        if info and info['is_last_day']:
            logger.info(f"Last day of matchup period {info['period']}")
            espn_bot("get_close_scores")

    except Exception as e:
        logger.error(f"Error checking period ending: {e}")


def scheduler():
    """
    Schedule jobs for MLB fantasy baseball alerts.

    Uses a hybrid approach:
    - Periodic check (every 2 hours) detects matchup period transitions
      and sends recaps/new matchups automatically
    - Daily cron jobs handle routine alerts (scoreboard, monitor, waivers)
    - Evening check on last day of period sends close scores
    """
    data = get_env_vars()
    game_timezone = 'America/New_York'
    sched = BlockingScheduler(job_defaults={'misfire_grace_time': 15 * 60})
    season_start_date = data['season_start_date']
    season_end_date = data['season_end_date']
    my_timezone = data['my_timezone']

    # === Matchup period transition detection ===
    # Check every 2 hours for period changes (sends final/standings/matchups)
    sched.add_job(check_matchup_period_change, 'interval', hours=2,
                  id='period_check', replace_existing=True)

    # === Last day of period: close scores ===
    # Check every evening - only sends if it's actually the last day
    sched.add_job(check_period_ending, 'cron',
                  id='close_scores', hour=22, minute=0,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=game_timezone, replace_existing=True)

    # === Daily alerts ===

    # Morning score update
    sched.add_job(espn_bot, 'cron', ['get_scoreboard_short'], id='scoreboard_morning',
                  hour=8, minute=0,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)

    # Evening score update (after most games finish)
    sched.add_job(espn_bot, 'cron', ['get_scoreboard_short'], id='scoreboard_evening',
                  hour=23, minute=0,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=game_timezone, replace_existing=True)

    # Waiver report
    sched.add_job(espn_bot, 'cron', ['get_waiver_report'], id='waiver_report',
                  hour=7, minute=32,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)

    # Player monitor - before games start
    if data['monitor_report']:
        sched.add_job(espn_bot, 'cron', ['get_monitor'], id='monitor',
                      hour=11, minute=0,
                      start_date=season_start_date, end_date=season_end_date,
                      timezone=game_timezone, replace_existing=True)

    # Log period info on startup
    try:
        league, espn_s2, swid = _get_league(data)
        info = get_current_period_info(league, espn_s2, swid)
        if info:
            print(f"Current matchup period: {info['period']} of {info['total_periods']}")
            print(f"Period dates: {info['start']} to {info['end']}")
            print(f"Days remaining: {info['days_remaining']}")
        else:
            print("Could not determine matchup period info (season may not have started)")
    except Exception as e:
        print(f"Could not fetch period info: {e}")

    print("Ready!")
    sched.start()
