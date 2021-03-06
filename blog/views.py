from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .models import Post, Comment, Poll
from .forms import PostForm, CommentForm
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from el_pagination.decorators import page_template
from el_pagination import utils
from random import shuffle
import pandas as pd
import numpy as np
import sys
import random
from pathlib import Path
import sqlite3
import datetime
import vk_api
from .settings import vk_username, vk_password, home_path
from .topic_profile import *
import os
from django.template import RequestContext
import avinit
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Post, Quote, QuoteInline
from numpy.random import choice
import threading
import time
from background_task import background
import csv
from time import gmtime, strftime

def current_catalog():
    if os.getcwd() == home_path:
        return ""
    else:
        return "proetcontra/"


def connect_to_database():
    # print(os.getcwd())
    if os.getcwd() == home_path:
        con = sqlite3.connect('db.sqlite3', timeout=30)
    else:
        try:
            con = sqlite3.connect('proetcontra/db.sqlite3', timeout=30)

        except sqlite3.OperationalError:
            con = sqlite3.connect('db.sqlite3', timeout=30)
    return con

# Read-only connection to DB
def connect_to_database_ro():
    if os.getcwd() == home_path:
        con = sqlite3.connect('file:db.sqlite3?mode=ro', uri=True, timeout=30)
    else:
        try:
            con = sqlite3.connect('file:proetcontra/db.sqlite3?mode=ro', uri=True, timeout=30)

        except sqlite3.OperationalError:
            con = sqlite3.connect('file:db.sqlite3?mode=ro', uri=True, timeout=30)
    return con


# Disabled as of 17/11/19
def write_shown_posts_analytics(request, post_list):
    # Fix for none session_key
    if not request.session.session_key:
        request.session.save()

    user_key = get_user_key(request)

    # Connecting to database
    con = connect_to_database()
    cursor = con.cursor()

    post_ids = []
    for post in post_list:
        post_ids.append(post.pk)

    last_recommendation = pd.read_sql_query("select user_id, post_list, date from "
                   "shown_posts_analytics where user_id=\"" + str(user_key) + "\"", con)

    # If this recommendation is different from the last (catching BUG):
    if last_recommendation.empty:
        # Adding view to log
        t = (user_key, json.dumps(post_ids), datetime.datetime.now())
        cursor.execute('insert into shown_posts_analytics(user_id,post_list,date) '
                       'values (?,?,?)', t)
        con.commit()

    else:
        if json.dumps(post_ids) != last_recommendation.iloc[-1:]["post_list"].item():
            # Adding view to log
            t = (user_key, json.dumps(post_ids), datetime.datetime.now())
            cursor.execute('insert into shown_posts_analytics(user_id,post_list,date) '
                           'values (?,?,?)', t)
            con.commit()

    cursor.close()
    con.close()


    return 0


# Twice excluding in order to produce sliceable set
def random_value(posts, num=None):
    if len(posts) == 0:
        return []

    un_posts = Post.objects
    top_posts = Post.objects

    for post in posts:
        un_posts = un_posts.exclude(id=str(post.pk))

    for post in un_posts:
        top_posts = top_posts.exclude(id=str(post.pk))

    if num:
        return top_posts.filter(published_date__lte=timezone.now()).order_by('?')[:num]

    return top_posts.filter(published_date__lte=timezone.now()).order_by('?')[:1]


def read_file(name):
    filepath = Path(name)
    if filepath.exists():
        file = pd.read_csv(name)
    else:
        file = pd.read_csv('/home/juliavictor/my-first-blog/'+name)
    return file


def write_file(df, name):
    filepath = Path(name)
    if filepath.exists():
        file = df.to_csv(name, encoding='utf-8', index=False)
    else:
        file = df.to_csv('/home/juliavictor/my-first-blog/'+name,
                    encoding='utf-8', index=False)


