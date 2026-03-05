from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_headline_enable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True,
                null=True,
                default=None,
                unique=True,
                max_length=254,
                verbose_name="email address",
            ),
        ),
    ]
