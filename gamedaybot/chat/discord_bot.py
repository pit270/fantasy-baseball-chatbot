import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import threading
import asyncio
import logging

logger = logging.getLogger(__name__)

_bot = None
_loop = None

COMMAND_MAP = {
    'scores': ('get_scoreboard_short', 'Current matchup scores'),
    'matchups': ('get_matchups', 'Who is playing who this week'),
    'standings': ('get_standings', 'League standings'),
    'trophies': ('get_trophies', 'Awards for the current week'),
    'close': ('get_close_scores', 'Matchups that are too close to call'),
    'injuries': ('get_monitor', 'Injured or IL-ineligible players in starting lineups'),
    'results': ('get_final', 'Final scores and awards from last week'),
    'allplay': ('win_matrix', 'Standings if every team played each other every week'),
    'seasonrecap': ('trophy_recap', 'Trophy counts for the entire season'),
}


def _is_admin(member):
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild


class SetupModal(discord.ui.Modal, title='Fantasy Baseball Bot Setup'):
    league_id = discord.ui.TextInput(
        label='ESPN League ID',
        placeholder='Found in your ESPN league URL',
        required=True,
        max_length=20,
    )
    alert_channel = discord.ui.TextInput(
        label='Alert Channel Name',
        placeholder='e.g. fantasy-alerts (leave blank for this channel)',
        required=False,
        max_length=100,
    )
    espn_s2 = discord.ui.TextInput(
        label='ESPN S2 Cookie (private leagues only)',
        placeholder='Leave blank for public leagues',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    swid = discord.ui.TextInput(
        label='ESPN SWID Cookie (private leagues only)',
        placeholder='e.g. {B29ADE85-146F-...} — leave blank for public leagues',
        required=False,
        max_length=50,
    )

    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self._source_interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        from gamedaybot.db import save_guild_config, get_guild_config
        from gamedaybot.espn.scheduler import register_guild_jobs

        guild_id = interaction.guild_id
        source = self._source_interaction

        # Resolve alert channel
        channel_name = self.alert_channel.value.strip().lstrip('#')
        if channel_name:
            matched = discord.utils.get(interaction.guild.text_channels, name=channel_name)
            channel_id = str(matched.id) if matched else str(source.channel_id)
        else:
            channel_id = str(source.channel_id)

        updates = {'league_id': self.league_id.value.strip(), 'channel_id': channel_id}
        if self.espn_s2.value.strip():
            updates['espn_s2'] = self.espn_s2.value.strip()
        if self.swid.value.strip():
            updates['swid'] = self.swid.value.strip()

        save_guild_config(guild_id, **updates)

        full_config = get_guild_config(guild_id)
        if full_config and full_config.get('league_id'):
            await asyncio.to_thread(register_guild_jobs, full_config)

        ch = interaction.guild.get_channel(int(channel_id))
        channel_display = f'#{ch.name}' if ch else channel_id

        await interaction.response.send_message(
            f"✅ **Setup complete!**\n"
            f"```"
            f"League ID:     {updates['league_id']}\n"
            f"Alert channel: {channel_display}\n"
            f"ESPN auth:     {'configured' if updates.get('espn_s2') else 'not set (public league)'}"
            f"```\n"
            "Run `/status` anytime to review your settings.",
            ephemeral=True,
        )


def create_bot():
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='/', intents=intents)

    @bot.event
    async def on_ready():
        import os
        guild_id = os.environ.get('DISCORD_GUILD_ID')
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Slash commands synced to guild {guild_id} ({len(synced)} commands) — available immediately")
        else:
            synced = await bot.tree.sync()
            print(f"Slash commands synced globally ({len(synced)} commands) — may take up to 1 hour to appear")
        logger.info(f"Discord bot logged in as {bot.user}")

    async def _send_report(interaction: discord.Interaction, function_name: str):
        from gamedaybot.espn.espn_bot import generate_report
        from gamedaybot.db import get_guild_config
        import gamedaybot.utils.util as util

        guild_config = get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config.get('league_id'):
            await interaction.response.send_message(
                "```This server hasn't been set up yet. Run /setup to configure your league.```",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            text = await asyncio.to_thread(generate_report, function_name, guild_config)
        except Exception as e:
            logger.error(f"Error generating report '{function_name}': {e}")
            await interaction.followup.send(f"```Error generating report: {e}```")
            return

        if not text:
            await interaction.followup.send("```No data available```")
            return

        messages = util.str_limit_check(text, 1900)
        for message in messages:
            await interaction.followup.send(f"```{message}```")

    # Register report slash commands
    def make_command(fn_name):
        async def _cmd(interaction: discord.Interaction):
            await _send_report(interaction, fn_name)
        return _cmd

    for cmd_name, (function_name, description) in COMMAND_MAP.items():
        bot.tree.command(name=cmd_name, description=description)(make_command(function_name))

    @bot.tree.command(name='transactions', description="Recent adds and drops")
    @app_commands.describe(days='How many days to look back (default 1 = last 24 hours; 2+ aligns to midnight)')
    async def transactions(interaction: discord.Interaction, days: Optional[int] = 1):
        from gamedaybot.espn.espn_bot import generate_report
        from gamedaybot.db import get_guild_config
        import gamedaybot.utils.util as util

        if days < 1:
            await interaction.response.send_message("```days must be 1 or more.```", ephemeral=True)
            return

        guild_config = get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config.get('league_id'):
            await interaction.response.send_message(
                "```This server hasn't been set up yet. Run /setup to configure your league.```",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            text = await asyncio.to_thread(generate_report, 'get_waiver_report', guild_config, days)
        except Exception as e:
            logger.error(f"Error generating waiver report: {e}")
            await interaction.followup.send(f"```Error generating report: {e}```")
            return

        if not text:
            await interaction.followup.send("```No data available```")
            return

        for message in util.str_limit_check(text, 1900):
            await interaction.followup.send(f"```{message}```")

    @bot.tree.command(name='setup', description='Configure the bot for your league (admin only)')
    async def setup(interaction: discord.Interaction):
        if not _is_admin(interaction.user):
            await interaction.response.send_message(
                "```Only server admins can run /setup.```", ephemeral=True
            )
            return
        await interaction.response.send_modal(SetupModal(interaction))

    @bot.tree.command(name='status', description='Show current bot configuration for this server')
    async def status(interaction: discord.Interaction):
        from gamedaybot.db import get_guild_config
        config = get_guild_config(interaction.guild_id)
        if not config or not config.get('league_id'):
            await interaction.response.send_message(
                "```Not configured. Run /setup to get started.```", ephemeral=True
            )
            return

        def _on(key, default=1):
            return 'on' if config.get(key, default) else 'off'

        channel_id = config.get('channel_id')
        lines = [
            f"League ID:          {config.get('league_id', 'not set')}",
            f"Year:               {config.get('league_year', 2026)}",
            f"Alert channel:      {channel_id or 'not set'}",
            f"Timezone:           {config.get('timezone', 'America/New_York')}",
            f"ESPN auth:          {'set' if config.get('espn_s2') else 'not set'}",
            f"",
            f"Scheduled alerts:",
            f"  Scoreboard (8am): {_on('scoreboard_morning')}",
            f"  Scoreboard (11pm):{_on('scoreboard_evening')}",
            f"  Waivers:          {'daily' if config.get('daily_waiver') else 'Mondays'}",
            f"  Injuries:         {_on('monitor_report')}",
            f"  Close scores:     {_on('close_scores')}",
            f"  Period recap:     {_on('period_recap')}",
        ]
        await interaction.response.send_message(
            "```" + "\n".join(lines) + "```", ephemeral=True
        )

    @bot.tree.command(name='config', description='Toggle scheduled alerts (admin only)')
    @app_commands.describe(
        scoreboard_morning='Morning score update at 8am (your timezone)',
        scoreboard_evening='Evening score update at 11pm ET',
        waivers='Waiver report frequency',
        injuries='Daily injured/IL starters alert at 11am ET',
        close_scores='Close scores alert on last day of each week',
        period_recap='End-of-week recap: results, standings, matchups',
        timezone='Your timezone, e.g. America/Chicago or America/Los_Angeles',
    )
    @app_commands.choices(waivers=[
        app_commands.Choice(name='Daily (Mon–Sun)', value='daily'),
        app_commands.Choice(name='Mondays only', value='monday'),
        app_commands.Choice(name='Off', value='off'),
    ])
    async def config(
        interaction: discord.Interaction,
        scoreboard_morning: Optional[bool] = None,
        scoreboard_evening: Optional[bool] = None,
        waivers: Optional[str] = None,
        injuries: Optional[bool] = None,
        close_scores: Optional[bool] = None,
        period_recap: Optional[bool] = None,
        timezone: Optional[str] = None,
    ):
        from gamedaybot.db import get_guild_config, save_guild_config
        from gamedaybot.espn.scheduler import register_guild_jobs

        if not _is_admin(interaction.user):
            await interaction.response.send_message(
                "```Only server admins can run /config.```", ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        config = get_guild_config(guild_id)
        if not config or not config.get('league_id'):
            await interaction.response.send_message(
                "```Not configured yet. Run /setup first.```", ephemeral=True
            )
            return

        updates = {}
        if scoreboard_morning is not None:
            updates['scoreboard_morning'] = int(scoreboard_morning)
        if scoreboard_evening is not None:
            updates['scoreboard_evening'] = int(scoreboard_evening)
        if waivers is not None:
            updates['waiver_report'] = 0 if waivers == 'off' else 1
            updates['daily_waiver'] = 1 if waivers == 'daily' else 0
        if injuries is not None:
            updates['monitor_report'] = int(injuries)
        if close_scores is not None:
            updates['close_scores'] = int(close_scores)
        if period_recap is not None:
            updates['period_recap'] = int(period_recap)
        if timezone is not None:
            updates['timezone'] = timezone.strip()

        if not updates:
            await interaction.response.send_message(
                "```No changes specified.```", ephemeral=True
            )
            return

        save_guild_config(guild_id, **updates)

        # Re-register scheduler jobs to apply changes
        full_config = get_guild_config(guild_id)
        await asyncio.to_thread(register_guild_jobs, full_config)

        def _on(key, default=1):
            return 'on' if full_config.get(key, default) else 'off'

        lines = [
            "Settings updated!",
            f"",
            f"  Scoreboard (8am): {_on('scoreboard_morning')}",
            f"  Scoreboard (11pm):{_on('scoreboard_evening')}",
            f"  Waivers:          {'off' if not full_config.get('waiver_report', 1) else ('daily' if full_config.get('daily_waiver') else 'Mondays')}",
            f"  Injuries:         {_on('monitor_report')}",
            f"  Close scores:     {_on('close_scores')}",
            f"  Period recap:     {_on('period_recap')}",
            f"  Timezone:         {full_config.get('timezone', 'America/New_York')}",
        ]
        await interaction.response.send_message(
            "```" + "\n".join(lines) + "```", ephemeral=True
        )

    return bot


def _send_via_rest(text, channel_id):
    """Send a message via Discord's REST API using the bot token (no client needed)."""
    import os
    import requests
    import gamedaybot.utils.util as util

    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        logger.warning("DISCORD_BOT_TOKEN not set, cannot send via REST")
        return

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {'Authorization': f'Bot {token}', 'Content-Type': 'application/json'}
    for message in util.str_limit_check(text, 1900):
        r = requests.post(url, json={'content': f'```{message}```'}, headers=headers)
        if r.status_code not in (200, 201):
            logger.error(f"Discord REST send failed: {r.status_code} {r.text}")


def send_message(text, channel_id=None):
    """Send a message to a specific Discord channel from any thread."""
    if not channel_id:
        logger.warning("No channel_id provided, skipping message")
        return

    if not _bot or not _loop:
        _send_via_rest(text, channel_id)
        return

    async def _send():
        ch = _bot.get_channel(int(channel_id))
        if not ch:
            logger.error(f"Discord channel {channel_id} not found")
            return
        import gamedaybot.utils.util as util
        for message in util.str_limit_check(text, 1900):
            await ch.send(f"```{message}```")

    future = asyncio.run_coroutine_threadsafe(_send(), _loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        logger.error(f"Error sending Discord message: {e}")


def start_discord_bot(token):
    """Start the Discord bot in a daemon thread."""
    global _bot, _loop

    def run():
        global _bot, _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _bot = create_bot()
        _loop.run_until_complete(_bot.start(token))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("Discord bot started in background thread")
