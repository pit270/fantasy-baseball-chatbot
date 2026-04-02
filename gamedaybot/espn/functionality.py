from datetime import date


def find_team(league, identifier):
    """Find a team by abbreviation (exact) or name (substring), case-insensitive.
    Returns the team object if exactly one match, None otherwise."""
    identifier = identifier.strip()
    if not identifier:
        return None

    # Try exact abbreviation match first
    for team in league.teams:
        if team.team_abbrev.lower() == identifier.lower():
            return team

    # Fall back to substring name match
    matches = [t for t in league.teams if identifier.lower() in t.team_name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def get_scoreboard_short(league, week=None):
    """
    Retrieve the scoreboard for a given matchup period of the fantasy baseball season.
    Shows head-to-head scores (points leagues) or category records (category leagues).
    """
    if not week:
        week = league.currentMatchupPeriod

    box_scores = league.box_scores(matchup_period=week)
    score = []
    for i in box_scores:
        if i.away_team:
            if hasattr(i, 'home_wins'):
                # H2H Categories league
                score.append('%4s %d-%d-%d %s' % (
                    i.home_team.team_abbrev,
                    i.home_wins, i.home_losses, i.home_ties,
                    i.away_team.team_abbrev))
            else:
                # H2H Points league
                score.append('%4s %6.2f - %6.2f %s' % (
                    i.home_team.team_abbrev, i.home_score,
                    i.away_score, i.away_team.team_abbrev))
    text = ['Score Update (Week %d)' % week] + score
    return '\n'.join(text)


def get_scoreboard(league, week=None):
    """
    Retrieve a detailed scoreboard for H2H category leagues showing stat comparisons.
    Falls back to short scoreboard for points leagues.
    """
    if not week:
        week = league.currentMatchupPeriod

    box_scores = league.box_scores(matchup_period=week)

    # Check if this is a categories league
    if not box_scores or not hasattr(box_scores[0], 'home_stats'):
        return get_scoreboard_short(league, week=week)

    lines = ['Detailed Scoreboard (Week %d)' % week]
    for i in box_scores:
        if i.away_team and hasattr(i, 'home_stats'):
            lines.append('')
            lines.append('%s (%d-%d-%d) vs %s (%d-%d-%d)' % (
                i.home_team.team_name,
                i.home_wins, i.home_losses, i.home_ties,
                i.away_team.team_name,
                i.away_wins, i.away_losses, i.away_ties))
            # Show category-by-category breakdown
            for stat_name in sorted(i.home_stats.keys()):
                home_val = i.home_stats[stat_name]['value']
                away_val = i.away_stats[stat_name]['value']
                home_result = i.home_stats[stat_name]['result']
                if home_result == 'WIN':
                    marker = '<'
                elif home_result == 'LOSS':
                    marker = '>'
                else:
                    marker = '='
                if isinstance(home_val, float):
                    lines.append('  %6s: %8.3f %s %-8.3f' % (stat_name, home_val, marker, away_val))
                else:
                    lines.append('  %6s: %8s %s %-8s' % (stat_name, str(home_val), marker, str(away_val)))

    return '\n'.join(lines)


def get_standings(league, top_half_scoring=False, week=None):
    """
    Retrieve the current standings for the fantasy baseball league.
    """
    standings_txt = ''
    teams = league.teams
    standings = []
    if not top_half_scoring:
        standings = league.standings()
        standings_txt = [f"{pos + 1:2}: ({team.wins}-{team.losses}-{team.ties}) {team.team_name}"
                         for pos, team in enumerate(standings)]
    else:
        top_half_totals = {t.team_name: 0 for t in teams}
        if not week:
            week = league.currentMatchupPeriod
        for w in range(1, week):
            top_half_totals = top_half_wins(league, top_half_totals, w)

        for t in teams:
            wins = top_half_totals[t.team_name] + t.wins
            standings.append((wins, t.losses, t.ties, t.team_name))

        standings = sorted(standings, key=lambda tup: tup[0], reverse=True)
        standings_txt = [f"{pos + 1:2}: {team_name} ({wins}-{losses}-{ties}) (+{top_half_totals[team_name]})"
                         for pos, (wins, losses, ties, team_name) in enumerate(standings)]
    text = ["Current Standings"] + standings_txt

    return "\n".join(text)


def top_half_wins(league, top_half_totals, week):
    box_scores = league.box_scores(matchup_period=week)

    if hasattr(box_scores[0], 'home_wins'):
        # Categories: use category wins as score proxy
        scores = [(i.home_wins, i.home_team.team_name) for i in box_scores] + \
            [(i.away_wins, i.away_team.team_name) for i in box_scores if i.away_team]
    else:
        scores = [(i.home_score, i.home_team.team_name) for i in box_scores] + \
            [(i.away_score, i.away_team.team_name) for i in box_scores if i.away_team]

    scores = sorted(scores, key=lambda tup: tup[0], reverse=True)

    for i in range(0, len(scores) // 2):
        points, team_name = scores[i]
        top_half_totals[team_name] += 1

    return top_half_totals


def get_matchups(league, week=None):
    """
    Retrieve the matchups for a given matchup period in the fantasy baseball league.
    """
    if not week:
        week = league.currentMatchupPeriod

    matchups = league.box_scores(matchup_period=week)

    full_names = ['%s vs %s' % (i.home_team.team_name, i.away_team.team_name)
                  for i in matchups if i.away_team]

    abbrevs = ['%4s (%s-%s-%s) vs (%s-%s-%s) %s' % (
        i.home_team.team_abbrev, i.home_team.wins, i.home_team.losses, i.home_team.ties,
        i.away_team.wins, i.away_team.losses, i.away_team.ties, i.away_team.team_abbrev)
        for i in matchups if i.away_team]

    text = ['Matchups (Week %d)' % week] + full_names + [''] + abbrevs
    return '\n'.join(text)


def get_close_scores(league, week=None):
    """
    Retrieve close matchups for H2H categories (within 1 category win)
    or H2H points (within 20 points) leagues.
    """
    if not week:
        week = league.currentMatchupPeriod

    box_scores = league.box_scores(matchup_period=week)
    score = []

    for i in box_scores:
        if i.away_team:
            if hasattr(i, 'home_wins'):
                # Categories: close if margin is 1 category or tied
                diff = abs(i.home_wins - i.away_wins)
                if diff <= 1:
                    score.append('%4s %d-%d-%d %s' % (
                        i.home_team.team_abbrev,
                        i.home_wins, i.home_losses, i.home_ties,
                        i.away_team.team_abbrev))
            else:
                # Points: close if within 20 points
                diff = abs(i.home_score - i.away_score)
                if diff <= 20:
                    score.append('%4s %6.2f - %6.2f %s' % (
                        i.home_team.team_abbrev, i.home_score,
                        i.away_score, i.away_team.team_abbrev))

    if not score:
        return ''
    text = ['Close Matchups'] + score
    return '\n'.join(text)


def get_monitor(league):
    """
    Retrieve a list of players with injury concerns in starting lineups.
    """
    box_scores = league.box_scores()
    monitor = []
    text = ''
    for i in box_scores:
        if i.home_team:
            monitor += scan_roster(i.home_lineup, i.home_team)
        if i.away_team:
            monitor += scan_roster(i.away_lineup, i.away_team)

    if monitor:
        text = ['Starting Players to Monitor'] + monitor
    else:
        text = ['No Players to Monitor. Good Luck!']
    return '\n'.join(text)


def scan_roster(lineup, team):
    """
    Scan a lineup for players with injury statuses or IL-ineligible players in IL slots.
    """
    count = 0
    players = []
    for i in lineup:
        if i.slot_position not in ('BE', 'IL') and \
            i.injuryStatus not in ('ACTIVE', 'NORMAL', None) \
                and i.game_played == 0:
            count += 1
            player = i.position + ' ' + i.name + ' - ' + str(i.injuryStatus).title().replace('_', ' ')
            players += [player]

        if i.slot_position == 'IL' and \
            i.injuryStatus not in ('INJURY_RESERVE', 'OUT', 'SIXTY_DAY_DL',
                                   'FIFTEEN_DAY_DL', 'TEN_DAY_DL', 'SEVEN_DAY_DL',
                                   'BEREAVEMENT', 'PATERNITY', 'SUSPENSION'):
            count += 1
            player = i.position + ' ' + i.name + ' - Not IL eligible'
            players += [player]

    list_str = ""
    report = ""

    for p in players:
        list_str += p + "\n"

    if count > 0:
        s = '%s: \n%s \n' % (team.team_name, list_str[:-1])
        report = [s.lstrip()]

    return report


def get_waiver_report(league, faab=False, days=1):
    """
    Generate a waiver report listing transactions grouped by team.
    days=1 uses a rolling 24-hour window; days>=2 aligns to midnight.
    """
    from datetime import datetime, timezone as tz, timedelta
    from collections import defaultdict
    activities = league.recent_activity(50)
    now = datetime.now(tz.utc)
    if days == 1:
        cutoff = now.timestamp() - 86400
    else:
        cutoff = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)).timestamp()
    label = 'Last 24 hours' if days == 1 else f'Last {days} days'
    today = date.today().strftime('%Y-%m-%d')
    text = ''

    # team_name -> {'added': [...], 'dropped': [...]}
    by_team = defaultdict(lambda: {'added': [], 'dropped': []})
    added_types = ('WAIVER ADDED', 'FA ADDED')
    drop_types = ('DROPPED',)

    for activity in activities:
        if (activity.date / 1000) < cutoff:
            continue
        for team, action, player in activity.actions:
            if not isinstance(player, str) or not player:
                continue
            team_name = team.team_name
            if action in added_types:
                by_team[team_name]['added'].append(player)
            elif action in drop_types:
                by_team[team_name]['dropped'].append(player)

    if not by_team:
        return 'Waiver Report (%s): \nNo waiver transactions' % label

    report = []
    for team_name, moves in by_team.items():
        lines = [team_name]
        for p in moves['added']:
            lines.append(f'  ADDED   {p}')
        for p in moves['dropped']:
            lines.append(f'  DROPPED {p}')
        report.append('\n'.join(lines))

    return 'Waiver Report (%s): \n' % label + '\n\n'.join(report)


