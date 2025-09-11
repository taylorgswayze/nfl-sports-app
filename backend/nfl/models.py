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

    def __str__(self):
        return f'{self.name}: {self.details} during {self.season_type_name}'


class Game(models.Model):
    event_id = models.IntegerField(unique=True, primary_key=True)
    short_name = models.CharField(max_length=100, null=True)
    game_datetime = models.DateTimeField()
    season = models.IntegerField()
    week_num = models.IntegerField()
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    week = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='games_for_week', null=True)

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
    category = models.CharField(max_length=50, null=True)
    stat_name = models.CharField(max_length=50, null=True)
    value = models.FloatField(null=True)
    rank = models.IntegerField(null=True)
    display_rank = models.CharField(max_length=10, null=True)
    description = models.CharField(max_length=200, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['team_id', 'category', 'stat_name'],
                name='unique_team_category_stat'
            )
        ]
