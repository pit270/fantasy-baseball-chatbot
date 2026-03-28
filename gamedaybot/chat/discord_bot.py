import discord
from discord.ext import commands
import threading
import asyncio
import logging

logger = logging.getLogger(__name__)

_bot = None
_loop = None
_channel_id = None

COMMAND_MAP = {
    'scores': ('get_scoreboard_short', 'Current matchup scores'),
    'matchups': ('get_matchups', 'Who is playing who this week'),
    'standings': ('get_standings', 'League standings'),
    'trophies': ('get_trophies', 'Awards for the current week'),
    'close': ('get_close_scores', 'Matchups that are too close to call'),
    'transactions': ('get_waiver_report', "Today's adds and drops"),
    'injuries': ('get_monitor', 'Injured or IL-ineligible players in starting lineups'),
    'results': ('get_final', 'Final scores and awards from last week'),
    'allplay': ('win_matrix', 'Standings if every team played each other every week'),
    'seasonrecap': ('trophy_recap', 'Trophy counts for the entire season'),
}


def create_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"Discord bot logged in as {bot.user}")

    async def handle_report(ctx, function_name):
        from gamedaybot.espn.espn_bot import generate_report
        import gamedaybot.utils.util as util

        try:
            text = await asyncio.to_thread(generate_report, function_name)
        except Exception as e:
            logger.error(f"Error generating report '{function_name}': {e}")
            await ctx.send(f"```Error generating report: {e}```")
            return

        if not text:
            await ctx.send("```No data available```")
            return

        messages = util.str_limit_check(text, 1900)
        for message in messages:
            await ctx.send(f"```{message}```")

    for cmd_name, (function_name, description) in COMMAND_MAP.items():
        @bot.command(name=cmd_name, help=description)
        async def command_handler(ctx, _fn=function_name):
            await handle_report(ctx, _fn)

    return bot


def send_message(text):
    """Send a message to the configured Discord channel from any thread."""
    if not _bot or not _loop or not _channel_id:
        logger.warning("Discord bot not initialized, skipping message")
        return

    async def _send():
        channel = _bot.get_channel(_channel_id)
        if not channel:
            logger.error(f"Discord channel {_channel_id} not found")
            return
        import gamedaybot.utils.util as util
        messages = util.str_limit_check(text, 1900)
        for message in messages:
            await channel.send(f"```{message}```")

    future = asyncio.run_coroutine_threadsafe(_send(), _loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        logger.error(f"Error sending Discord message: {e}")


def start_discord_bot(token, channel_id):
    """Start the Discord bot in a daemon thread."""
    global _bot, _loop, _channel_id
    _channel_id = int(channel_id) if channel_id else None

    def run():
        global _bot, _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _bot = create_bot()
        _loop.run_until_complete(_bot.start(token))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("Discord bot started in background thread")