def get_weekly_score_with_win_loss(league, week=None):
    """
    Get scores with W/L for each team in a matchup period.
    Supports both points and categories leagues.
    """
    if not week:
        week = league.currentMatchupPeriod

    box_scores = league.box_scores(matchup_period=week)
    weekly_scores = {}
    for i in box_scores:
        if i.home_team != 0 and i.away_team != 0:
            if hasattr(i, 'home_wins'):
                # Categories league
                if i.home_wins > i.away_wins:
                    weekly_scores[i.home_team] = [i.home_wins, 'W']
                    weekly_scores[i.away_team] = [i.away_wins, 'L']
                elif i.home_wins < i.away_wins:
                    weekly_scores[i.home_team] = [i.home_wins, 'L']
                    weekly_scores[i.away_team] = [i.away_wins, 'W']
                else:
                    weekly_scores[i.home_team] = [i.home_wins, 'T']
                    weekly_scores[i.away_team] = [i.away_wins, 'T']
            else:
                # Points league
                if i.home_score > i.away_score:
                    weekly_scores[i.home_team] = [i.home_score, 'W']
                    weekly_scores[i.away_team] = [i.away_score, 'L']
                elif i.home_score < i.away_score:
                    weekly_scores[i.home_team] = [i.home_score, 'L']
                    weekly_scores[i.away_team] = [i.away_score, 'W']
                else:
                    weekly_scores[i.home_team] = [i.home_score, 'T']
                    weekly_scores[i.away_team] = [i.away_score, 'T']
    return dict(sorted(weekly_scores.items(), key=lambda item: item[1][0], reverse=True))


