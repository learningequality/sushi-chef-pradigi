"""
PRATHAM Open School is organized as follow:
- There is top level set of topics (e.g. Mathematics, English, Science, ...)
- Each topic has subtopics (e.g. Geometry, Algebra, ...)
- Each subtopic has lessons (e.g. Triangle, Circle, Polygons, ...)
- Finally, each subtopic has contents like videos, pdfs and html5 files.

TODO: hn/Fun and hn/Story do not follow this structure. For now, they
are not being scraped.
"""

import re
import requests
import urllib

from bs4 import BeautifulSoup
from le_utils.constants import licenses
from ricecooker.classes.files import VideoFile, HTMLZipFile, WebVideoFile, ThumbnailFile
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode, ExerciseNode
from ricecooker.config import LOGGER
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter

DOMAIN = 'prathamopenschool.org'

# In debug mode, only one topic is downloaded.
DEBUG_MODE = False

# Cache logic.
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(),
                                      cache=cache)
session = requests.Session()
session.mount('http://', basic_adapter)
session.mount('https://', basic_adapter)
session.mount('http://www.' + DOMAIN, forever_adapter)
session.mount('https://www.' + DOMAIN, forever_adapter)


def construct_channel(*args, **kwargs):
    global DEBUG_MODE
    DEBUG_MODE = 'debug' in kwargs
    language = kwargs['language']
    channel = ChannelNode(
        title='Pratham Open School {}'.format(language),
        source_domain=DOMAIN,
        source_id='pratham-open-school-{}'.format(language),
    )
    get_topics(channel, language)
    return channel


def get_topics(parent, path):
    doc = get_page(path)
    try:
        menu_row = doc.find('div', {'id': 'menu-row'})
    except Exception as e:
        LOGGER.error('get_topics: %s : %s' % (e, doc))
        return
    for topic in menu_row.find_all('a'):
        try:
            if topic['href'] == '#':
                continue
            LOGGER.info('topic: %s' % (topic['href']))
            title = topic.get_text().strip()
            source_id = get_source_id(topic['href'])
            node = TopicNode(title=title, source_id=source_id)
            parent.add_child(node)
            get_subtopics(node, topic['href'])
            if DEBUG_MODE:
                return
        except Exception as e:
            LOGGER.error('get_topics: %s : %s' % (e, topic))


def get_subtopics(parent, path):
    doc = get_page(path)
    try:
        menu_row = doc.find('div', {'id': 'body-row'})
        menu_row = menu_row.find('div', {'class': 'col-md-2'})
    except Exception as e:
        LOGGER.error('get_subtopics: %s : %s' % (e, doc))
        return
    for subtopic in menu_row.find_all('a'):
        try:
            LOGGER.info('subtopic: %s' % (subtopic['href']))
            title = subtopic.get_text().strip()
            source_id = get_source_id(subtopic['href'])
            node = TopicNode(title=title, source_id=source_id)
            parent.add_child(node)
            get_lessons(node, subtopic['href'])
        except Exception as e:
            LOGGER.error('get_subtopics: %s : %s' % (e, subtopic))


def get_lessons(parent, path):
    doc = get_page(path)
    try:
        menu_row = doc.find('div', {'id': 'body-row'})
        menu_row = menu_row.find('div', {'class': 'col-md-9'})
    except Exception as e:
        LOGGER.error('get_lessons: %s : %s' % (e, doc))
        return
    for lesson in menu_row.find_all('div', {'class': 'thumbnail'}):
        try:
            title = lesson.find('div', {'class': 'txtline'}).get_text().strip()
            link = lesson.find('a')['href']
            LOGGER.info('lesson: %s' % (link))
            source_id = get_source_id(link)
            node = TopicNode(title=title, source_id=source_id)
            parent.add_child(node)
            get_contents(node, link)
        except Exception as e:
            LOGGER.error('get_lessons: %s : %s' % (e, lesson))


def get_contents(parent, path):
    doc = get_page(path)
    try:
        menu_row = doc.find('div', {'id': 'row-exu'})
    except Exception as e:
        LOGGER.error('get_contents: %s : %s' % (e, doc))
        return
    for content in menu_row.find_all('div', {'class': 'col-md-3'}):
        try:
            title = content.find('div', {'class': 'txtline'}).get_text()
            link = get_content_link(content)
            if link.endswith('mp4'):
                video = VideoNode(
                    title=title,
                    source_id=get_source_id(link),
                    license=licenses.PUBLIC_DOMAIN,
                    files=[VideoFile(link)])
                parent.add_child(video)
                if DEBUG_MODE:
                    return
            elif link.endswith('pdf'):
                # TODO
                pass
            elif link.endswith('html'):
                # TODO
                pass
        except Exception as e:
            LOGGER.error('get_contents: %s : %s' % (e, content))


# Helper functions
def get_absolute_path(path):
    return urllib.parse.urljoin('http://www.' + DOMAIN, path)


def get_page(path):
    url = get_absolute_path(path)
    resp = session.get(url)
    return BeautifulSoup(resp.content, 'html.parser')


def get_source_id(path):
    return path.strip("/").split("/")[-1]


def get_content_link(content):
    link = content.find('a', {'id': 'navigate'})
    regex = re.compile(r"res_click\('(.*)','.*','.*','.*'\)")
    match = regex.search(link['onclick'])
    link = match.group(1)
    link = get_absolute_path(link)
    return link
