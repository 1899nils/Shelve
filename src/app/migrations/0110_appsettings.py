from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0109_reopen_completed_tv_with_new_seasons"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tmdb_api_key",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="TMDB API key (get one at https://www.themoviedb.org/settings/api)",
                        max_length=255,
                    ),
                ),
            ],
            options={
                "verbose_name": "App Settings",
                "verbose_name_plural": "App Settings",
            },
        ),
    ]
