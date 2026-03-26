import sys
import os
sys.path.insert(1, os.path.abspath('.'))

from espn_api.baseball import League
import gamedaybot.espn.season_recap as recap
import gamedaybot.espn.functionality as espn
from gamedaybot.chat.discord import Discord
from gamedaybot.chat.slack import Slack
from gamedaybot.chat.groupme import GroupMe

# LEAGUE_ID = os.environ["LEAGUE_ID"]
# LEAGUE_YEAR = os.environ["LEAGUE_YEAR"]

## Manually populate with your baseball league info
LEAGUE_ID = 12345  # Replace with your ESPN baseball league ID
LEAGUE_YEAR = 2025

league = League(league_id=LEAGUE_ID, year=LEAGUE_YEAR)
print(espn.get_scoreboard_short(league))
print(espn.get_scoreboard(league))
print(espn.get_standings(league))
print(espn.get_close_scores(league))
print(espn.get_monitor(league))
print(espn.get_matchups(league))
print(espn.get_trophies(league))

print(recap.win_matrix(league))
print(recap.trophy_recap(league))

try:
    swid = os.environ["SWID"]
except KeyError:
    swid = '{1}'
try:
    espn_s2 = os.environ["ESPN_S2"]
except KeyError:
    espn_s2 = '1'

if swid != '{1}' and espn_s2 != '1':
    league = League(league_id=LEAGUE_ID, year=LEAGUE_YEAR, espn_s2=espn_s2, swid=swid)
    print(espn.get_waiver_report(league))
    print(espn.get_waiver_report(league, True))
