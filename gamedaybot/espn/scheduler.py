from apscheduler.schedulers.blocking import BlockingScheduler
from gamedaybot.espn.espn_bot import espn_bot
from gamedaybot.espn.env_vars import get_env_vars


def scheduler():
    """
    Schedule jobs for MLB fantasy baseball alerts.

    MLB season runs ~late March through October with games almost every day.
    Matchup periods are typically weekly (Monday-Sunday).

    Schedule:
    - Monday morning:    Final scores + trophies from previous matchup period
    - Monday morning:    Standings
    - Monday morning:    Waiver report (if enabled)
    - Monday evening:    New matchups for the week
    - Daily morning:     Score update (Tue-Sun)
    - Daily morning:     Waiver report (if daily_waiver enabled)
    - Daily evening:     Score update (games typically 7pm+ ET)
    - Daily:             Player monitor (if enabled)
    """
    data = get_env_vars()
    game_timezone = 'America/New_York'
    sched = BlockingScheduler(job_defaults={'misfire_grace_time': 15 * 60})
    season_start_date = data['season_start_date']
    season_end_date = data['season_end_date']
    my_timezone = data['my_timezone']

    # Monday: end of matchup period recap
    sched.add_job(espn_bot, 'cron', ['get_final'], id='final',
                  day_of_week='mon', hour=7, minute=30, start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)
    sched.add_job(espn_bot, 'cron', ['get_standings'], id='standings',
                  day_of_week='mon', hour=7, minute=31, start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)
    sched.add_job(espn_bot, 'cron', ['get_waiver_report'], id='waiver_report',
                  day_of_week='mon', hour=7, minute=32, start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)

    # Monday evening: new matchups
    sched.add_job(espn_bot, 'cron', ['get_matchups'], id='matchups',
                  day_of_week='mon', hour=10, minute=0, start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)

    # Daily waiver report (if enabled)
    if data['daily_waiver']:
        sched.add_job(
            espn_bot, 'cron', ['get_waiver_report'],
            id='daily_waiver_report', day_of_week='tue,wed,thu,fri,sat,sun', hour=7, minute=32,
            start_date=season_start_date, end_date=season_end_date,
            timezone=my_timezone, replace_existing=True)

    # Daily score updates - morning and evening
    sched.add_job(espn_bot, 'cron', ['get_scoreboard_short'], id='scoreboard_morning',
                  day_of_week='tue,wed,thu,fri,sat,sun', hour=8, minute=0,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=my_timezone, replace_existing=True)
    sched.add_job(espn_bot, 'cron', ['get_scoreboard_short'], id='scoreboard_evening',
                  day_of_week='mon,tue,wed,thu,fri,sat,sun', hour=23, minute=0,
                  start_date=season_start_date, end_date=season_end_date,
                  timezone=game_timezone, replace_existing=True)

    # Close scores check - Sunday evening (end of typical matchup period)
    sched.add_job(espn_bot, 'cron', ['get_close_scores'], id='close_scores',
                  day_of_week='sun', hour=22, minute=0, start_date=season_start_date, end_date=season_end_date,
                  timezone=game_timezone, replace_existing=True)

    # Player monitor - daily before games start
    if data['monitor_report']:
        sched.add_job(espn_bot, 'cron', ['get_monitor'], id='monitor',
                      day_of_week='mon,tue,wed,thu,fri,sat,sun', hour=11, minute=0,
                      start_date=season_start_date, end_date=season_end_date,
                      timezone=game_timezone, replace_existing=True)

    print("Ready!")
    sched.start()