def get_lucky_trophy(league, week=None, recap=False):
    """
    Find the luckiest (lowest scoring winner) and unluckiest (highest scoring loser) teams.
    """
    if not week:
        week = league.currentMatchupPeriod - 1

    weekly_scores = get_weekly_score_with_win_loss(league, week=week)
    losses = 0
    unlucky_record = ''
    lucky_record = ''
    num_teams = len(weekly_scores) - 1

    unlucky_team = None
    lucky_team = None

    for t in weekly_scores:
        if weekly_scores[t][1] == 'L':
            unlucky_team = t
            unlucky_record = str(num_teams - losses) + '-' + str(losses)
            break
        losses += 1

    wins = 0
    weekly_scores = dict(sorted(weekly_scores.items(), key=lambda item: item[1][0]))
    for t in weekly_scores:
        if weekly_scores[t][1] == 'W':
            lucky_team = t
            lucky_record = str(wins) + '-' + str(num_teams - wins)
            break
        wins += 1

    if not lucky_team or not unlucky_team:
        if recap:
            return None, None, weekly_scores
        return ['No lucky/unlucky teams this period']

    if recap:
        return lucky_team.team_abbrev, unlucky_team.team_abbrev, weekly_scores

    lucky_str = ['Lucky'] + ['%s was %s against the league, but still got the win' % (lucky_team.team_name, lucky_record)]
    unlucky_str = ['Unlucky'] + ['%s was %s against the league, but still took an L' % (unlucky_team.team_name, unlucky_record)]
    return (lucky_str + unlucky_str)