@page_template('blog/post_list_page.html')
def post_list(request, template='blog/post_list.html', extra_context=None):

    start = time.time()
    time_array = []

    time_array.append(strftime("%Y-%m-%d %H:%M:%S", gmtime()))

    time_array.append(round(time.time() - start, 2))


    # Remove session key on 1 page after reload
    if not request.is_ajax() and request.session.get("post_list"):
        # If current user has loaded the main page at least once
        if request.session.get("page_num"):
            page = request.session['page_num'] - 1
            last_shown_posts = request.session['post_list'][0:page*12+12]
            decrease_shown_posts_rec(request, last_shown_posts)

        del request.session['post_list']

    time_array.append(round(time.time() - start, 2))

    # Add session key for pagination without reloading new content
    if not request.session.get("post_list"):
        # Recommender system 1: content-based
        if not logged_with_vk(request) or not open_vk_profile(request):
            # print("not logged with vk: form_feed_content_recs")
            # request.session['post_list'] = form_feed_content_recs(request)
            request.session['post_list'] = form_content_recs_analog(request)
        # Recommender system 2: topic-profile-based
        else:
            # print("logged with vk: topic_profile_recommendations")

            user_vector = user_topic_profile(request)

            # Forming rating of best recommended post for current user
            request.session['post_list'] = topic_profile_recommendations(request, user_vector)

        time_array.append(round(time.time() - start, 2))
        # Подгрузка сведений об опросах поста
        # Connecting to database
        con = connect_to_database_ro()
        cursor = con.cursor()

        # Check if current user voted in current poll
        user_key = get_user_key(request)
        user_polls = pd.read_sql_query("SELECT * FROM blog_poll_values "
                                        "where user_id=\"" + str(user_key) + "\"", con)

        cursor.close()
        con.close()

        time_array.append(round(time.time() - start, 2))


        # for post in request.session['post_list']:
        #     poll_id_array = []

        #     for quote in post.quotes.all():
        #         for poll in quote.polls.all():
        #             poll_id_array.append(poll.id)

        #     user_poll_num = user_polls.loc[user_polls.post_id == post.pk]['blog_poll_id'].tolist()

        #     setattr(post, 'total_polls', len(poll_id_array))
        #     setattr(post, 'user_polls', len(set(user_poll_num) & set(poll_id_array)))


        time_array.append(round(time.time() - start, 2))


    # Get objects of posts from session
    posts = request.session.get('post_list')


    # Form a list of recommended posts
    context = {
        'entry_list': posts,
    }

    if extra_context is not None:
        context.update(extra_context)


    # Remove session on last page
    page = utils.get_page_number_from_request(request)
    request.session['page_num'] = page

    # Writing to database shown posts for user
    if request.session.get("page_num"):
        page = request.session['page_num'] - 1
        # write_shown_posts_analytics(request, request.session['post_list'])

    time_array.append(round(time.time() - start, 2))


    with open("out.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(time_array)

    return render(request, template, context)


def decrease_shown_posts_rec(request, posts):
    user_key = get_user_key(request)

    # Updating values for shown posts
    con = connect_to_database()
    cursor = con.cursor()

    for post in posts:
        # decrease tag values of shown posts by 0.1
        cursor.execute("update blog_post_categories set value = value - 0.1"
                       " where category = " + str(post.tag) +
                       " and user_id=\"" + str(user_key) + "\"")

        # decrease values of shown posts by 0.1
        cursor.execute("update blog_post_recs set value = value - 0.1"
                       " where post_id = " + str(post.pk) +
                       " and user_id=\"" + str(user_key) + "\"")

        # for TopicProfile-RS
        if logged_with_vk(request):
            user_id = request.user.social_auth.values_list("uid")[0][0]
            cursor.execute("update topic_profile_user_post set weight = weight - 0.4"
                           " where post_id = " + str(post.pk) +
                           " and user_id=\"" + str(user_id) + "\"")

    con.commit()
    cursor.close()
    con.close()

    return 0


# Forms list of recommended posts for user
def topic_profile_recommendations(request, user_vector):
    user_id = request.user.social_auth.values_list("uid")[0][0]

    # Collecting post weights from database
    con = connect_to_database_ro()
    posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('-views')
    post_weights = pd.read_sql_query("select user_id, post_id, weight from "
                   "topic_profile_user_post where user_id=\"" + str(user_id) + "\"", con)

    con.close()


    con = connect_to_database()
    cursor = con.cursor()
    # Updating new posts OR creating rows for new user
    for post in posts:
        if post.pk not in post_weights["post_id"].tolist():
            t = (user_id, post.pk, 10)
            cursor.execute('insert into topic_profile_user_post(user_id,post_id,weight)'
                           ' values (?,?,?)', t)
    con.commit()
    con.close()

    con = connect_to_database_ro()
    # Loading updated database (once again)
    post_weights = pd.read_sql_query("select user_id, post_id, weight from "
                                     "topic_profile_user_post where user_id=\"" + str(user_id) + "\"", con)

    con.close()

    # At this point post_weights MUST be - not post_weights.empty -
    posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('-views')

    user_post_recs = []
    # for the rest of the feed
    feed_posts = []
    feed_probab = []

    for post in posts:
        post_vector = json.loads(post.topic_profile)

        # comparing user & post vector
        cosine_distance = compare_vectors(user_vector, post_vector)
        weight = post_weights.loc[post_weights.post_id == post.pk, 'weight'].values[0]

        # getting rid of negative values, inelegantly
        weight = weight + 10000000000000

        if weight < 0:
            weight = 0.01

        # forming final rating of posts
        user_rec = {'post': post, 'value': cosine_distance * weight}

        feed_posts.append(post)
        feed_probab.append(cosine_distance * weight)

        user_post_recs.append(user_rec)

    # Sorting posts
    sorted_recs = sorted(user_post_recs, key=lambda k: k['value'], reverse=True)

    # Forming final list of 9 posts for main page
    # 3 random from TOP:1-5, 3 random from TOP:6-10, 3 random from TOP:11-20
    merged_list = random.sample(sorted_recs[0:4], 3) + \
                  random.sample(sorted_recs[5:9], 3) + \
                  random.sample(sorted_recs[10:19], 3)

    post_recommends = []

    for element in merged_list:
        post_recommends.append(element['post'])

    # print(post_recommends)

    # The rest of the feed with some probability
    feed = choice(feed_posts, 1000, p=normalize_vector_full(feed_probab))

    # Excluding duplicates
    feed = list(set(feed))

    # Excluding top 9 posts form the feed
    rest_of_feed = [x for x in feed if x not in post_recommends]

    return post_recommends + rest_of_feed


# Checks whether or not current user
# is logged in using any social network
def logged_with_vk(request):
    if request.user.is_authenticated():
        return request.user.social_auth.exists()
    else:
        return False


# Checks whether or not current user' VK profile is clodes
def open_vk_profile(request):
    if not logged_with_vk(request):
        return False

    user_id = request.user.social_auth.values_list("uid")[0][0]

    # Check if current user' topic profile is in database
    con = connect_to_database_ro()

    user_value = pd.read_sql_query("select uid, topic_profile, date, rs "
                                   "from vk_topic_profiles "
                                   "where uid=\"" + str(user_id) + "\"", con)
    con.close()

    # If vector for current user exists, fetch it from the database
    if not user_value.empty:
        if user_value['rs'][0] == 1:
            return True
        else:
            return False

    else:
        # Connecting to VK Api
        vk_session = vk_api.VkApi(vk_username, vk_password)
        vk_session.auth()

        vk = vk_session.get_api()

        try:
            # Получаем список групп пользователя вместе с количеством участников
            group_list = vk.groups.get(user_id=user_id, extended=1, fields='members_count')

        except vk_api.exceptions.ApiError:
            t = (user_id, json.dumps([0]), datetime.datetime.now(), 0)
            con = connect_to_database_ro()
            cursor = con.cursor()
            cursor.execute('insert into vk_topic_profiles(uid,topic_profile,date, rs) values (?,?,?,?)', t)
            con.commit()
            con.close()
            return False

    return True


# Builds topic profile for VK user
def user_topic_profile(request):
    if not logged_with_vk(request):
        return 0

    user_id = request.user.social_auth.values_list("uid")[0][0]

    # Check if current user' topic profile is in database
    con = connect_to_database_ro()

    user_value = pd.read_sql_query("select uid, topic_profile, date, rs "
                                   "from vk_topic_profiles "
                                   "where uid=\"" + str(user_id) + "\"", con)

    con.close()

    # If vector for current user exists, fetch it from the database
    if not user_value.empty:
        # rs = 1 means we use TopicProfile-RS, rs = 0 means we use content-RS
        # print(user_value['rs'][0])
        vector = json.loads(user_value['topic_profile'][0])

    else:
        # building topic profile by shortened group list
        vector = load_user_vk_vector.now(user_id, 2)

        # Write new vector to database
        t = (user_id, json.dumps(vector), datetime.datetime.now(), 1)

        con = connect_to_database()
        cursor = con.cursor()
        cursor.execute('insert into vk_topic_profiles(uid,topic_profile,date, rs) values (?,?,?,?)', t)
        con.commit()
        con.close()

        # # # and starting async function
        # download_thread = threading.Thread(target=load_user_vk_vector, args=[user_id])
        # download_thread.start()
        load_user_vk_vector(user_id)


    return vector


@background(schedule=2)
def load_user_vk_vector(user_id, group_limit=None):
    print("load_user_vk_vector start: user " + str(user_id))

    # Connecting to VK Api
    vk_session = vk_api.VkApi(vk_username, vk_password)
    vk_session.auth()

    vk = vk_session.get_api()

    # Получаем словарь из файла
    try:
        with open(current_catalog() + "dict.json", "r") as read_file:
            dictionary = json.load(read_file)

    except FileNotFoundError:
        with open("dict.json", "r") as read_file:
            dictionary = json.load(read_file)


    print("load_user_vk_vector: check point 1")

    # Получаем список групп пользователя вместе с количеством участников
    group_list = vk.groups.get(user_id=user_id, extended=1, fields='members_count')

    feed = ""

    print("load_user_vk_vector: check point 2")

    # # Ограничение на количество групп
    # if group_limit is None:
    #     group_array = group_list['items']
    # else:
    #     group_array = group_list['items'][0:group_limit]

    i = 0

    # Для каждой группы в цикле проверяем количество участников
    # Если удовлетворяет условию, то добавляем в общий документ по 100 постов со стены
    for group in group_list['items']:
        try:
            members = group['members_count']
        except KeyError:
            continue

        if 50 <= members <= 1000000 and group['id'] not in VK_GROUP_ID_EXCEPTIONS:
            print("load_user_vk_vector: group download: " + str(group['id']) + "...")
            download = get_group_wall(vk, group['id'])
            feed += download
            if len(download) > 0:
                i += 1

        if i == group_limit:
            break

    # Строим тематический профиль
    vector = form_doc_vector(normalize_doc(feed), dictionary, True)

    print("load_user_vk_vector: check point 3")

    # Нормализуем его
    vector = normalize_vector(vector)
    # print(vector)

    if group_limit is None:
        # Write new vector to database
        con = connect_to_database()
        cursor = con.cursor()

        cursor.execute("update vk_topic_profiles set topic_profile = \""
                       + json.dumps(vector) + "\" where uid=" + str(user_id))

        con.commit()
        cursor.close()
        con.close()

    # # Выводим рейтинг наиболее популярных категорий
    # for line in form_topic_rating(vector, dictionary)[:10]:
    #     print(line[0] + ": " + str(np.round(line[1],5)))

    print("load_user_vk_vector: user " + str(user_id) + " end, at array len:" + str(i))
    return vector


# Downloads the wall of VK group
def get_group_wall(vk, name):
    name = '-' + str(name)
    news_feed = ""

    try:
        feed = vk.wall.get(owner_id=name, count=100)

    except vk_api.exceptions.ApiError:
        # print("Пропускаем группу т.к. стена закрыта...")
        return news_feed

    for post in feed['items']:
        news_feed += post['text'] + "\n"

    return news_feed


def get_user_key(request):
    if request.user.is_authenticated():
        user_key = request.user.id
    else:
        user_key = request.session.session_key
    return str(user_key)


# Not used anymore. Look for form_content_recs_analog
def form_feed_content_recs(request):
    post_list = form_nine_content_recs(request, [])
    new_list = post_list

    # while len(new_list) > 0:
    while len(post_list) < 50:
        new_list = form_nine_content_recs(request, post_list)
        post_list += new_list
        # print(len(new_list))

    return post_list


def form_content_recs_analog(request):
    # start_time = time.time()

    if not request.session.session_key:
        request.session.save()

    user_key = get_user_key(request)

    posts = []
    arrays = []

    # Connecting to database
    con = connect_to_database_ro()

    user_posts = pd.read_sql_query("select user_id, post_id from "
                                  "blog_post_recs where "
                                   "user_id=\"" + str(user_key) + "\"", con)

    con.close()

    all_posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('-views')

    con = connect_to_database()
    cursor = con.cursor()

    # If this user never appeared before
    if user_posts.empty:

        for post in all_posts:
            t = (user_key, post.pk, post.tag, 10)
            cursor.execute('insert into blog_post_recs(user_id,post_id,category,value)'
                           ' values (?,?,?,?)', t)
        con.commit()
    else:
        # updating new posts
        for post in all_posts:
            if post.pk not in user_posts["post_id"].tolist():
                t = (user_key, post.pk, post.tag, 10)
                cursor.execute('insert into blog_post_recs(user_id,post_id,category,value)'
                               ' values (?,?,?,?)', t)
        con.commit()

    user_cats = pd.read_sql_query("select user_id, category, value from "
                                  "blog_post_categories where "
                                  "user_id=\"" + str(user_key) + "\"", con)

    cursor.close()
    con.close()

    if user_cats.empty:
        con = connect_to_database()
        cursor = con.cursor()
        # if user is new, fill all categories with 10
        for i in range(1, 11):
            t = (user_key, i, 10)
            cursor.execute('insert into blog_post_categories(user_id,category,value)'
                           ' values (?,?,?)', t)
        con.commit()
        cursor.close()
        con.close()

        # show 7 most popular posts
        pop_post = Post.objects
        arrays.append([y for y in pop_post.filter(published_date__lte=timezone.now()).order_by('-views')[:42]])

    else:
        # sorting categories list by descending order
        user_cats = user_cats.sort_values('value', ascending=False)

        # selecting top 7 categories for this user
        cat_list = user_cats['category'][:7].tolist()
        cat_list = list(set(cat_list))
        shuffle(cat_list)

        con = connect_to_database_ro()

        user_cat_list = pd.read_sql_query("select post_id, value, category from"
                           " blog_post_recs where user_id=\"" + str(user_key) +
                           "\" order by value desc", con)

        con.close()

        for category in cat_list:
            curr_cat = user_cat_list.loc[user_cat_list['category'] == category]
            post_ids = []

            for index, row in curr_cat.head(7).iterrows():
                post_ids.append(row[0])

            arrays.append([y for y in Post.objects.filter(id__in=post_ids).order_by('?')])



    # 5 популярных постов
    pop_posts = Post.objects
    for array in arrays:
        for post in array:
            pop_posts = pop_posts.exclude(id=str(post.pk))
    pop_posts = pop_posts.filter(published_date__lte=timezone.now()).order_by('-views')[:7]

    arrays.append([y for y in random_value(pop_posts,5)])

    # 5 новых постов
    new_posts = Post.objects
    for array in arrays:
        for post in array:
            new_posts = new_posts.exclude(id=str(post.pk))
    new_posts = new_posts.filter(published_date__lte=timezone.now()).order_by('-published_date')[:7]

    arrays.append([z for z in random_value(new_posts,5)])

    # Последовательно соединяем элементы массивов в общий список рекомендованных постов
    len_sum = 0
    for array in arrays:
        len_sum += len(array)

    while len_sum > 0:
        len_sum = 0

        for array in arrays:
            if array:
                posts.append(array.pop(0))
            len_sum += len(array)

    # print("Analog  --- %s seconds ---" % (time.time() - start_time))

    return posts


# Not used anymore. Look for form_content_recs_analog
def form_nine_content_recs(request, post_list):
    posts = form_recommendations(request, post_list)

    # 1 most popular post
    pop_post = Post.objects
    for post in posts:
        pop_post = pop_post.exclude(id=str(post.pk))
    for post in post_list:
        pop_post = pop_post.exclude(id=str(post.pk))
    pop_post = pop_post.filter(published_date__lte=timezone.now()).order_by('-views')[:7]

    posts = [x for x in posts] + \
            [y for y in random_value(pop_post)]

    # 1 newest post
    new_post = Post.objects
    for post in posts:
        new_post = new_post.exclude(id=str(post.pk))
    for post in post_list:
        new_post = new_post.exclude(id=str(post.pk))
    new_post = new_post.filter(published_date__lte=timezone.now()).order_by('-published_date')[:7]
    posts = [x for x in posts] + \
            [z for z in random_value(new_post)]

    return posts


# Not used anymore. Look for form_content_recs_analog
def form_recommendations(request, post_list):
    # form list of 7 categories
    post_list_ids = []
    for post in post_list:
        post_list_ids.append(post.pk)

    if not request.session.session_key:
        request.session.save()

    user_key = get_user_key(request)

    # Connecting to database
    con = connect_to_database()
    cursor = con.cursor()

    user_posts = pd.read_sql_query("select user_id, post_id from "
                                  "blog_post_recs where "
                                   "user_id=\"" + str(user_key) + "\"", con)

    posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('-views')

    # If this user never appeared before
    if user_posts.empty:
        for post in posts:
            t = (user_key, post.pk, post.tag, 10)
            cursor.execute('insert into blog_post_recs(user_id,post_id,category,value)'
                           ' values (?,?,?,?)', t)
        con.commit()
    else:
        # updating new posts
        for post in posts:
            if post.pk not in user_posts["post_id"].tolist():
                t = (user_key, post.pk, post.tag, 10)
                cursor.execute('insert into blog_post_recs(user_id,post_id,category,value)'
                               ' values (?,?,?,?)', t)
        con.commit()

    user_cats = pd.read_sql_query("select user_id, category, value from "
                                  "blog_post_categories where "
                                   "user_id=\"" + str(user_key) + "\"", con)

    if user_cats.empty:
        # if user is new, fill all categories with 10
        for i in range(1, 11):
           t = (user_key, i, 10)
           cursor.execute('insert into blog_post_categories(user_id,category,value)'
                          ' values (?,?,?)', t)
        con.commit()

        # show 7 most popular posts
        pop_post = Post.objects
        for post in post_list:
            pop_post = pop_post.exclude(id=str(post.pk))
        posts = pop_post.filter(published_date__lte=timezone.now()).order_by('-views')[:7]


    else:
        # sorting categories list by descending order
        user_cats = user_cats.sort_values('value', ascending=False)

        # selecting top 7 categories for this user
        cat_list = user_cats['category'][:7].tolist()
        cat_list = list(set(cat_list))
        shuffle(cat_list)

        posts = []

        for category in cat_list:
            # selecting 1 best post from each category
            cursor.execute("select post_id, value from blog_post_recs "
                           "where category=" + str(category) +
                           " and user_id=\"" + str(user_key) +
                           "\" order by value desc")
            post_ids = cursor.fetchall()
            post_id = -1

            for id in post_ids:
                if id[0] not in post_list_ids:
                    post_id = id[0]
                    break

            if post_id == -1:
                continue

            # print("Best post from category: "+str(category))
            # print(post_id)

            posts = [x for x in posts] + [y for y in Post.objects.filter(pk=post_id).order_by('?')[:1]]

    con.commit()
    cursor.close()
    con.close()

    return posts


def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)

    # Fix for none session_key
    if not request.session.session_key:
        request.session.save()

    user_key = get_user_key(request)

    # Adding view to log
    t = (user_key, pk, datetime.datetime.now())

    # Connecting to database
    con = connect_to_database()
    cursor = con.cursor()

    cursor.execute('insert into blog_post_views(user_id,post_id,date) values (?,?,?)', t)

    con.commit()
    cursor.close()
    con.close()

    # Polls: submitting on POST
    if request.method == "POST":
        for key in request.POST:
            if 'likert' in key:
                answer = request.POST[key]
                poll_number = key.split('-')[1]
                submit_poll(request, pk, answer, poll_number)

    js_results = {}
    # cur_user = []
    poll_value = 0
    # !! const_value for graph visualisation
    const = 1

    con = connect_to_database_ro()

    for quote in post.quotes.all():
        for poll in quote.polls.all():
            # Check if current user voted in current poll
            poll_status = pd.read_sql_query("SELECT * FROM blog_poll_values "
                                           "where post_id=" + pk +
                                           " and blog_poll_id=" + str(poll.id) +
                                           " and user_id=\"" + str(user_key) + "\"", con)

            # If user voted at least once
            if not poll_status.empty:
                array = [0, 0, 0, 0, 0]

                post_values = pd.read_sql_query("select value, count(value) from (select user_id, "
                      "blog_poll_id, value, max(date) as date from blog_poll_values where "
                      "blog_poll_id="+str(poll.id)+" group by user_id) group by value", con)

                values = post_values['value'].tolist()
                counts = post_values['count(value)'].tolist()

                for value, count in zip(values, counts):
                    for element in range(0, 5):
                        if value == element + 1:
                            array[element] = count

                # Adding constant to every value
                array = [x + const for x in array]

                # Counting percentages
                sum_array = sum(array)
                if sum_array != 0:
                    for element in range(0, 5):
                        array[element] = int(round(array[element]*100/sum_array))

                # Completing the final array
                array = list(reversed(array))
                array.append(poll.id)
                array.append(poll.question)
                js_results[poll.id] = array

            else:
                # print("Never voted")
                # We will not show results
                js_results[poll.id] = None

    # Unique views counter setting
    cursor = con.cursor()
    cursor.execute("select user_id, post_id, max(date) as date from blog_post_views "
                   "where post_id=" + pk + " group by user_id")
    post.views = len(cursor.fetchall())
    cursor.close()
    con.close()

    con = connect_to_database()
    cursor = con.cursor()

    # Increasing value by 0.8
    cursor.execute("update blog_post_categories set value = value + 0.8"
                       " where category = " + str(post.tag) +
                       " and user_id=\"" + str(user_key) + "\"")

    # Decrease values of shown post by 1
    cursor.execute("update blog_post_recs set value = value - 1"
                   " where post_id = " + str(post.pk) +
                   " and user_id=\"" + str(user_key) + "\"")

    # for TopicProfile-RS
    if logged_with_vk(request):
        user_id = request.user.social_auth.values_list("uid")[0][0]
        cursor.execute("update topic_profile_user_post set weight = weight - 2"
                       " where post_id = " + str(post.pk) +
                       " and user_id=\"" + str(user_id) + "\"")

    con.commit()
    cursor.close()
    con.close()

    post.save()

    # For black & white filter
    request.session[pk] = 1

    posts = Post.objects
    posts = posts.exclude(id=str(post.pk))
    posts = posts.filter(tag=post.tag).order_by('?')[:3]

    # write_shown_posts_analytics(request, posts)

    # polls = random.shuffle([i for i in post.polls.all()])

    # print(js_results)

    # Comments section
    if request.method == "POST":
        if 'post-comment' in request.POST:
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.author = request.user
                comment.post = post
                comment.save()
                return redirect('post_detail', pk=post.pk)
        else:
            form = CommentForm()
    else:
        form = CommentForm()

    if request.user.is_authenticated:
        svg_tag = svg_avatar(form_username(request.user))
    else:
        svg_tag = ""

    post_comments = []

    for comment in post.comments.all():
        line = {}
        line["author"] = form_username(comment.author)
        line["created_date"] = comment.created_date
        line["text"] = comment.text
        svg = svg_avatar(line["author"])
        line["svg"] = svg
        post_comments.append(line)

    return render(request, 'blog/post_detail.html',
                  {'post': post, 'posts': posts, 'js_results': js_results,
                   'form': form, 'svg_tag': svg_tag,
                   'post_comments': post_comments, 'request': request})


