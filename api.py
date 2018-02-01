# Core
import datetime
import calendar
import re
import json
import textwrap
from urllib.parse import urlsplit

# Third party
import dateutil.parser
import requests_cache

# Local
from helpers import join_ids, build_url


API_URL = 'https://admin.insights.ubuntu.com/wp-json/wp/v2'


# Set cache expire time
cached_session = requests_cache.CachedSession(
    name="hour-cache",
    expire_after=datetime.timedelta(hours=1),
    old_data_on_error=True
)

# Requests should timeout after 2 seconds in total
request_timeout = 10

# Static data from the API (@todo: Remove)

GROUPBYID = {
    1706: {'slug': 'cloud-and-server', 'name': 'Cloud and server'},
    1666: {'slug': 'internet-of-things', 'name': 'Internet of things'},
    1479: {'slug': 'desktop', 'name': 'Desktop'},
    2100: {
        'slug': 'canonical-announcements', 'name': 'Canonical announcements'
    },
    1707: {'slug': 'phone-and-tablet', 'name': 'Phone and tablet'},
    2051: {'slug': 'people-and-culture', 'name': 'People and culture'},
}
GROUPBYSLUG = {
    'cloud-and-server': {'id': 1706, 'name': 'Cloud and server'},
    'internet-of-things': {'id': 1666, 'name': 'Internet of things'},
    'desktop': {'id': 1479, 'name': 'Desktop'},
    'canonical-announcements': {'id': 2100, 'name': 'Canonical announcements'},
    'phone-and-tablet': {'id': 1707, 'name': 'Phone and tablet'},
    'people-and-culture': {'id': 2051, 'name': 'People and culture'},
}
CATEGORIESBYID = {
    1172: {'slug': 'case-studies', 'name': 'Case Study'},
    1187: {'slug': 'webinars', 'name': 'Webinar'},
    1189: {'slug': 'news', 'name': 'News'},
    1453: {'slug': 'articles', 'name': 'Article'},
    1485: {'slug': 'whitepapers', 'name': 'Whitepaper'},
    1509: {'slug': 'videos', 'name': 'Video'},
    2497: {'slug': 'tutorials', 'name': 'Tutorial'},
}
CATEGORIESBYSLUG = {
    'all': {'id': None, 'name': 'All'},
    'case-studies': {'id': 1172, 'name': 'Case Study'},
    'webinars': {'id': 1187, 'name': 'Webinar'},
    'news': {'id': 1189, 'name': 'News'},
    'articles': {'id': 1453, 'name': 'Article'},
    'whitepapers': {'id': 1485, 'name': 'Whitepaper'},
    'videos': {'id': 1509, 'name': 'Video'},
    'tutorials': {'id': 2497, 'name': 'Tutorial'},
}
TOPICBYID = {
    1979: {"name": "Big data", "slug": "big-data"},
    1477: {"name": "Cloud", "slug": "cloud"},
    2099: {
        "name": "Canonical announcements", "slug": "canonical-announcements"
    },
    1921: {"name": "Desktop", "slug": "desktop"},
    1924: {"name": "Internet of Things", "slug": "internet-of-things"},
    2052: {"name": "People and culture", "slug": "people-and-culture"},
    1340: {"name": "Phone", "slug": "phone"},
    1922: {"name": "Server", "slug": "server"},
    1481: {"name": "Tablet", "slug": "tablet"},
    1482: {"name": "TV", "slug": "tv"},
}


# Utility functions

def get(endpoint, parameters={}):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    url = build_url(API_URL, endpoint, parameters)

    response = cached_session.get(url)

    response.raise_for_status()

    return response


def _embed_post_data(post):
    if '_embedded' not in post:
        return post
    embedded = post['_embedded']
    post['author'] = _normalise_user(embedded['author'][0])
    post['category'] = get_category_by_id(post['categories'][0])
    if post['topic']:
        post['topics'] = get_topic_by_id(post['topic'][0])
    if 'groups' not in post and post['group']:
        post['groups'] = get_group_by_id(int(post['group'][0]))
    return post


def _normalise_user(user):
    link = user['link']
    path = urlsplit(link).path
    user['relative_link'] = path
    return user


def _normalise_posts(posts, groups_id=None):
    for post in posts:
        if post['excerpt']['rendered']:
            # replace headings (e.g. h1) to paragraphs
            post['excerpt']['rendered'] = re.sub(
                r"h\d>", "p>",
                post['excerpt']['rendered']
            )

            # remove images
            post['excerpt']['rendered'] = re.sub(
                r"<img(.[^>]*)?", "",
                post['excerpt']['rendered']
            )

            # shorten to 250 chars, on a wordbreak and with a ...
            post['excerpt']['rendered'] = textwrap.shorten(
                post['excerpt']['rendered'],
                width=250,
                placeholder="&hellip;"
            )

            # if there is a [...] replace with ...
            post['excerpt']['rendered'] = re.sub(
                r"\[\&hellip;\]", "&hellip;",
                post['excerpt']['rendered']
            )
        post = _normalise_post(post, groups_id=groups_id)
    return posts