def get_trophies(league, week=None, recap=False):
    """
    Returns trophies for the highest score, lowest score, closest win, and biggest blowout.
    Adapted for both H2H points and H2H categories baseball leagues.
    """
    if not week:
        week = league.currentMatchupPeriod - 1

    matchups = league.box_scores(matchup_period=week)

    is_categories = hasattr(matchups[0], 'home_wins') if matchups else False

    low_score = 99999999
    high_score = -1
    closest_score = 99999999
    biggest_blowout = -1

    high_team = None
    low_team = None
    close_winner = None
    close_loser = None
    ownerer = None
    blown_out = None

    for i in matchups:
        if is_categories:
            home_val = i.home_wins if i.home_team != 0 else 0
            away_val = i.away_wins if i.away_team != 0 else 0
        else:
            home_val = i.home_score if i.home_team != 0 else 0
            away_val = i.away_score if i.away_team != 0 else 0

        if i.home_team != 0:
            if home_val > high_score:
                high_score = home_val
                high_team = i.home_team
            if home_val < low_score:
                low_score = home_val
                low_team = i.home_team
        if i.away_team != 0:
            if away_val > high_score:
                high_score = away_val
                high_team = i.away_team
            if away_val < low_score:
                low_score = away_val
                low_team = i.away_team

        if i.away_team != 0 and i.home_team != 0:
            diff = abs(away_val - home_val)
            if diff != 0 and diff < closest_score:
                closest_score = diff
                if away_val > home_val:
                    close_winner = i.away_team
                    close_loser = i.home_team
                else:
                    close_winner = i.home_team
                    close_loser = i.away_team
            if diff > biggest_blowout:
                biggest_blowout = diff
                if away_val > home_val:
                    ownerer = i.away_team
                    blown_out = i.home_team
                else:
                    ownerer = i.home_team
                    blown_out = i.away_team

    if recap:
        h = high_team.team_abbrev if high_team else ''
        l = low_team.team_abbrev if low_team else ''
        b = blown_out.team_abbrev if blown_out else ''
        c = close_winner.team_abbrev if close_winner else ''
        return h, l, b, c

    score_label = "category wins" if is_categories else "points"

    lines = ['Trophies of the week:']

    if high_team:
        lines += ['High score: %s with %.2f %s' % (high_team.team_name, high_score, score_label)]
    if low_team:
        lines += ['Low score: %s with %.2f %s' % (low_team.team_name, low_score, score_label)]
    if ownerer and blown_out:
        lines += ['Blow out: %s blew out %s by %.2f %s' % (ownerer.team_name, blown_out.team_name, biggest_blowout, score_label)]
    if close_winner and close_loser:
        lines += ['Close win: %s barely beat %s by %.2f %s' % (close_winner.team_name, close_loser.team_name, closest_score, score_label)]

    lucky_result = get_lucky_trophy(league, week)
    if isinstance(lucky_result, list):
        lines += lucky_result

    return '\n'.join(lines)


