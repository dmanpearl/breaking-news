from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_userpreferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreferences",
            name="history_expand_all",
            field=models.BooleanField(
                default=False,
                help_text="Expand all history items by default.",
            ),
        ),
    ]
