# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-02-20 12:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_comment'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='image',
            field=models.ImageField(default='default-image.png', upload_to='media'),
        ),
    ]
