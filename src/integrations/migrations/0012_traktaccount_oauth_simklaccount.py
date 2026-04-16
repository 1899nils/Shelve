import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0011_lastfmaccount_history_import_completed_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add OAuth fields to TraktAccount
        migrations.AddField(
            model_name="traktaccount",
            name="access_token",
            field=models.TextField(
                blank=True,
                help_text="Encrypted OAuth access token for rating sync",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="refresh_token",
            field=models.TextField(
                blank=True,
                help_text="Encrypted OAuth refresh token for rating sync",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="token_expires_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the access token expires",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="username",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="traktaccount",
            name="rating_sync_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Whether to push ratings from Shelve to Trakt",
            ),
        ),
        # Create SimklAccount
        migrations.CreateModel(
            name="SimklAccount",
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
                    "access_token",
                    models.TextField(
                        blank=True,
                        help_text="Encrypted SIMKL OAuth access token (does not expire)",
                        null=True,
                    ),
                ),
                ("username", models.CharField(blank=True, default="", max_length=255)),
                (
                    "rating_sync_enabled",
                    models.BooleanField(
                        default=False,
                        help_text="Whether to push ratings from Shelve to SIMKL",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simkl_account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "SIMKL account",
                "verbose_name_plural": "SIMKL accounts",
            },
        ),
    ]
