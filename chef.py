"""
PRATHAM Open School is organized as follow:
- There is top level set of topics (e.g. Mathematics, English, Science, ...)
- Each topic has subtopics (e.g. Geometry, Algebra, ...)
- Each subtopic has lessons (e.g. Triangle, Circle, Polygons, ...)
- Finally, each subtopic has contents like videos, pdfs and html5 files.

TODO: hn/Fun and hn/Story do not follow this structure. For now, they
are not being scraped.
"""

import os
import re
import requests
import shutil
import tempfile
import urllib
import zipfile

from bs4 import BeautifulSoup
from le_utils.constants import licenses
from ricecooker.classes.files import VideoFile, HTMLZipFile, WebVideoFile, ThumbnailFile
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode, ExerciseNode
from ricecooker.config import LOGGER
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip

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
            LOGGER.info('  subtopic: %s' % (subtopic['href']))
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
            LOGGER.info('    lesson: %s' % (link))
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
            main_file, master_file = get_content_link(content)
            if main_file.endswith('mp4'):
                video = VideoNode(
                    title=title,
                    source_id=get_source_id(main_file),
                    license=licenses.PUBLIC_DOMAIN,
                    files=[VideoFile(main_file)])
                parent.add_child(video)
            elif main_file.endswith('pdf'):
                # TODO
                pass
            elif main_file.endswith('html') and master_file.endswith('zip'):
                html5app = get_zip_file(master_file, main_file, title)
                if html5app:
                    parent.add_child(html5app)
            else:
                LOGGER.error('Content not supported: %s, %s' % (main_file, master_file))
        except Exception as e:
            LOGGER.error('get_contents: %s : %s' % (e, content))


# Helper functions
def get_absolute_path(path):
    return urllib.parse.urljoin('http://www.' + DOMAIN, path)


def make_request(url):
    response = session.get(url)
    if response.status_code != 200:
        LOGGER.error("NOT FOUND: %s" % (url))
    return response


def get_page(path):
    url = get_absolute_path(path)
    resp = make_request(url)
    return BeautifulSoup(resp.content, 'html.parser')


def get_source_id(path):
    return path.strip('/').split('/')[-1]


def get_content_link(content):
    """The link to a content has an onclick attribute that executes
    the res_click function. This function has 4 parameters:
    - The main file (e.g. an mp4 file, an entry html page to a game).
    - The type of resource (video, internal link, ...).
    - A description.
    - A master file (e.g. for a game, it is a zip file).
    """
    link = content.find('a', {'id': 'navigate'})
    regex = re.compile(r"res_click\('(.*)','.*','.*','(.*)'\)")
    match = regex.search(link['onclick'])
    link = match.group(1)
    main_file = get_absolute_path(link)
    master_file = match.group(2)
    if master_file:
        master_file = get_absolute_path(master_file)
    return main_file, master_file


def get_zip_file(zip_file_url, main_file, title):
    """HTML games are provided as zip files, the entry point of the game is
     main_file. main_file needs to be renamed to index.html to make it
     compatible with Kolibri.
    """
    destpath = tempfile.mkdtemp()
    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]
        zip_basename = zip_filename.rsplit('.', 1)[0]
        zip_folder = os.path.join(destpath, zip_basename)

        # Extract zip file contents.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            zf.extractall(destpath)

        # In some cases, the files are under the www directory,
        # let's move them up one level.
        www_dir = os.path.join(zip_folder, 'www')
        if os.path.isdir(www_dir):
            files = os.listdir(www_dir)
            for f in files:
                shutil.move(os.path.join(www_dir, f), zip_folder)

        # Rename main_file to index.html.
        main_file = main_file.split('/')[-1]
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'index.html')
        os.rename(src, dest)

        zippath = create_predictable_zip(zip_folder)
        html5app = HTML5AppNode(
            files=[HTMLZipFile(zippath)],
            title=title,
            # thumbnail=thumbnail,
            source_id=main_file,
            license=licenses.PUBLIC_DOMAIN,
        )
        return html5app
    except Exception as e:
        LOGGER.error("get_zip_file: %s, %s, %s, %s, %s" %
                     (zip_file_url, main_file, title, destpath, e))
        return None
