import sys
import os
sys.path.insert(1, os.path.abspath('.'))
import pytest
import gamedaybot.espn.functionality as espn


# --- Mock objects ---

class MockTeam:
    def __init__(self, team_id, abbrev, name, wins=0, losses=0, ties=0, standing=1):
        self.team_id = team_id
        self.team_abbrev = abbrev
        self.team_name = name
        self.wins = wins
        self.losses = losses
        self.ties = ties
        self.standing = standing
        self.schedule = []


class MockBoxScorePoints:
    """H2H Points box score."""
    def __init__(self, home_team, away_team, home_score, away_score):
        self.home_team = home_team
        self.away_team = away_team
        self.home_score = home_score
        self.away_score = away_score


class MockBoxScoreCategories:
    """H2H Categories box score."""
    def __init__(self, home_team, away_team, home_wins, away_wins,
                 home_losses=0, away_losses=0, home_ties=0, away_ties=0):
        self.home_team = home_team
        self.away_team = away_team
        self.home_wins = home_wins
        self.away_wins = away_wins
        self.home_losses = home_losses
        self.away_losses = away_losses
        self.home_ties = home_ties
        self.away_ties = away_ties


class MockSettings:
    def __init__(self, playoff_team_count=4, reg_season_count=20):
        self.playoff_team_count = playoff_team_count
        self.reg_season_count = reg_season_count


class MockLeague:
    def __init__(self, teams, box_scores_by_week, current_period, settings=None):
        self.teams = teams
        self._box_scores = box_scores_by_week
        self.currentMatchupPeriod = current_period
        self.settings = settings or MockSettings()
        self.year = 2026

    def box_scores(self, matchup_period=None):
        if matchup_period is None:
            matchup_period = self.currentMatchupPeriod
        return self._box_scores.get(matchup_period, [])


# --- Helpers to build leagues ---

def make_teams(count=6):
    names = [
        ('TM1', 'Team Alpha'), ('TM2', 'Team Beta'), ('TM3', 'Team Gamma'),
        ('TM4', 'Team Delta'), ('TM5', 'Team Epsilon'), ('TM6', 'Team Zeta'),
        ('TM7', 'Team Eta'), ('TM8', 'Team Theta'),
    ]
    return [MockTeam(i + 1, names[i][0], names[i][1], standing=i + 1)
            for i in range(count)]


# ===========================================================================
# Tests for find_team
# ===========================================================================

class TestFindTeam:
    def setup_method(self):
        self.teams = make_teams(4)
        self.league = MockLeague(self.teams, {}, 1)

    def test_find_by_exact_abbrev(self):
        assert espn.find_team(self.league, 'TM1') == self.teams[0]

    def test_find_by_abbrev_case_insensitive(self):
        assert espn.find_team(self.league, 'tm2') == self.teams[1]

    def test_find_by_name_substring(self):
        assert espn.find_team(self.league, 'Alpha') == self.teams[0]

    def test_find_by_name_case_insensitive(self):
        assert espn.find_team(self.league, 'gamma') == self.teams[2]

    def test_no_match_returns_none(self):
        assert espn.find_team(self.league, 'NonExistent') is None

    def test_empty_string_returns_none(self):
        assert espn.find_team(self.league, '') is None

    def test_ambiguous_name_returns_none(self):
        # 'Team' matches all teams
        assert espn.find_team(self.league, 'Team') is None

    def test_abbrev_takes_priority_over_name(self):
        # If abbrev matches exactly, use it even if name also matches
        result = espn.find_team(self.league, 'TM3')
        assert result == self.teams[2]


# ===========================================================================
# Tests for get_streaks / _compute_streaks
# ===========================================================================

