import os
if os.environ.get("AWS_EXECUTION_ENV") is not None:
    import utils.util as util
    from chat.groupme import GroupMe
    from chat.slack import Slack
    from chat.discord import Discord
else:
    import sys
    sys.path.insert(1, os.path.abspath('.'))
    import gamedaybot.utils.util as util
    from gamedaybot.chat.groupme import GroupMe
    from gamedaybot.chat.slack import Slack
    from gamedaybot.chat.discord import Discord
    from gamedaybot.espn.env_vars import get_env_vars
    import gamedaybot.espn.functionality as espn
    import gamedaybot.espn.season_recap as recap


from espn_api.baseball import League
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _make_league(guild_config):
    """Create an ESPN League object from a guild config dict."""
    league_id = guild_config['league_id']
    year = guild_config.get('league_year', 2026)
    espn_s2 = guild_config.get('espn_s2') or '1'
    swid = guild_config.get('swid') or '{1}'

    if swid.find("{", 0) == -1:
        swid = "{" + swid
    if swid.find("}", -1) == -1:
        swid = swid + "}"

    if swid == '{1}' or espn_s2 == '1':
        return League(league_id=league_id, year=year), '1', '{1}'
    else:
        return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid), espn_s2, swid


def generate_report(function, guild_config):
    """
    Generate report text for a given function name and guild config.

    Parameters
    ----------
    function: str
        A string that specifies which type of report to generate.
    guild_config: dict
        Guild configuration dict (from db.get_guild_config or similar).

    Returns
    -------
    str or None
        The generated report text, or None if no report could be generated.
    """
    league, espn_s2, swid = _make_league(guild_config)
    top_half_scoring = bool(guild_config.get('top_half_scoring', False))

    # always let init and broadcast run
    if function not in ["init", "broadcast", "win_matrix", "trophy_recap"] and league.scoringPeriodId > league.finalScoringPeriod:
        logger.info("Not in active season")
        return None

    text = ''
    logger.info("Function: " + function)

    if function == "get_matchups":
        text = espn.get_matchups(league)
    elif function == "get_scoreboard":
        text = espn.get_scoreboard(league)
    elif function == "get_scoreboard_short":
        text = espn.get_scoreboard_short(league)
    elif function == "get_close_scores":
        text = espn.get_close_scores(league)
    elif function == "get_standings":
        text = espn.get_standings(league, top_half_scoring)
    elif function == "get_trophies":
        text = espn.get_trophies(league)
    elif function == "win_matrix":
        text = recap.win_matrix(league)
    elif function == "trophy_recap":
        text = recap.trophy_recap(league)
    elif function == "get_final":
        week = league.currentMatchupPeriod - 1
        text = "Final " + espn.get_scoreboard_short(league, week=week)
        text = text + "\n\n" + espn.get_trophies(league, week=week)
    elif function == "get_waiver_report" and swid != '{1}' and espn_s2 != '1':
        faab = league.settings.faab
        text = espn.get_waiver_report(league, faab)
    elif function == "get_monitor":
        text = espn.get_monitor(league)
    else:
        return None

    if text != '' and text is not None:
        return text
    return None


def espn_bot(function, guild_config):
    """
    Send messages to all configured platforms for a guild.

    Parameters
    ----------
    function: str
        Report type to generate and send.
    guild_config: dict
        Guild configuration dict containing messaging platform settings.
    """
    from gamedaybot.chat.discord_bot import send_message as discord_bot_send

    text = generate_report(function, guild_config)
    if not text:
        return

    logger.debug(text)

    # GroupMe and Slack still read from env vars for backward compat
    data = get_env_vars()
    str_limit = data.get('str_limit', 3000)

    bot_id = data.get('bot_id', 1)
    slack_webhook_url = data.get('slack_webhook_url', 1)
    discord_webhook_url = data.get('discord_webhook_url', 1)

    groupme_bot = GroupMe(bot_id)
    slack_bot = Slack(slack_webhook_url)
    discord_webhook = Discord(discord_webhook_url)

    guild_id = guild_config.get('guild_id')
    channel_id = guild_config.get('channel_id')
    use_discord_bot = bool(channel_id)

    messages = util.str_limit_check(text, str_limit)
    for message in messages:
        groupme_bot.send_message(message)
        slack_bot.send_message(message)
        if use_discord_bot:
            discord_bot_send(message, channel_id=channel_id)
        else:
            discord_webhook.send_message(message)


if __name__ == '__main__':
    from gamedaybot.espn.scheduler import scheduler
    from gamedaybot.chat.discord_bot import start_discord_bot
    from gamedaybot.db import init_db
    from gamedaybot.espn.env_vars import get_env_vars

    init_db()

    data = get_env_vars()
    discord_token = data.get('discord_bot_token')
    if discord_token:
        start_discord_bot(discord_token)

    scheduler()
