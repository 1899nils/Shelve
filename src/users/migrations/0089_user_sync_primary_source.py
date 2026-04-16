from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0088_alter_user_anime_sort_alter_user_boardgame_sort_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="sync_primary_source",
            field=models.CharField(
                blank=True,
                choices=[("", "None"), ("trakt", "Trakt"), ("simkl", "SIMKL")],
                default="",
                help_text="Primary external service for importing data",
                max_length=20,
            ),
        ),
    ]