class TestStreaks:
    def _make_league_with_results(self, weekly_results, num_teams=4):
        """Build a league from a list of weekly box score results.
        weekly_results: list of lists of (home_idx, away_idx, home_score, away_score)
        """
        teams = make_teams(num_teams)
        box_by_week = {}
        for week_idx, matchups in enumerate(weekly_results, 1):
            week_scores = []
            for home_idx, away_idx, home_score, away_score in matchups:
                week_scores.append(MockBoxScorePoints(
                    teams[home_idx], teams[away_idx], home_score, away_score))
            box_by_week[week_idx] = week_scores

        current_period = len(weekly_results) + 1
        return MockLeague(teams, box_by_week, current_period)

    def test_no_completed_weeks(self):
        league = MockLeague(make_teams(4), {}, 1)
        result = espn.get_streaks(league)
        assert 'No completed matchup periods' in result

    def test_single_week(self):
        league = self._make_league_with_results([
            [(0, 1, 100, 90), (2, 3, 80, 85)],
        ])
        result = espn.get_streaks(league)
        assert 'W1' in result
        assert 'L1' in result

    def test_win_streak(self):
        # Team 0 wins 3 straight
        league = self._make_league_with_results([
            [(0, 1, 100, 90), (2, 3, 80, 85)],
            [(0, 2, 110, 90), (1, 3, 80, 70)],
            [(0, 3, 105, 95), (1, 2, 60, 70)],
        ])
        streaks = espn._compute_streaks(league)
        teams = league.teams
        assert streaks[teams[0]]['type'] == 'W'
        assert streaks[teams[0]]['count'] == 3

    def test_streak_broken(self):
        # Team 0 wins, then loses
        league = self._make_league_with_results([
            [(0, 1, 100, 90), (2, 3, 80, 85)],
            [(0, 2, 50, 90), (1, 3, 80, 70)],
        ])
        streaks = espn._compute_streaks(league)
        teams = league.teams
        assert streaks[teams[0]]['type'] == 'L'
        assert streaks[teams[0]]['count'] == 1

    def test_categories_league_streaks(self):
        teams = make_teams(4)
        box_by_week = {
            1: [MockBoxScoreCategories(teams[0], teams[1], 7, 3),
                MockBoxScoreCategories(teams[2], teams[3], 5, 5)],
            2: [MockBoxScoreCategories(teams[0], teams[2], 8, 2),
                MockBoxScoreCategories(teams[1], teams[3], 6, 4)],
        }
        league = MockLeague(teams, box_by_week, 3)
        streaks = espn._compute_streaks(league)
        assert streaks[teams[0]]['type'] == 'W'
        assert streaks[teams[0]]['count'] == 2
        assert streaks[teams[2]]['type'] == 'L'  # T then L -> L1
        assert streaks[teams[2]]['count'] == 1

    def test_get_streaks_output_format(self):
        league = self._make_league_with_results([
            [(0, 1, 100, 90), (2, 3, 80, 85)],
        ])
        result = espn.get_streaks(league)
        assert 'Current Streaks' in result
        assert 'Team Alpha' in result


class TestStreakMilestones:
    def _make_winning_streak_league(self, streak_length):
        teams = make_teams(4)
        box_by_week = {}
        for week in range(1, streak_length + 1):
            box_by_week[week] = [
                MockBoxScorePoints(teams[0], teams[1], 100, 90),
                MockBoxScorePoints(teams[2], teams[3], 80, 85),
            ]
        return MockLeague(teams, box_by_week, streak_length + 1)

    def test_no_milestones_under_5(self):
        league = self._make_winning_streak_league(4)
        assert espn.get_streak_milestones(league) == ''

    def test_milestone_at_5(self):
        league = self._make_winning_streak_league(5)
        result = espn.get_streak_milestones(league)
        assert 'Streak Alert!' in result
        assert 'Team Alpha' in result
        assert '5-game win streak' in result

    def test_no_milestones_early_season(self):
        league = MockLeague(make_teams(4), {}, 1)
        assert espn.get_streak_milestones(league) == ''


# ===========================================================================
# Tests for get_rivalry
# ===========================================================================

class TestRivalry:
    def _make_rivalry_league(self):
        teams = make_teams(4)
        box_by_week = {
            1: [MockBoxScorePoints(teams[0], teams[1], 100, 90),
                MockBoxScorePoints(teams[2], teams[3], 80, 85)],
            2: [MockBoxScorePoints(teams[0], teams[2], 110, 95),
                MockBoxScorePoints(teams[1], teams[3], 70, 80)],
            3: [MockBoxScorePoints(teams[0], teams[1], 85, 95),
                MockBoxScorePoints(teams[2], teams[3], 90, 70)],
        }
        return MockLeague(teams, box_by_week, 4)

    def test_rivalry_normal(self):
        league = self._make_rivalry_league()
        result = espn.get_rivalry(league, 'TM1', 'TM2')
        assert 'Rivalry' in result
        assert 'Team Alpha' in result
        assert 'Team Beta' in result
        assert 'Week  1' in result
        assert 'Week  3' in result
        # TM1 won week 1, lost week 3 -> 1-1-0
        assert '1-1-0' in result

    def test_rivalry_no_matchups(self):
        league = self._make_rivalry_league()
        result = espn.get_rivalry(league, 'TM1', 'TM4')
        assert 'have not faced each other' in result

    def test_rivalry_invalid_team(self):
        league = self._make_rivalry_league()
        result = espn.get_rivalry(league, 'INVALID', 'TM2')
        assert 'Could not find team' in result
        assert 'Available' in result

    def test_rivalry_same_team(self):
        league = self._make_rivalry_league()
        result = espn.get_rivalry(league, 'TM1', 'TM1')
        assert 'two different teams' in result

    def test_rivalry_by_name(self):
        league = self._make_rivalry_league()
        result = espn.get_rivalry(league, 'Alpha', 'Beta')
        assert 'Rivalry' in result

    def test_rivalry_categories_league(self):
        teams = make_teams(4)
        box_by_week = {
            1: [MockBoxScoreCategories(teams[0], teams[1], 7, 3),
                MockBoxScoreCategories(teams[2], teams[3], 5, 5)],
        }
        league = MockLeague(teams, box_by_week, 2)
        result = espn.get_rivalry(league, 'TM1', 'TM2')
        assert '7-3' in result
        assert '1-0-0' in result