def svg_avatar(username):
    svg_tag = avinit.get_svg_avatar(username)
    svg_tag = svg_tag.replace("200px", "50px")\
        .replace("80px","24px").replace("200","50")
    return svg_tag


def form_username(user):
    # User name
    fn = user.first_name
    ln = user.last_name
    if len(ln) > 0:
        user_name = fn + ' ' + ln
    else:
        if len(fn) > 0:
            user_name = fn
        else:
            user_name = str(user)
    return user_name


def submit_poll(request, pk, answer, poll_id):
    """ Submiting poll with given answer. Returns json for AJAX. """
    if request.method == 'POST':
        js_results = {}
        if not request.session.session_key:
            request.session.save()

        user_key = get_user_key(request)
        post = get_object_or_404(Post, pk=pk)

        # Connecting to database
        con = connect_to_database()
        cursor = con.cursor()

        # Adding new values
        t = (user_key, pk, poll_id, answer, datetime.datetime.now())
        cursor.execute('insert into blog_poll_values(user_id,post_id,blog_poll_id,value,date) values (?,?,?,?,?)', t)
        con.commit()

        array = [0, 0, 0, 0, 0]

        post_values = pd.read_sql_query("select value, count(value) from (select user_id, "
            "blog_poll_id, value, max(date) as date from blog_poll_values where "
            "blog_poll_id="+str(poll_id)+" group by user_id) group by value", con)

        cursor.close()
        con.close()

        values = post_values['value'].tolist()
        counts = post_values['count(value)'].tolist()

        for value, count in zip(values, counts):
            for element in range(0, 5):
                if value == element + 1:
                    array[element] = count
        const = 1
        # Adding constant to every value
        array = [x + const for x in array]

        # Counting percentages
        sum_array = sum(array)
        if sum_array != 0:
            for element in range(0, 5):
                array[element] = int(round(array[element]*100/sum_array))

        # Completing the final array
        array = list(reversed(array))
        js_results["id"] = poll_id
        js_results["values"] = array


        return HttpResponse(
                json.dumps(js_results),
                content_type="application/json"
            )
    else:
        return HttpResponse(
            json.dumps({"error": "Упс, произошла ошибка. Попробуйте перезагрузить страницу!"}),
            content_type="application/json"
        )


