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
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def espn_bot(function):
    """
    Send messages to a messaging platform with information about an ESPN fantasy baseball league.

    Parameters
    ----------
    function: str
        A string that specifies which type of information to send.
    """

    data = get_env_vars()
    str_limit = data['str_limit']

    try:
        bot_id = data['bot_id']
    except KeyError:
        bot_id = 1

    try:
        slack_webhook_url = data['slack_webhook_url']
    except KeyError:
        slack_webhook_url = 1

    try:
        discord_webhook_url = data['discord_webhook_url']
    except KeyError:
        discord_webhook_url = 1

    if (len(str(bot_id)) <= 1 and
        len(str(slack_webhook_url)) <= 1 and
            len(str(discord_webhook_url)) <= 1):
        raise Exception("No messaging platform info provided. Be sure one of BOT_ID, SLACK_WEBHOOK_URL, or DISCORD_WEBHOOK_URL env variables are set")

    league_id = data['league_id']

    try:
        year = int(data['year'])
    except KeyError:
        year = 2026

    try:
        swid = data['swid']
    except KeyError:
        swid = '{1}'

    if swid.find("{", 0) == -1:
        swid = "{" + swid
    if swid.find("}", -1) == -1:
        swid = swid + "}"

    try:
        espn_s2 = data['espn_s2']
    except KeyError:
        espn_s2 = '1'

    try:
        top_half_scoring = util.str_to_bool(data['top_half_scoring'])
    except KeyError:
        top_half_scoring = False

    groupme_bot = GroupMe(bot_id)
    slack_bot = Slack(slack_webhook_url)
    discord_bot = Discord(discord_webhook_url)

    if swid == '{1}' or espn_s2 == '1':
        league = League(league_id=league_id, year=year)
    else:
        league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    try:
        broadcast_message = data['broadcast_message']
    except KeyError:
        broadcast_message = None

    # always let init and broadcast run
    if function not in ["init", "broadcast", "win_matrix", "trophy_recap"] and league.scoringPeriodId > league.finalScoringPeriod:
        logger.info("Not in active season")
        return

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
        # get the scores of last matchup period
        week = league.currentMatchupPeriod - 1
        text = "Final " + espn.get_scoreboard_short(league, week=week)
        text = text + "\n\n" + espn.get_trophies(league, week=week)
    elif function == "get_waiver_report" and swid != '{1}' and espn_s2 != '1':
        faab = league.settings.faab
        text = espn.get_waiver_report(league, faab)
    elif function == "get_monitor":
        text = espn.get_monitor(league)
    elif function == "broadcast":
        try:
            text = broadcast_message
        except KeyError:
            pass
    elif function == "init":
        try:
            text = data["init_msg"]
        except KeyError:
            pass
    else:
        text = "Something bad happened. HALP"

    logger.debug(data)
    if text != '' and text is not None:
        logger.debug(text)
        messages = util.str_limit_check(text, str_limit)
        for message in messages:
            groupme_bot.send_message(message)
            slack_bot.send_message(message)
            discord_bot.send_message(message)


if __name__ == '__main__':
    from gamedaybot.espn.scheduler import scheduler

    espn_bot("init")
    scheduler()
