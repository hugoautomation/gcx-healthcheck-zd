# Generated by Django 5.1.2 on 2024-11-13 06:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("healthcheck", "0008_zendeskuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="zendeskuser",
            name="plan",
            field=models.CharField(blank=True, max_length=320, null=True),
        ),
    ]