def isNaN(num):
    return num != num


@login_required
def show_user_profile(request):
    # Fix for none session_key
    if not request.session.session_key:
        request.session.save()

    svg = svg_avatar(form_username(request.user))

    # User name
    fn = request.user.first_name
    ln = request.user.last_name
    if len(ln) > 0:
        user_name = fn + ' ' + ln
    else:
        if len(fn) > 0:
            user_name = fn
        else:
            user_name = request.user

    try:
        # Получаем значение тематического профиля
        user_id = request.user.social_auth.values_list("uid")[0][0]

    except IndexError:
        return render(request, 'blog/user_profile.html', {'user_name': user_name,
                                                              'topic_profile': [("Профиль не сформирован","0")],
                                                              'svg': svg})

    if not open_vk_profile(request):
        return render(request, 'blog/user_profile.html', {'user_name': user_name,
                                                          'topic_profile': [("Профиль не сформирован: профиль VK закрыт", "0")],
                                                          'svg': svg})

    # Connecting to database
    con = connect_to_database_ro()
    user_value = pd.read_sql_query("select uid, topic_profile, date, rs "
                                   "from vk_topic_profiles "
                                   "where uid=\"" + str(user_id) + "\"", con)
    con.close()

    # If vector for current user exists, fetch it from the database
    if not user_value.empty:
        topic_vector = json.loads(user_value['topic_profile'][0])
    else:
        topic_vector = []

    if len(topic_vector) != 69:
        return render(request, 'blog/user_profile.html', {'user_name': user_name,
                                                          'topic_profile': [
                                                              ("Тематический профиль не был сформирован", "0")],
                                                          'svg': svg})

    # Получаем словарь из файла
    with open(current_catalog() + "dict.json", "r") as read_file:
        dictionary = json.load(read_file)

    # Формируем новый тематический профиль
    rating = form_topic_rating(topic_vector, dictionary, True)

    # Нормализация вектора
    i = 0
    for key in rating:
        rating[key] = rating[key]*((rating[key] - medium_vector[i])/std_array_2[i])
        i += 1

    user_rating = topic_profile_ui(rating)

    for key in user_rating:
        user_rating[key] = np.round(user_rating[key], 5)

    # Сортируем получившийся словарь по значению
    sorted_dict = sorted(user_rating.items(), key=operator.itemgetter(1), reverse=True)

    # Убираем из списка категории, значения которых меньше 0
    final_dict = []
    for tup in sorted_dict:
        if float(tup[1]) > 0:
            final_dict.append(tup)
        else:
            break

    return render(request, 'blog/user_profile.html', {'user_name': user_name,
                                                      'topic_profile': final_dict,
                                                      'svg': svg})

