from apscheduler.schedulers.background import BackgroundScheduler
from gamedaybot.espn.espn_bot import espn_bot
from gamedaybot.espn.matchup_periods import get_current_period_info
from espn_api.baseball import League
import logging
import time

logger = logging.getLogger(__name__)

# Per-guild state: guild_id -> last known matchup period
_last_matchup_period = {}

_sched = None


def _get_league(guild_config):
    """Create a League instance from a guild config dict."""
    swid = guild_config.get('swid') or '{1}'
    espn_s2 = guild_config.get('espn_s2') or '1'

    if swid.find("{", 0) == -1:
        swid = "{" + swid
    if swid.find("}", -1) == -1:
        swid = swid + "}"

    league_id = guild_config['league_id']
    year = guild_config.get('league_year', 2026)

    if swid == '{1}' or espn_s2 == '1':
        return League(league_id=league_id, year=year), None, None
    else:
        return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid), espn_s2, swid


def check_matchup_period_change(guild_config):
    """Check for matchup period transition and send recap if changed."""
    guild_id = guild_config['guild_id']
    try:
        league, espn_s2, swid = _get_league(guild_config)
        current_mp = league.currentMatchupPeriod

        if guild_id not in _last_matchup_period:
            _last_matchup_period[guild_id] = current_mp
            logger.info(f"[{guild_id}] Initial matchup period: {current_mp}")
            return

        if current_mp != _last_matchup_period[guild_id]:
            logger.info(f"[{guild_id}] Matchup period changed: {_last_matchup_period[guild_id]} -> {current_mp}")
            _last_matchup_period[guild_id] = current_mp
            if guild_config.get('period_recap', True):
                espn_bot("get_final", guild_config)
                espn_bot("get_standings", guild_config)
                espn_bot("get_matchups", guild_config)

    except Exception as e:
        logger.error(f"[{guild_id}] Error checking matchup period: {e}")


def check_period_ending(guild_config):
    """Send close scores alert if today is the last day of the matchup period."""
    guild_id = guild_config['guild_id']
    if not guild_config.get('close_scores', True):
        return
    try:
        league, espn_s2, swid = _get_league(guild_config)
        info = get_current_period_info(league, espn_s2, swid)
        if info and info['is_last_day']:
            logger.info(f"[{guild_id}] Last day of matchup period {info['period']}")
            espn_bot("get_close_scores", guild_config)
    except Exception as e:
        logger.error(f"[{guild_id}] Error checking period ending: {e}")


def _add_or_remove_job(job_id, enabled, add_fn):
    """Add a job if enabled, remove it if disabled."""
    if enabled:
        add_fn()
    else:
        try:
            _sched.remove_job(job_id)
        except Exception:
            pass


def register_guild_jobs(guild_config):
    """Register all scheduled jobs for a single guild."""
    global _sched
    if _sched is None:
        return

    guild_id = guild_config['guild_id']
    game_timezone = 'America/New_York'
    my_timezone = guild_config.get('timezone', 'America/New_York')
    season_start = '2026-03-25'
    season_end = '2026-10-15'

    prefix = str(guild_id)

    _sched.add_job(check_matchup_period_change, 'interval', hours=2,
                   args=[guild_config],
                   id=f'{prefix}_period_check', replace_existing=True)

    _sched.add_job(check_period_ending, 'cron',
                   args=[guild_config],
                   id=f'{prefix}_close_scores', hour=22, minute=0,
                   start_date=season_start, end_date=season_end,
                   timezone=game_timezone, replace_existing=True)

    _add_or_remove_job(
        f'{prefix}_scoreboard_morning',
        guild_config.get('scoreboard_morning', True),
        lambda: _sched.add_job(espn_bot, 'cron', args=['get_scoreboard_short', guild_config],
                               id=f'{prefix}_scoreboard_morning', hour=8, minute=0,
                               start_date=season_start, end_date=season_end,
                               timezone=my_timezone, replace_existing=True),
    )

    _add_or_remove_job(
        f'{prefix}_scoreboard_evening',
        guild_config.get('scoreboard_evening', True),
        lambda: _sched.add_job(espn_bot, 'cron', args=['get_scoreboard_short', guild_config],
                               id=f'{prefix}_scoreboard_evening', hour=23, minute=0,
                               start_date=season_start, end_date=season_end,
                               timezone=game_timezone, replace_existing=True),
    )

    # Waiver report: Mondays only by default, every day if daily_waiver is enabled
    waiver_dow = 'mon-sun' if guild_config.get('daily_waiver', False) else 'mon'
    _add_or_remove_job(
        f'{prefix}_waiver_report',
        guild_config.get('waiver_report', True),
        lambda: _sched.add_job(espn_bot, 'cron', args=['get_waiver_report', guild_config],
                               id=f'{prefix}_waiver_report', hour=7, minute=32,
                               day_of_week=waiver_dow,
                               start_date=season_start, end_date=season_end,
                               timezone=my_timezone, replace_existing=True),
    )

    _add_or_remove_job(
        f'{prefix}_monitor',
        guild_config.get('monitor_report', True),
        lambda: _sched.add_job(espn_bot, 'cron', args=['get_monitor', guild_config],
                               id=f'{prefix}_monitor', hour=11, minute=0,
                               start_date=season_start, end_date=season_end,
                               timezone=game_timezone, replace_existing=True),
    )

    logger.info(f"[{guild_id}] Scheduled jobs registered")


def remove_guild_jobs(guild_id):
    """Remove all scheduled jobs for a guild."""
    global _sched
    if _sched is None:
        return

    prefixes = [
        f'{guild_id}_period_check',
        f'{guild_id}_close_scores',
        f'{guild_id}_scoreboard_morning',
        f'{guild_id}_scoreboard_evening',
        f'{guild_id}_waiver_report',
        f'{guild_id}_monitor',
    ]
    for job_id in prefixes:
        try:
            _sched.remove_job(job_id)
        except Exception:
            pass

    if guild_id in _last_matchup_period:
        del _last_matchup_period[guild_id]

    logger.info(f"[{guild_id}] Scheduled jobs removed")


def scheduler():
    """
    Start the background scheduler for all configured guilds,
    then block the main thread.
    """
    global _sched
    from gamedaybot.db import get_all_guild_configs

    _sched = BackgroundScheduler(job_defaults={'misfire_grace_time': 15 * 60})
    _sched.start()

    configs = get_all_guild_configs()
    if not configs:
        logger.warning("No guilds configured yet. Use !setup in Discord to add a league.")
    for guild_config in configs:
        register_guild_jobs(guild_config)

    print(f"Scheduler started with {len(configs)} guild(s). Ready!")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        _sched.shutdown()