# ===========================================================================
# Tests for get_playoff_race / get_playoff_alerts
# ===========================================================================

class TestPlayoffRace:
    def _make_playoff_league(self, wins_list, remaining_weeks=5,
                             playoff_spots=2, reg_season=20):
        """Create a league with teams having the given win counts."""
        teams = make_teams(len(wins_list))
        total_games = reg_season - remaining_weeks
        for i, w in enumerate(wins_list):
            teams[i].wins = w
            teams[i].losses = total_games - w
            teams[i].standing = i + 1
        # Sort by standing (already sorted)
        settings = MockSettings(playoff_team_count=playoff_spots,
                                reg_season_count=reg_season)
        current_period = total_games + 1
        return MockLeague(teams, {}, current_period, settings)

    def test_no_playoffs_configured(self):
        league = self._make_playoff_league([5, 3, 2, 1],
                                           playoff_spots=0)
        result = espn.get_playoff_race(league)
        assert 'does not have playoffs configured' in result

    def test_regular_season_over(self):
        teams = make_teams(4)
        for i, w in enumerate([10, 8, 6, 4]):
            teams[i].wins = w
            teams[i].losses = 20 - w
            teams[i].standing = i + 1
        settings = MockSettings(playoff_team_count=2, reg_season_count=20)
        league = MockLeague(teams, {}, 21, settings)
        result = espn.get_playoff_race(league)
        assert 'regular season is over' in result

    def test_clinched(self):
        # Team 1 has 15 wins, bubble (team 3) has 5 wins, 5 weeks left
        # 15 - 5 = 10 > 5 remaining -> clinched
        league = self._make_playoff_league([15, 10, 5, 3],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_race(league)
        assert 'CLINCHED' in result

    def test_eliminated(self):
        # Team 4 has 1 win, cutline team (team 2) has 12 wins, 5 weeks left
        # max for team 4: 1 + 5 = 6 < 12 -> eliminated
        league = self._make_playoff_league([15, 12, 5, 1],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_race(league)
        assert 'ELIMINATED' in result

    def test_all_in_race(self):
        # Close standings, everyone still in it
        league = self._make_playoff_league([8, 7, 6, 5],
                                           remaining_weeks=10, playoff_spots=2)
        result = espn.get_playoff_race(league)
        assert 'CLINCHED' not in result
        assert 'ELIMINATED' not in result
        assert 'In the race' in result

    def test_playoff_cutline_shown(self):
        league = self._make_playoff_league([10, 8, 6, 4],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_race(league)
        assert 'playoff cutline' in result

    def test_magic_number(self):
        # Team 1: 10 wins, bubble: 5 wins, 5 remaining
        # magic = 5 + 1 - (10 - 5) = 1
        league = self._make_playoff_league([10, 8, 5, 3],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_race(league)
        lines = result.split('\n')
        # Find line with Team Alpha
        alpha_line = [l for l in lines if 'Team Alpha' in l][0]
        assert '1' in alpha_line  # magic number 1

    def test_shows_spots_and_remaining(self):
        league = self._make_playoff_league([10, 8, 6, 4],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_race(league)
        assert '2 spots' in result
        assert '5 weeks remaining' in result


class TestPlayoffAlerts:
    def _make_playoff_league(self, wins_list, remaining_weeks=5,
                             playoff_spots=2, reg_season=20):
        teams = make_teams(len(wins_list))
        total_games = reg_season - remaining_weeks
        for i, w in enumerate(wins_list):
            teams[i].wins = w
            teams[i].losses = total_games - w
            teams[i].standing = i + 1
        settings = MockSettings(playoff_team_count=playoff_spots,
                                reg_season_count=reg_season)
        current_period = total_games + 1
        return MockLeague(teams, {}, current_period, settings)

    def test_no_alerts_all_in_race(self):
        league = self._make_playoff_league([8, 7, 6, 5],
                                           remaining_weeks=10, playoff_spots=2)
        assert espn.get_playoff_alerts(league) == ''

    def test_clinch_alert(self):
        league = self._make_playoff_league([15, 10, 5, 3],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_alerts(league)
        assert 'CLINCHED' in result
        assert 'Team Alpha' in result

    def test_elimination_alert(self):
        league = self._make_playoff_league([15, 12, 5, 1],
                                           remaining_weeks=5, playoff_spots=2)
        result = espn.get_playoff_alerts(league)
        assert 'ELIMINATED' in result
        assert 'Team Delta' in result

    def test_no_alerts_when_season_over(self):
        teams = make_teams(4)
        for i, w in enumerate([10, 8, 6, 4]):
            teams[i].wins = w
            teams[i].losses = 20 - w
            teams[i].standing = i + 1
        settings = MockSettings(playoff_team_count=2, reg_season_count=20)
        league = MockLeague(teams, {}, 21, settings)
        assert espn.get_playoff_alerts(league) == ''
