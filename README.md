# ESPN Fantasy Baseball Chat Bot

This is a GroupMe, Discord, or Slack chat bot for ESPN Fantasy Baseball leagues.

Adapted from [dtcarls/fantasy_football_chat_bot](https://github.com/dtcarls/fantasy_football_chat_bot) for baseball.

> **AI Disclaimer:** This codebase has been significantly modified by AI (Claude by Anthropic). The conversion from fantasy football to fantasy baseball, including matchup period derivation, scheduling logic, and multi-format scoring support, was generated with AI assistance.

## What does this do?

Sends automated messages about your ESPN Fantasy Baseball league on a schedule tuned for the MLB season (late March - October):

| Message | Schedule | Description |
|---------|----------|-------------|
| Final Scores + Trophies | Monday 7:30am local | Previous matchup period results and awards |
| Standings | Monday 7:31am local | Current league standings |
| Waiver Report | Monday 7:32am local | Waiver transactions (if enabled) |
| Matchups | Monday 10:00am local | New matchup period pairings |
| Morning Score Update | Tue-Sun 8:00am local | Current scoreboard |
| Evening Score Update | Daily 11:00pm ET | End-of-day scores |
| Close Scores | Sunday 10:00pm ET | Tight matchups heading into end of period |
| Player Monitor | Daily 11:00am ET | Injured players in starting lineups (if enabled) |
| Daily Waiver Report | Tue-Sun 7:32am local | Daily transactions (if `DAILY_WAIVER` enabled) |

Supports both **H2H Points** and **H2H Categories** scoring formats.

## Setup

### Chat Platform Setup

Set up at least one of GroupMe, Slack, or Discord:

- **GroupMe**: Create a bot at https://dev.groupme.com and get the `BOT_ID`
- **Slack**: Create an incoming webhook at https://api.slack.com/apps and get the `SLACK_WEBHOOK_URL`
- **Discord**: Create a webhook in your server settings and get the `DISCORD_WEBHOOK_URL`

### Environment Variables

| Var | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| BOT_ID | String | For GroupMe | None | GroupMe Bot ID |
| SLACK_WEBHOOK_URL | String | For Slack | None | Slack incoming webhook URL |
| DISCORD_WEBHOOK_URL | String | For Discord | None | Discord webhook URL |
| LEAGUE_ID | String | Yes | None | ESPN Fantasy Baseball league ID |
| LEAGUE_YEAR | String | No | 2026 | ESPN league season year |
| START_DATE | Date | No | 2026-03-26 | When the bot starts sending messages (YYYY-MM-DD) |
| END_DATE | Date | No | 2026-10-15 | When the bot stops sending messages (YYYY-MM-DD) |
| TIMEZONE | String | No | America/New_York | Timezone for scheduled messages |
| INIT_MSG | String | No | None | Message sent on bot startup |
| TOP_HALF_SCORING | Bool | No | False | Include top-half scoring bonus wins in standings |
| MONITOR_REPORT | Bool | No | True | Enable daily player injury monitor |
| WAIVER_REPORT | Bool | No | False | Enable waiver reports (requires ESPN_S2 + SWID) |
| DAILY_WAIVER | Bool | No | False | Send waiver reports daily instead of just Mondays |
| ESPN_S2 | String | For private leagues | None | ESPN auth cookie |
| SWID | String | For private leagues | None | ESPN auth cookie |

### Running with Docker

```bash
docker-compose up -d
```

Edit `docker-compose.yml` to set your environment variables first.

### Running without Docker

```bash
pip install -r requirements.txt
export LEAGUE_ID=your_league_id
export DISCORD_WEBHOOK_URL=your_webhook_url
python3 gamedaybot/espn/espn_bot.py
```

### Running Tests

```bash
pip install -r requirements-test.txt
pytest
```

## Private Leagues

For private leagues, you need `ESPN_S2` and `SWID` cookies:

1. Log into your ESPN Fantasy Baseball account in Chrome
2. Right-click anywhere and select Inspect
3. Go to Application > Storage > Cookies > `http://fantasy.espn.com`
4. Find and copy the `espn_s2` and `SWID` values

## Credits

Based on [fantasy_football_chat_bot](https://github.com/dtcarls/fantasy_football_chat_bot) by Dean Carlson.
Uses the [espn_api](https://github.com/cwendt94/espn-api) library.
