import os
if os.environ.get("AWS_EXECUTION_ENV") is not None:
    import espn.functionality as espn
else:
    import sys
    sys.path.insert(1, os.path.abspath('.'))
    import gamedaybot.espn.functionality as espn


def trophy_recap(league):
    """
    Season recap showing trophy counts for each team across all matchup periods.
    """
    ICONS = ['HC', 'LC', 'BO', 'CW', 'LK', 'UL']
    legend = ['*LEGEND*', 'HC: Most Points/Cat Wins', 'LC: Least Points/Cat Wins',
              'BO: Blown out', 'CW: Close wins', 'LK: Lucky', 'UL: Unlucky']
    team_trophies = {}

    for team in league.teams:
        team_trophies[team.team_abbrev] = [0 for _ in range(len(ICONS))]

    for week in range(1, league.currentMatchupPeriod):
        try:
            high_score_team, low_score_team, blown_out_team, close_win_team = espn.get_trophies(league=league, week=week, recap=True)
            if high_score_team:
                team_trophies[high_score_team][0] += 1
            if low_score_team:
                team_trophies[low_score_team][1] += 1
            if blown_out_team:
                team_trophies[blown_out_team][2] += 1
            if close_win_team:
                team_trophies[close_win_team][3] += 1
        except Exception:
            pass

        try:
            lucky_team, unlucky_team, scores = espn.get_lucky_trophy(league=league, week=week, recap=True)
            if lucky_team:
                team_trophies[lucky_team][4] += 1
            if unlucky_team:
                team_trophies[unlucky_team][5] += 1
        except Exception:
            pass

    result = 'Season Recap!\n'
    result += "Team".ljust(7, ' ')
    for icon in ICONS:
        result += icon + ' '
    result += '\n'
    for team_name, trophies in team_trophies.items():
        result += f"{team_name.ljust(5, ' ')}: {trophies}\n"
    result += '\n'.join(legend)

    return result


def win_matrix(league):
    """
    Standings if every team played every other team every matchup period.
    """
    team_record = {team.team_abbrev: [0, 0] for team in league.teams}

    for week in range(1, league.currentMatchupPeriod):
        scores = espn.get_weekly_score_with_win_loss(league=league, week=week)
        losses = 0
        for team in scores:
            team_record[team.team_abbrev][0] += len(scores) - 1 - losses
            team_record[team.team_abbrev][1] += losses
            losses += 1

    # Avoid division by zero
    team_record = dict(sorted(team_record.items(),
                               key=lambda item: item[1][0] / max(item[1][1], 1),
                               reverse=True))

    standings_txt = ["Standings if everyone played every team every matchup period"]
    pos = 1
    for team in team_record:
        standings_txt += [f"{pos:2}. {team:4} ({team_record[team][0]}-{team_record[team][1]})"]
        pos += 1

    return '\n'.join(standings_txt)
