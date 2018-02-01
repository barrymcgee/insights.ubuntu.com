# Core
import urllib

# Third-party
import flask
from flask import request

# Local
import api
import helpers
import local_data
from werkzeug.routing import BaseConverter


INSIGHTS_URL = 'https://insights.ubuntu.com'

app = flask.Flask(__name__)


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter


@app.route('/')
def homepage():
    """
    Return search results, or homepage content
    """

    search_query = request.args.get('q')

    if search_query:
        page = flask.request.args.get('page') or 1

        posts, meta = api.get_posts(search=search_query, page=page)

        return flask.render_template(
            'search.html',
            query=search_query,
            total=meta['total'],
            pages=meta['pages'],
            page=page
        )

    posts, meta = api.get_posts(per_page=13)

    webinars = helpers.get_rss_feed_content(
        'https://www.brighttalk.com/channel/6793/feed'
    )

    featured_posts, meta = api.get_posts(sticky=True, per_page=1)
    featured_post = featured_posts[0] if featured_posts else None

    homepage_posts = []

    # Format posts
    for post in posts:
        # Skip the featured post, if found
        if featured_post and post['id'] == featured_post['id']:
            continue

        # Add group data for first group
        if post['group']:
            post['group'] = local_data.get_group_by_id(
                int(post['group'][0])
            )

        # Expand categories
        post['category'] = local_data.get_category_by_id(
            post['categories'][0]
        )

        # Add the post to the list
        homepage_posts.append(post)

    return flask.render_template(
        'index.html',
        posts=homepage_posts[:12],
        featured_post=featured_post,
        webinars=webinars,
    )


@app.route('/<group>/')
@app.route('/<group>/<category>/')
def group_category(group_slug, category_slug='all'):
    if group_slug == 'press-centre':
        group_slug = 'canonical-announcements'

    group = api.get_group_by_slug(group_slug)

    if not group:
        flask.abort(404)

    group = api.get_group_details(group)  # read the json file

    group_ids = [group['id']]

    if category_slug:
        category = api.get_category_by_slug(category_slug)

        if not category:
            flask.abort(404)

        category_id = [category['id']]

    page = flask.request.args.get('page') or 1
    posts, meta = api.get_posts(
        groups_id=group_ids,
        categories=[category_id] if category_id else [],
        page=page,
        per_page=12
    )

    for post in posts:
        post['groups'] = [group]
        post['category'] = local_data.get_category_by_id(post['categories'][0])

    return flask.render_template(
        'group.html',
        posts=posts,
        group=group,
        category=category if category else None,
        page=page,
        pages=meta['pages'],
        total=meta['total'],
    )


@app.route('/topics/<slug>/')
def topic_name(slug):
    topic = api.get_topic_details(slug)

    if topic:
        response_json = api.get_topic(topic['slug'])

        if response_json:
            tag = response_json[0]
            page = flask.request.args.get('page')
            posts, metadata = api.get_posts(tags=tag['id'], page=page)
        else:
            return flask.render_template(
                '404.html'
            )

        return flask.render_template(
            'topics.html', topic=topic, posts=posts, tag=tag, **metadata
        )
    else:
        return flask.render_template(
            '404.html'
        )


@app.route('/tag/<slug>/')
def tag_index(slug):
    response_json = api.get_tag(slug)

    if response_json:
        tag = response_json[0]
        page = flask.request.args.get('page')
        posts, metadata = api.get_posts(tags=[tag['id']], page=page)

        return flask.render_template(
            'tag.html', posts=posts, tag=tag, **metadata
        )
    else:
        return flask.render_template(
            '404.html'
        )


@app.route('/archives/<regex("[0-9]{4}"):year>/')
def archives_year(year):
    result = api.get_archives(year)
    return flask.render_template('archives.html', result=result)


@app.route('/archives/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/')
def archives_year_month(year, month):
    result = api.get_archives(year, month)
    return flask.render_template('archives.html', result=result)


@app.route(
    '/archives/<group>/<regex("[0-9]{4}"):year>/<regex("[0-9]{2}"):month>/'
)
def archives_group_year_month(group, year, month):
    group_id = ''
    groups = []
    if group:
        if group == 'press-centre':
            group = 'canonical-announcements'

        groups = api.get_group_by_slug(group)
        group_id = int(groups['id']) if groups else None
        group_name = groups['name'] if groups else None

        if not group_id:
            return flask.render_template(
                '404.html'
            )
    result = api.get_archives(year, month, group_id, group_name)
    return flask.render_template('archives.html', result=result)


@app.route(
    '/<regex("[0-9]{4}"):year>'
    '/<regex("[0-9]{2}"):month>'
    '/<regex("[0-9]{2}"):day>'
    '/<slug>/'
)
def post(year, month, day, slug):
    posts = api.get_posts(slugs=[slug])

    if not posts:
        flask.abort(404)

    post = posts[0]

    related_posts, meta = api.get_posts(per_page=3, post_id=post['id'])

    return flask.render_template(
        'post.html',
        post=post,
        tags=api.get_tag_details_from_post(post['id']),
        related_posts=related_posts
    )


@app.route('/author/<slug>/')
def user(slug):
    authors = api.get_users(slugs=[slug])

    if not authors:
        flask.abort(404)

    author = authors[0]

    recent_posts, meta = api.get_posts(author_ids=[author['id']], per_page=5)

    return flask.render_template(
        'author.html',
        author=author,
        recent_posts=recent_posts
    )


@app.route('/admin/')
@app.route('/feed/')
@app.route('/wp-content/')
@app.route('/wp-includes/')
@app.route('/wp-login.php/')
def redirect_wordpress_login():
    path = flask.request.path
    if (flask.request.args):
        path = '?'.join([path, urllib.parse.urlencode(flask.request.args)])

    return flask.redirect(INSIGHTS_URL + path)


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(410)
def page_deleted(e):
    return flask.render_template('410.html'), 410


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('500.html'), 500