def _normalise_post(post, groups_id=None):
    link = post['link']
    path = urlsplit(link).path
    post['relative_link'] = path
    post['formatted_date'] = datetime.datetime.strftime(
        dateutil.parser.parse(post['date']),
        "%d %B %Y"
    ).lstrip("0").replace(" 0", " ")

    if groups_id:
        post['groups'] = get_group_by_id(groups_id)

    post = _embed_post_data(post)
    return post


def search_posts(search):
    response = get('posts', {'_embed': True, 'search': search})
    posts = _normalise_posts(json.loads(response.text))

    return posts


def get_topic(slug):
    response = get('topic', {'slug': slug})

    return json.loads(response.text)


def get_tag(slug):
    response = get('tags', {'slug': slug})

    return json.loads(response.text)


def get_post(slug):
    response = get('posts', {'_embed': True, 'slug': slug})
    post = json.loads(response.text)[0]
    post['tags'] = get_tag_details_from_post(post['id'])
    post = _normalise_post(post)
    post['related_posts'] = get_related_posts(post)

    return post


def get_author(slug):
    response = get('users', {'_embed': True, 'slug': slug})
    user = json.loads(response.text)[0]
    user = _normalise_user(user)
    user['recent_posts'] = get_user_recent_posts(user['id'])

    return user


def get_posts(groups_id=None, categories=[], tags=[], page=1, per_page=12):
    response = get(
        'posts',
        {
            '_embed': True,
            'per_page': per_page,
            'page': page,
            'group': groups_id,
            'categories': join_ids(categories),
            'tags': join_ids(tags)
        }
    )

    headers = response.headers
    metadata = {
        'current_page': page or 1,
        'total_pages': headers.get('X-WP-TotalPages'),
        'total_posts': headers.get('X-WP-Total'),
    }

    posts = _normalise_posts(
        json.loads(response.text),
        groups_id=groups_id
    )

    return posts, metadata


def get_archives(
    year,
    month=None, group_id=None, group_name='Archives',
    categories=[], tags=[], page=1, per_page=100
):
    result = {}
    startmonth = 1
    endmonth = 12
    if month:
        startmonth = month
        endmonth = month
    last_day = calendar.monthrange(int(year), int(endmonth))[1]
    after = datetime.datetime(int(year), int(startmonth), 1)
    before = datetime.datetime(int(year), int(endmonth), last_day)

    response = get(
        'posts',
        {
            '_embed': True,
            'group': group_id,
            'before': before.isoformat(),
            'after': after.isoformat(),
            'per_page': per_page,
            'page': page
        }
    )

    posts = _normalise_posts(json.loads(response.text))
    if month:
        result["date"] = after.strftime("%B") + ' ' + str(year)
    else:
        result["date"] = str(year)
    if group_name != "Archives":
        group_name = group_name + ' archives'
    result["title"] = group_name
    result["posts"] = posts
    result["count"] = len(posts)
    return result


def get_related_posts(post):
    response = get(
        'tags',
        {
            'embed': True,
            'per_page': 3,
            'post': post['id']
        }
    )
    tags = json.loads(response.text)

    tag_ids = [tag['id'] for tag in tags]
    posts, meta = get_posts(tags=tag_ids)
    posts = _normalise_posts(posts)

    return posts


def get_user_recent_posts(user_id, limit=5):
    response = get(
        'posts',
        {
            'embed': True,
            'author': user_id,
            'per_page': limit,
        }
    )
    posts = _normalise_posts(json.loads(response.text))

    return posts


def get_tag_details_from_post(post_id):
    response = get('tags', {'post': post_id})
    tags = json.loads(response.text)

    return tags


def get_featured_post(groups_id=None, categories=[], per_page=1):
    response = get(
        'posts',
        {
            '_embed': True,
            'sticky': True,
            'per_page': per_page,
            'group': groups_id,
            'categories': join_ids(categories)
        }
    )
    posts = _normalise_posts(json.loads(response.text), groups_id=groups_id)

    return posts[0] if posts else None


def get_category_by_id(category_id):
    global CATEGORIESBYID
    return CATEGORIESBYID[category_id]


def get_category_by_slug(category_name):
    global CATEGORIESBYSLUG
    return CATEGORIESBYSLUG[category_name]


def get_group_by_id(group_id):
    global GROUPBYID
    return GROUPBYID[group_id]


def get_group_by_slug(group_slug):
    global GROUPBYSLUG
    return GROUPBYSLUG[group_slug]


def get_topic_by_id(topic_id):
    global TOPICBYID
    return TOPICBYID[topic_id]


def get_group_details(slug):
    with open('data/groups.json') as file:
        groups = json.load(file)

    for group in groups:
        if group['slug'] == slug:
            return group


def get_topic_details(slug):
    with open('data/topics.json') as file:
        topics = json.load(file)

    for topic in topics:
        if topic['slug'] == slug:
            return topic
