import os
import gamedaybot.utils.util as utils


def get_env_vars():
    """Load global (non-league-specific) environment variables."""
    data = {}

    str_limit = 40000  # slack char limit

    try:
        bot_id = os.environ["BOT_ID"]
        str_limit = 1000
    except KeyError:
        bot_id = 1

    try:
        slack_webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    except KeyError:
        slack_webhook_url = 1

    try:
        discord_webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        str_limit = 3000
    except KeyError:
        discord_webhook_url = 1

    try:
        discord_bot_token = os.environ["DISCORD_BOT_TOKEN"]
        str_limit = 3000
    except KeyError:
        discord_bot_token = None

    data['str_limit'] = str_limit
    data['bot_id'] = bot_id
    data['slack_webhook_url'] = slack_webhook_url
    data['discord_webhook_url'] = discord_webhook_url
    data['discord_bot_token'] = discord_bot_token

    try:
        data['db_path'] = os.environ["DB_PATH"]
    except KeyError:
        data['db_path'] = 'guilds.db'

    return data
