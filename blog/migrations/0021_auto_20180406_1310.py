# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-04-06 10:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0020_auto_20180311_1927'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='tag',
            field=models.IntegerField(choices=[(1, 'Язык и речь'), (2, 'Растения и животные'), (3, 'Культура и искусство'), (4, 'Химия и биология'), (6, 'Земля и Вселенная'), (7, 'Человек и общество'), (8, 'Наука и технологии'), (9, 'История и археология'), (10, 'Медицина и здоровье')], default=1),
        ),
    ]
