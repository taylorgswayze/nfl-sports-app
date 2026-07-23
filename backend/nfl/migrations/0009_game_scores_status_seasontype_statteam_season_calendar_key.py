from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema prerequisites for scores + multi-season backfill.

    - Game gains home_score / away_score / status / season_type_id.
    - StatTeam gains a season column (existing rows are 2025 data) and the
      unique constraint is extended to include it.
    - Calendar rows become unique on (season, season_type_id, week_num) so
      the yearly rollover can no longer overwrite prior seasons in place.
    """

    dependencies = [
        ('nfl', '0008_athlete_display_name_athlete_position_abbreviation_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='home_score',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='game',
            name='away_score',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='game',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('in', 'In Progress'),
                    ('final', 'Final'),
                ],
                default='scheduled',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='game',
            name='season_type_id',
            field=models.IntegerField(default=2),
        ),
        migrations.AddField(
            model_name='statteam',
            name='season',
            field=models.IntegerField(default=2025),
            preserve_default=False,
        ),
        migrations.RemoveConstraint(
            model_name='statteam',
            name='unique_team_category_stat',
        ),
        migrations.AddConstraint(
            model_name='statteam',
            constraint=models.UniqueConstraint(
                fields=('team_id', 'season', 'category', 'stat_name'),
                name='unique_team_season_category_stat',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='calendar',
            unique_together={('season', 'season_type_id', 'week_num')},
        ),
    ]