def _compute_streaks(league):
    """Compute current win/loss/tie streaks for all teams.
    Returns dict: {team: {'type': 'W'/'L'/'T', 'count': int}}"""
    streaks = {t: {'type': None, 'count': 0} for t in league.teams}

    for week in range(1, league.currentMatchupPeriod):
        weekly = get_weekly_score_with_win_loss(league, week=week)
        for team, (score, result) in weekly.items():
            if streaks[team]['type'] == result:
                streaks[team]['count'] += 1
            else:
                streaks[team]['type'] = result
                streaks[team]['count'] = 1

    return streaks


def get_streaks(league):
    """Display current win/loss/tie streaks for all teams, sorted by length."""
    if league.currentMatchupPeriod <= 1:
        return 'No completed matchup periods yet.'

    streaks = _compute_streaks(league)
    sorted_teams = sorted(streaks.keys(),
                          key=lambda t: streaks[t]['count'], reverse=True)

    lines = ['Current Streaks']
    for team in sorted_teams:
        s = streaks[team]
        if s['type'] is None:
            continue
        streak_str = '%s%d' % (s['type'], s['count'])
        lines.append('%-20s %s' % (team.team_name[:20], streak_str))

    return '\n'.join(lines)


def get_streak_milestones(league):
    """Return notable streak milestones (5+ games). Empty string if none."""
    if league.currentMatchupPeriod <= 1:
        return ''

    streaks = _compute_streaks(league)
    notable = [(t, s) for t, s in streaks.items() if s['count'] >= 5]

    if not notable:
        return ''

    notable.sort(key=lambda x: x[1]['count'], reverse=True)
    lines = ['Streak Alert!']
    for team, s in notable:
        label = 'win' if s['type'] == 'W' else 'losing' if s['type'] == 'L' else 'tie'
        lines.append('%s is on a %d-game %s streak!' % (team.team_name, s['count'], label))

    return '\n'.join(lines)


def get_rivalry(league, team1_name, team2_name):
    """Head-to-head record between two teams across all matchup periods this season."""
    team1 = find_team(league, team1_name)
    team2 = find_team(league, team2_name)

    available = ', '.join(t.team_abbrev for t in league.teams)

    if not team1:
        return "Could not find team matching '%s'. Available: %s" % (team1_name, available)
    if not team2:
        return "Could not find team matching '%s'. Available: %s" % (team2_name, available)
    if team1 == team2:
        return "Please provide two different teams."

    t1_wins = 0
    t2_wins = 0
    ties = 0
    matchup_results = []

    for week in range(1, league.currentMatchupPeriod):
        box_scores = league.box_scores(matchup_period=week)
        for bs in box_scores:
            home = bs.home_team
            away = bs.away_team
            if not away or home == 0 or away == 0:
                continue

            if not ((home.team_id == team1.team_id and away.team_id == team2.team_id) or
                    (home.team_id == team2.team_id and away.team_id == team1.team_id)):
                continue

            is_categories = hasattr(bs, 'home_wins')
            if is_categories:
                t1_is_home = home.team_id == team1.team_id
                home_val = bs.home_wins
                away_val = bs.away_wins
            else:
                t1_is_home = home.team_id == team1.team_id
                home_val = bs.home_score
                away_val = bs.away_score

            t1_val = home_val if t1_is_home else away_val
            t2_val = away_val if t1_is_home else home_val

            if t1_val > t2_val:
                t1_wins += 1
                result = 'W'
            elif t1_val < t2_val:
                t2_wins += 1
                result = 'L'
            else:
                ties += 1
                result = 'T'

            if is_categories:
                detail = '%d-%d' % (int(t1_val), int(t2_val))
            else:
                detail = '%.2f - %.2f' % (t1_val, t2_val)
            matchup_results.append((week, detail, result))

    if not matchup_results:
        return '%s and %s have not faced each other yet this season.' % (
            team1.team_name, team2.team_name)

    lines = ['Rivalry: %s vs %s (%d)' % (team1.team_name, team2.team_name, league.year)]
    lines.append('%s leads %d-%d-%d' % (
        team1.team_name if t1_wins > t2_wins else
        team2.team_name if t2_wins > t1_wins else 'Tied',
        max(t1_wins, t2_wins), min(t1_wins, t2_wins), ties)
        if t1_wins != t2_wins else 'Tied %d-%d-%d' % (t1_wins, t2_wins, ties))
    lines.append('')
    for week, detail, result in matchup_results:
        lines.append('Week %2d: %s  (%s)' % (week, detail, result))

    return '\n'.join(lines)


