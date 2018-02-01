# Core
import datetime
import calendar
import json
from urllib.parse import urlsplit

# Third party
import requests_cache

# Local
import helpers


API_URL = 'https://admin.insights.ubuntu.com/wp-json/wp/v2'


# Set cache expire time
cached_session = requests_cache.CachedSession(
    name="hour-cache",
    expire_after=datetime.timedelta(hours=1),
    old_data_on_error=True
)

# Requests should timeout after 2 seconds in total
request_timeout = 10


def get(endpoint, parameters={}):
    """
    Retrieve the response from the requests cache.
    If the cache has expired then it will attempt to update the cache.
    If it gets an error, it will use the cached response, if it exists.
    """

    url = helpers.build_url(API_URL, endpoint, parameters)

    response = cached_session.get(url)

    response.raise_for_status()

    return response


def get_tag(slug):
    response = get('tags', {'slug': slug})

    return json.loads(response.text)


def get_users(slugs):
    response = get('users', {'slug': ','.join(slugs)})

    users = response.json()

    for user in users:
        user['link'] = urlsplit(user['link']).path

    return users


def get_posts(
    page=1, per_page=12, search_query='', sticky=None,
    slugs=[], group_ids=[], category_ids=[], tag_ids=[], author_ids=[],
    before=None, after=None
):
    """
    Query posts from the wordpress API, optionally filtering by
    the parameters offered by the API.

    Transform the returned posts in the following ways:
    - Add a "summary" by reformatting the "excerpt"
    - Make the link relative
    - Format the date as e.g. "1 January 2008"
    - Add the author information, including making the link relative
    - Expand category information
    """

    # Retrieve posts
    response = get(
        'posts',
        {
            '_embed': True,
            'per_page': per_page,
            'page': page,
            'search': search_query,
            'group': helpers.join_ids(group_ids),
            'categories': helpers.join_ids(category_ids),
            'tags': helpers.join_ids(tag_ids),
            'author': helpers.join_ids(author_ids),
            'before': before,
            'after': after
        }
    )
    posts = response.json()

    # Format posts
    for post in posts:
        if 'excerpt' in post and 'rendered' in post['excerpt']:
            post['summary'] = helpers.format_excerpt(
                post['excerpt']['rendered']
            )

        post['date'] = helpers.format_date(post['date'])
        post['link'] = urlsplit(post['link']).path
        post['author'] = post['_embedded']['author'][0]
        post['author']['link'] = urlsplit(post['author']['link']).path

    return (
        posts,
        {
            'pages': response.headers.get('X-WP-TotalPages'),
            'total': response.headers.get('X-WP-Total')
        }
    )


def get_archives(
    year,
    month=None, group_id=None, group_name='Archives',
    categories=[], tags=[], page=1, per_page=100
):
    """

    """

    result = {}
    startmonth = 1
    endmonth = 12

    if month:
        startmonth = month
        endmonth = month

    last_day = calendar.monthrange(int(year), int(endmonth))[1]
    after = datetime.datetime(int(year), int(startmonth), 1)
    before = datetime.datetime(int(year), int(endmonth), last_day)

    response = get_posts(
        before=before.isoformat(),
        after=after.isoformat()
    )

    posts = json.loads(response.text)

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
