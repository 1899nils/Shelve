from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0012_traktaccount_oauth_simklaccount"),
    ]

    operations = [
        migrations.AddField(
            model_name="traktaccount",
            name="live_sync_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Whether to periodically pull data from Trakt to Shelve",
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="last_synced_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When the last successful sync from Trakt completed",
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="sync_status",
            field=models.CharField(
                choices=[("idle", "Idle"), ("syncing", "Syncing"), ("error", "Error")],
                default="idle",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="last_sync_error",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Last sync error message, if any",
                max_length=500,
            ),
        ),
    ]