def get_playoff_race(league):
    """Playoff race with magic numbers, clinch/elimination status, and upcoming matchups."""
    playoff_spots = league.settings.playoff_team_count
    reg_season = league.settings.reg_season_count
    completed_weeks = league.currentMatchupPeriod - 1

    if playoff_spots == 0:
        return 'This league does not have playoffs configured.'

    if completed_weeks >= reg_season:
        return 'The regular season is over. Playoffs have begun!'

    remaining_weeks = reg_season - completed_weeks

    # Sort teams by ESPN's playoff seed (standing)
    teams = sorted(league.teams, key=lambda t: t.standing)

    # Bubble team is the first team outside the playoff spots
    bubble_team = teams[playoff_spots] if len(teams) > playoff_spots else None
    # Cutline team is the last team in a playoff spot
    cutline_team = teams[playoff_spots - 1]

    lines = ['Playoff Race (%d spots, %d weeks remaining)' % (playoff_spots, remaining_weeks)]
    lines.append('')
    lines.append(' # %-20s Record  Status         Magic#' % 'Team')

    for pos, team in enumerate(teams, 1):
        record = '%d-%d-%d' % (team.wins, team.losses, team.ties)

        if pos <= playoff_spots:
            if bubble_team and team.wins - bubble_team.wins > remaining_weeks:
                status = 'CLINCHED'
                magic = '--'
            else:
                status = 'In the race'
                if bubble_team:
                    magic = str(remaining_weeks + 1 - (team.wins - bubble_team.wins))
                else:
                    magic = '--'
        else:
            max_wins = team.wins + remaining_weeks
            if max_wins < cutline_team.wins:
                status = 'ELIMINATED'
                magic = '--'
            else:
                status = 'In the race'
                magic = '--'

        lines.append('%2d %-20s %-7s %-14s %s' % (
            pos, team.team_name[:20], record, status, magic))

        if pos == playoff_spots:
            lines.append('   ---- playoff cutline ----')

    # Show next opponents
    lines.append('')
    lines.append('Upcoming matchups:')
    for team in teams:
        upcoming = []
        for week in range(league.currentMatchupPeriod,
                          min(league.currentMatchupPeriod + 3, reg_season + 1)):
            box_scores = league.box_scores(matchup_period=week)
            for bs in box_scores:
                if bs.home_team and bs.away_team:
                    if hasattr(bs.home_team, 'team_id') and bs.home_team.team_id == team.team_id:
                        upcoming.append(bs.away_team.team_abbrev)
                    elif hasattr(bs.away_team, 'team_id') and bs.away_team.team_id == team.team_id:
                        upcoming.append(bs.home_team.team_abbrev)
        lines.append('%-20s %s' % (team.team_name[:20], ', '.join(upcoming) if upcoming else 'None'))

    return '\n'.join(lines)


def get_playoff_alerts(league):
    """Return clinch/elimination alerts. Empty string if no team has clinched or been eliminated."""
    playoff_spots = league.settings.playoff_team_count
    reg_season = league.settings.reg_season_count
    completed_weeks = league.currentMatchupPeriod - 1

    if playoff_spots == 0 or completed_weeks >= reg_season:
        return ''

    remaining_weeks = reg_season - completed_weeks
    teams = sorted(league.teams, key=lambda t: t.standing)
    bubble_team = teams[playoff_spots] if len(teams) > playoff_spots else None
    cutline_team = teams[playoff_spots - 1]

    clinched = []
    eliminated = []

    for pos, team in enumerate(teams, 1):
        if pos <= playoff_spots:
            if bubble_team and team.wins - bubble_team.wins > remaining_weeks:
                clinched.append(team.team_name)
        else:
            max_wins = team.wins + remaining_weeks
            if max_wins < cutline_team.wins:
                eliminated.append(team.team_name)

    if not clinched and not eliminated:
        return ''

    lines = ['Playoff Alert!']
    for name in clinched:
        lines.append('%s has CLINCHED a playoff spot!' % name)
    for name in eliminated:
        lines.append('%s has been ELIMINATED from playoff contention.' % name)

    return '\n'.join(lines)
