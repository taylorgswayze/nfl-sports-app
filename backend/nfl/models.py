from django.db import models

class Team(models.Model):
    team_id = models.IntegerField(primary_key=True)
    team_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10, blank=True, null=True)
    record = models.CharField(max_length=20, blank=True, null=True)
    last_updated = models.DateTimeField(null=True)

    def __str__(self):
        return f'{self.short_name}'


class Calendar(models.Model):
    name = models.CharField(max_length=100, null=True)
    details = models.CharField(max_length=100, null=True)
    week_num = models.IntegerField(null=True)
    season = models.IntegerField(null=True)
    season_type_name = models.CharField(max_length=100, null=True)
    season_type_id = models.IntegerField(null=True)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)

    class Meta:
        unique_together = ['season', 'season_type_id', 'week_num']

    def __str__(self):
        return f'{self.name}: {self.details} during {self.season_type_name}'


class Game(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_IN = 'in'
    STATUS_FINAL = 'final'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_IN, 'In Progress'),
        (STATUS_FINAL, 'Final'),
    ]

    event_id = models.IntegerField(unique=True, primary_key=True)
    short_name = models.CharField(max_length=100, null=True)
    game_datetime = models.DateTimeField()
    season = models.IntegerField()
    week_num = models.IntegerField()
    season_type_id = models.IntegerField(default=2)  # 2=regular season, 3=postseason
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    week = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='games_for_week', null=True)
    home_score = models.IntegerField(null=True)
    away_score = models.IntegerField(null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)

    def __str__(self):
        return f'{self.home_team} vs {self.away_team}'


class Outcome(models.Model):
    event_id = models.OneToOneField(Game, on_delete=models.CASCADE, primary_key=True)
    spread_display = models.CharField(max_length=30, null=True)
    spread = models.IntegerField(null=True)
    home_win_prob = models.FloatField(null=True)
    away_win_prob = models.FloatField(null=True)
    pred_diff = models.FloatField(null=True)
    last_updated = models.DateTimeField(null=True)

    def __str__(self):
        return f'{self.spread_display}'


class Athlete(models.Model):
    athlete_id = models.IntegerField(unique=True, primary_key=True)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    display_name = models.CharField(max_length=100, null=True)  # Added for full name
    jersey = models.IntegerField(null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True)
    position_id = models.IntegerField(null=True)
    position = models.CharField(max_length=50, null=True)
    position_abbreviation = models.CharField(max_length=10, null=True)  # Added
    age = models.IntegerField(null=True)
    weight = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
    debut_year = models.IntegerField(null=True)
    active = models.CharField(max_length=50, null=True)
    status_id = models.IntegerField(null=True)
    status = models.CharField(max_length=50, null=True)
    injuries = models.CharField(max_length=50, null=True)
    # Depth chart standing from ESPN's seasonal depth chart: rank 1 within a
    # slot is the starter. Cleared when the player leaves the team, NULL for
    # deep reserves the chart does not list.
    depth_rank = models.IntegerField(null=True)
    depth_slot = models.IntegerField(null=True)
    last_updated = models.DateTimeField(null=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class SeasonStatistic(models.Model):
    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name='season_stats')
    season_year = models.IntegerField()
    season_type = models.CharField(max_length=20, default='Regular Season')
    category_name = models.CharField(max_length=50)  # passing, rushing, receiving, etc.
    stat_name = models.CharField(max_length=100)     # completions, passingYards, etc.
    stat_value = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    stat_display_value = models.CharField(max_length=50, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['athlete', 'season_year', 'season_type', 'category_name', 'stat_name']

    def __str__(self):
        return f'{self.athlete} - {self.season_year} {self.category_name}: {self.stat_name}'


class GameStatistic(models.Model):
    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name='game_stats')
    event_id = models.CharField(max_length=20)
    game_date = models.DateField(null=True)
    opponent = models.CharField(max_length=10, null=True)
    category_name = models.CharField(max_length=50)
    stat_name = models.CharField(max_length=100)
    stat_value = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    stat_display_value = models.CharField(max_length=50, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['athlete', 'event_id', 'category_name', 'stat_name']

    def __str__(self):
        return f'{self.athlete} - Game {self.event_id}: {self.stat_name}'


class StatTeam(models.Model):
    team_id = models.ForeignKey(Team, on_delete=models.CASCADE)
    season = models.IntegerField()
    category = models.CharField(max_length=50, null=True)
    stat_name = models.CharField(max_length=50, null=True)
    value = models.FloatField(null=True)
    rank = models.IntegerField(null=True)
    display_rank = models.CharField(max_length=10, null=True)
    description = models.CharField(max_length=200, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['team_id', 'season', 'category', 'stat_name'],
                name='unique_team_season_category_stat'
            )
        ]


class DeskUser(models.Model):
    """A signed-in Google account. Sessions reference this via
    request.session['desk_user_id']; Sleeper settings live here so they
    follow the user across devices."""
    google_sub = models.CharField(max_length=64, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, default='')
    picture = models.URLField(blank=True, default='')
    sleeper_username = models.CharField(max_length=100, blank=True, default='')
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.email}'


class FantasyInsight(models.Model):
    """One Week Room report per (Sleeper user, league): the engine payload
    (lineup, waivers, trades, matchup projection, prose) as printed at
    generated_at. Refreshed every 12 hours by the cron job and on demand;
    the row is replaced in place, never versioned."""
    sleeper_user_id = models.CharField(max_length=32, db_index=True)
    username = models.CharField(max_length=100)
    league_id = models.CharField(max_length=32)
    season = models.IntegerField()
    week = models.IntegerField()
    payload = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['sleeper_user_id', 'league_id']

    def __str__(self):
        return f'{self.username} / {self.league_id} wk {self.week}'
