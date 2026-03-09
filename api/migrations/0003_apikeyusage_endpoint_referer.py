from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_apikeyusage"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikeyusage",
            name="endpoint",
            field=models.CharField(
                max_length=200,
                blank=True,
                default="",
                help_text="Request path, e.g. /api/v1/stream",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="apikeyusage",
            name="referer",
            field=models.CharField(
                max_length=300,
                blank=True,
                default="",
                help_text="HTTP Referer header, indicates the calling origin.",
            ),
        ),
    ]
