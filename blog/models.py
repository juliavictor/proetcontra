#! /usr/bin/env python
# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from django import forms
from django.core.validators import MinValueValidator
from django.contrib import admin
from django.forms import TextInput, Textarea


STATUS_CHOICES = (
    (1, ("Язык и речь")),
    (2, ("Растения и животные")),
    (3, ("Культура и искусство")),
    (4, ("Химия и биология")),
    (5, ("Логика и восприятие")),
    (6, ("Земля и Вселенная")),
    (7, ("Человек и общество")),
    (8, ("Наука и технологии")),
    (9, ("История и археология")),
    (10, ("Медицина и здоровье"))
)

FA_CHOICES = (
    (0, ("Против")),
    (1, ("За")))


def split_text(full_name):
    split = full_name.split()
    text = ""
    for word in split[:7]:
        text += word + " "
    if len(split) > 7:
        text += "..."
    return text


# Field sizes
glob_field_rows = 4
glob_field_cols = 80


class Post(models.Model):
    author = models.ForeignKey('auth.User')
    title = models.CharField(max_length=200)
    img_source = models.TextField()
    text = models.TextField()
    tag = models.IntegerField(choices=STATUS_CHOICES, default=1)
    views = models.PositiveIntegerField(validators=[MinValueValidator(1)], default = 0)
    created_date = models.DateTimeField(
            default=timezone.now)
    published_date = models.DateTimeField(
            blank=True, null=True)
    image = models.ImageField(upload_to='img', default="default-image.png")
    def approved_comments(self):
        return self.comments.filter(approved_comment=True)


    def publish(self):
        self.published_date = timezone.now()
        self.save()

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey('blog.Post', related_name='comments')
    author = models.CharField(max_length=200)
    text = models.TextField()
    created_date = models.DateTimeField(default=timezone.now)
    approved_comment = models.BooleanField(default=False)

    def approve(self):
        self.approved_comment = True
        self.save()


    def __str__(self):
        return self.text


class Poll(models.Model):
    post = models.ForeignKey('blog.Post', related_name='polls')
    question = models.TextField()
    polarity = models.IntegerField(choices=FA_CHOICES, default=1)
    def __str__(self):
        return split_text(self.question)



class Quote(models.Model):
    post = models.ForeignKey('blog.Post', related_name='quotes')
    quote = models.TextField()
    author = models.TextField()
    def __str__(self):
        return split_text(self.quote)


class PollInline(admin.StackedInline):
    model = Poll
    extra = 1
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': glob_field_cols})},
        models.TextField: {'widget': Textarea(attrs={'cols': glob_field_cols,
                                                     'rows': glob_field_rows})},
    }

class QuoteInline(admin.StackedInline):
    model = Quote
    extra = 1
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': glob_field_cols})},
        models.TextField: {'widget': Textarea(attrs={'cols': glob_field_cols,
                                                     'rows': glob_field_rows})},
    }


class PostAdmin(admin.ModelAdmin):
    inlines = [
        PollInline,
        QuoteInline,
    ]

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': glob_field_cols})},
        models.TextField: {'widget': Textarea(attrs={'cols': glob_field_cols,
                                                     'rows': glob_field_rows})},
    }


