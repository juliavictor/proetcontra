# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-03-02 09:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0016_auto_20180302_1106'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='tag',
            field=models.IntegerField(choices=[(1, 'Основной тег'), (2, 'Человек и общество'), (3, 'Язык и речь'), (4, 'История и археология'), (5, 'Leading candidate')], default=1),
        ),
    ]