@login_required
def show_user_history(request):
    # Fix for none session_key

    if not request.session.session_key:
        request.session.save()

    user_key = get_user_key(request)

    # Connecting to database
    con = connect_to_database_ro()
    # Getting all polls this user voted
    posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('-views')

    poll_texts = []
    cmap = {1: 'Абсолютно не согласен', 2: 'Скорее не согласен',
            3: 'Отношусь нейтрально', 4: 'Скорее согласен',
            5: 'Совершенно согласен'}

    for post in posts:
        for quote in post.quotes.all():
            for poll in quote.polls.all():
                # print(poll.question)
                post_val = pd.read_sql_query("select user_id, blog_poll_id, post_id, value, "
                      "max(date) as date from blog_poll_values where blog_poll_id="
                      + str(poll.id) + " and user_id=\"" + str(user_key) + "\"", con)

                if post_val['value'][0] is not None:
                    value = post_val['value'][0]
                    date = post_val['date'][0].split()
                    date = date[0].split("-")
                    # print(date)

                    if not isNaN(value):
                        value = cmap[value]
                        poll_texts.append((poll, value, date))

    # cursor.execute('DELETE FROM vk_topic_profiles WHERE uid=189183825')
    # con.commit()

    con.close()


    # User name
    fn = request.user.first_name
    ln = request.user.last_name
    if len(ln) > 0:
        user_name = fn + ' ' + ln
    else:
        if len(fn) > 0:
            user_name = fn
        else:
            user_name = request.user

    svg = svg_avatar(form_username(request.user))

    return render(request, 'blog/user_history.html', {'poll_texts': poll_texts,
                                                      'user_name': user_name, 'svg': svg})


