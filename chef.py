#!/usr/bin/env python
"""
PRATHAM Open School (PraDigi) content is organized as follow:
- There is top level set of topics (e.g. Mathematics, English, Science, ...)
- Each topic has subtopics (e.g. Geometry, Algebra, ...)
- Each subtopic has lessons (e.g. Triangle, Circle, Polygons, ...)
- Finally, each lesson has contents like videos, pdfs and html5 files.
"""

import os
import re
import requests
import shutil
import tempfile
from urllib.parse import urljoin
import zipfile


from basiccrawler.crawler import BasicCrawler
from bs4 import BeautifulSoup
from le_utils.constants import licenses
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import VideoFile, HTMLZipFile, DocumentFile
from ricecooker.classes.nodes import (ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode)
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils.caching import (CacheForeverHeuristic, FileCache, CacheControlAdapter)
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip

DOMAIN = 'prathamopenschool.org'
FULL_DOMAIN_URL = 'http://www.' + DOMAIN
PRADIGI_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='PraDigi')
PRADIGI_LANGUAGES = ['hn', 'mr']
PRADIGI_LANG_URL_MAP = {
    'hn': 'http://www.prathamopenschool.org/hn/',
    'mr': 'http://www.prathamopenschool.org/mr/',
}


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




class PraDigiCrawler(BasicCrawler):
    CRAWLING_STAGE_OUTPUT = 'chefdata/trees/pradigi_web_resource_tree.json'
    MAIN_SOURCE_DOMAIN = FULL_DOMAIN_URL
    START_PAGE_CONTEXT = {'kind': 'lang_page'}
    kind_handlers = {
        'lang_page': 'on_lang_page',
        'topic_page': 'on_topic_page',
        'games_page': 'on_games_page',
        'subtopic_page': 'on_subtopic_page',
        'lesson_page': 'on_lesson_page',
    }


    def on_lang_page(self, url, page, context):
        LOGGER.debug('in on_lang_page ' + url)
        page_dict = dict(
            kind='lang_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'menu-row'})
        except Exception as e:
            LOGGER.error('on_lang_page: %s : %s' % (e, page))
            return
        for topic in menu_row.find_all('a'):
            try:
                if topic['href'] == '#':
                    print('skipping', topic)
                    continue
                topic_url = urljoin(url, topic['href'])
                title = topic.get_text().strip()
                source_id = get_source_id(topic['href'])
                
                if 'Fun' in topic['href'] or 'Story' in topic['href']:
                    LOGGER.info('found games page: %s: %s' % (source_id, title))
                    context = dict(
                        parent=page_dict,
                        kind='games_page',
                        title=title,
                        source_id=source_id,
                    )
                    self.enqueue_url_and_context(topic_url, context)

                else:
                    LOGGER.info('found topic: %s: %s' % (source_id, title))
                    context = dict(
                        parent=page_dict,
                        kind='topic_page',
                        title=title,
                        source_id=source_id,
                    )
                    self.enqueue_url_and_context(topic_url, context)

                if DEBUG_MODE:
                    return
            except Exception as e:
                LOGGER.error('on_lang_page: %s : %s' % (e, topic))


    def on_topic_page(self, url, page, context):
        LOGGER.debug('in on_topic_page ' + url)
        page_dict = dict(
            kind='topic_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            menu_row = body_row.find('div', {'class': 'col-md-2'})
        except Exception as e:
            LOGGER.error('get_subtopics: %s : %s' % (e, page))
            return
        for subtopic in menu_row.find_all('a'):
            try:
                subtopic_url = urljoin(url, subtopic['href'])
                title = subtopic.get_text().strip()
                source_id = get_source_id(subtopic['href'])
                LOGGER.info('  found subtopic: %s: %s' % (source_id, title))
                context = dict(
                    parent=page_dict,
                    kind='subtopic_page',
                    title=title,
                    source_id=source_id,
                )
                self.enqueue_url_and_context(subtopic_url, context)
            except Exception as e:
                LOGGER.error('on_topic_page: %s : %s' % (e, subtopic))


    def on_games_page(self, url, page, context):
        print('     in on_games_page', url)
        page_dict = dict(
            kind='games_page_WIP',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)






    def on_subtopic_page(self, url, page, context):
        print('     in on_subtopic_page', url)
        page_dict = dict(
            kind='subtopic_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'body-row'})
            menu_row = menu_row.find('div', {'class': 'col-md-9'})
        except Exception as e:
            LOGGER.error('on_subtopic_page: %s : %s' % (e, page))
            return
        for lesson in menu_row.find_all('div', {'class': 'thumbnail'}):
            try:
                title = lesson.find('div', {'class': 'txtline'}).get_text().strip()
                lesson_url = urljoin(url, lesson.find('a')['href'])
                thumbnail_src = lesson.find('a').find('img')['src']
                thumbnail_url = urljoin(url, thumbnail_src)
                source_id = get_source_id(lesson.find('a')['href'])
                LOGGER.info('     lesson: %s: %s' % (source_id, title))
                context = dict(
                    parent=page_dict,
                    kind='lesson_page',
                    title=title,
                    source_id=source_id,
                    thumbnail_url=thumbnail_url,
                )
                self.enqueue_url_and_context(lesson_url, context)
                # get_contents(node, link)
            except Exception as e:
                LOGGER.error('on_subtopic_page: %s : %s' % (e, lesson))


    def on_lesson_page(self, url, page, context):
        print('      in on_lesson_page', url)
        page_dict = dict(
            kind='lessons_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)




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
            thumbnail = content.find('a').find('img')['src']
            thumbnail = get_absolute_path(thumbnail)
            main_file, master_file, source_id = get_content_link(content)
            LOGGER.info('      content: %s: %s' % (source_id, title))
            if main_file.endswith('mp4'):
                video = VideoNode(
                    title=title,
                    source_id=source_id,
                    license=PRADIGI_LICENSE,
                    thumbnail=thumbnail,
                    files=[VideoFile(main_file)])
                parent.add_child(video)
            elif main_file.endswith('pdf'):
                pdf = DocumentNode(
                    title=title,
                    source_id=source_id,
                    license=PRADIGI_LICENSE,
                    thumbnail=thumbnail,
                    files=[DocumentFile(main_file)])
                parent.add_child(pdf)
            elif main_file.endswith('html') and master_file.endswith('zip'):
                zippath = get_zip_file(master_file, main_file)
                if zippath:
                    html5app = HTML5AppNode(
                        title=title,
                        source_id=source_id,
                        license=PRADIGI_LICENSE,
                        thumbnail=thumbnail,
                        files=[HTMLZipFile(zippath)],
                    )
                    parent.add_child(html5app)
            else:
                LOGGER.error('Content not supported: %s, %s' %
                             (main_file, master_file))
        except Exception as e:
            LOGGER.error('get_contents: %s : %s' % (e, content))




# Helper functions
def get_absolute_path(path):
    return urljoin('http://www.' + DOMAIN, path)


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
    source_id = link['href'][1:]
    regex = re.compile(r"res_click\('(.*)','.*','.*','(.*)'\)")
    match = regex.search(link['onclick'])
    link = match.group(1)
    main_file = get_absolute_path(link)
    master_file = match.group(2)
    if master_file:
        master_file = get_absolute_path(master_file)
    return main_file, master_file, source_id


def get_zip_file(zip_file_url, main_file):
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

        return create_predictable_zip(zip_folder)
    except Exception as e:
        LOGGER.error("get_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file, destpath, e))
        return None


# CHEF
################################################################################

class PraDigiChef(SushiChef):

    def validate_language(self, language):
        if language not in LANGUAGES:
            l = ', '.join(LANGUAGES)
            raise ValueError('Invalid language, valid values: {}'.format(l))

    def get_channel(self, *args, **kwargs):
        global DEBUG_MODE
        DEBUG_MODE = 'debug' in kwargs
        language = kwargs['language']
        self.validate_language(language)
        channel = ChannelNode(
            title='PraDigi',
            source_domain=DOMAIN,
            source_id='pratham-open-school-{}'.format(language),
            thumbnail=None, # get_absolute_path('img/logop.png'),
            language='hi', # language
        )
        return channel


    def construct_channel(self, *args, **kwargs):
        channel = self.get_channel(*args, **kwargs)
        language = kwargs['language']
        get_topics(channel, language)
        return channel


# CLI
################################################################################

if __name__ == '__main__':
    pradigi_chef = PraDigiChef()
    # args, options = pradigi_chef.parse_args_and_options()
    # if 'lang' not in options:
    #     raise ValueError('Need to specify command line option `lang=XY`, where XY in en, fr, ar, sw.')
    pradigi_chef.main()