# On post save, call topic_profile_rebuild
@receiver(post_save, sender=Post)
def post_handler(sender, instance, update_fields, **kwargs):
    if update_fields is not None and len(update_fields) == 2:
        check = 0
        for field in update_fields:
            if field == "topic_profile":
                check += 1
            if field == "tp_rating":
                check += 1
        if check == 2:
            return

    post_topic_profile(instance)


# On Quote & Poll save or delete, call topic_profile rebuild
@receiver(post_save, sender=Quote)
@receiver(post_delete, sender=Quote)
def quote_handler(instance, **kwargs):
    post_topic_profile(instance.post)


@receiver(post_save, sender=Poll)
@receiver(post_delete, sender=Poll)
def poll_handler(instance, **kwargs):
    post_topic_profile(instance.quote.post)


# Rebuilds topic profiles for selected posts
def post_topic_profile(posts):
    if os.getcwd() == home_path:
        with open("dict.json", "r") as read_file:
            dictionary = json.load(read_file)
    else:
        with open("proetcontra/dict.json", "r") as read_file:
            dictionary = json.load(read_file)

    if isinstance(posts, Post):
        posts = [posts]

    for post in posts:
        # if len(post.quotes.all()) == 0:
        #     continue

        post_text = ""
        # print("Dude, i'm rebuilding vector for " + str(post.title))
        post_text += post.title + '\n'

        for quote in post.quotes.all():
            post_text += quote.quote + '\n'

            for poll in quote.polls.all():
                post_text += poll.question + '\n'

        # Building topic profile for post's text
        vector = form_doc_vector(normalize_doc(post_text), dictionary, True)

        post.topic_profile = json.dumps(vector)

        rating = ""
        for line in form_topic_rating(vector, dictionary)[:5]:
            rating += line[0] + ": " + str(np.round(line[1], 5)) + "\n"

        post.tp_rating = rating
        post.save(update_fields=["topic_profile", "tp_rating"])

        # # json.loads(source)

        # print(form_topic_rating(vector, dictionary)[:5])


    return 0


@login_required
def post_new(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm()
    return render(request, 'blog/post_edit.html', {'form': form})


@login_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm(instance=post)
    return render(request, 'blog/post_edit.html', {'form': form})


@login_required
def post_draft_list(request):
    posts = Post.objects.filter(published_date__isnull=True).order_by('created_date')
    return render(request, 'blog/post_draft_list.html', {'posts': posts})


@login_required
def post_publish(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.publish()
    return redirect('post_detail', pk=pk)


@login_required
def post_remove(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.delete()
    return redirect('post_list')


def add_comment_to_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            fn = request.user.first_name
            ln = request.user.last_name
            if len(ln) > 0:
                comment.author = fn + ' ' + ln
            else:
                if len(fn) > 0:
                    comment.author = fn
                else:
                    comment.author = request.user
            comment.post = post
            comment.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = CommentForm()
    return render(request, 'blog/add_comment_to_post.html', {'form': form})


@login_required
def comment_approve(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    comment.approve()
    return redirect('post_detail', pk=comment.post.pk)


@login_required
def comment_remove(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    comment.delete()
    return redirect('post_detail', pk=comment.post.pk)


@login_required
def home(request):
    return render(request, 'core/home.html')