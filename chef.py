#!/usr/bin/env python
"""
PRATHAM Open School (PraDigi) content is organized as follow:
- There is top level set of topics (e.g. Mathematics, English, Science, ...)
    - Each topic has subtopics (e.g. Geometry, Algebra, ...)
        - Each subtopic has lessons (e.g. Triangle, Circle, Polygons, ...)
            - Finally, each lesson has contents like videos, pdfs and html5 zip files.
    - The Fun/ page contains various videos and HTML5 visaulisations
    - The Stories/ page contains PDFs
    - The gamelist/ contains various HTML5 games
      (not used, instead use games form http://www.gamerepo.prathamcms.org/)
"""

import csv
import json
import logging
import os
import re
import requests
import shutil
import tempfile
from urllib.parse import urljoin, urlparse
import zipfile


from basiccrawler.crawler import BasicCrawler
from bs4 import BeautifulSoup
from le_utils.constants import content_kinds, file_types, licenses
from le_utils.constants.languages import getlang, getlang_by_name
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import VideoFile, HTMLZipFile, DocumentFile
from ricecooker.classes.nodes import (ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode)
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils import downloader
from ricecooker.utils.caching import (CacheForeverHeuristic, FileCache, CacheControlAdapter)
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip

DOMAIN = 'prathamopenschool.org'
FULL_DOMAIN_URL = 'http://www.' + DOMAIN
PRADIGI_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='PraDigi').as_dict()
PRADIGI_LANGUAGES = ['hi', 'en', 'or', 'bn', 'pnb', 'kn', 'ta', 'te', 'mr', 'gu', 'as']
# 'mr']  # le-utils language codes for Hindi and Marathi
PRADIGI_LANG_URL_MAP = {
    'hi': 'http://www.prathamopenschool.org/hn/',
    'mr': 'http://www.prathamopenschool.org/mr/',
}
PRADIGI_STRINGS = {
    'hi': {
        'language_en': 'Hindi',
        'gamesrepo_suffixes': ['_KKS', '_HI'],
        'strings': {
            "Mathematics": "गणित",
            "English": "अंग्रेजी",
            "Health": "स्वास्थ्य",
            "Science": "विज्ञान",
            "Hospitality": "अतिथी सत्कार",
            "Construction": "भवन-निर्माण",
            "Automobile": "वाहन",
            "Electric": "इलेक्ट्रिक",
            "Beauty": "ब्युटी",
            "Healthcare": "स्वास्थ्य सेवा",
            "Std8": "8 वी कक्षा",
            "Fun": "मौज",
            "Story": "कहानियाँ",
        }
    },
    'en': {
        'language_en': 'English',
        'gamesrepo_suffixes': [],
        'strings': {
            "Mathematics": "Mathematics",
            "English": "English",
            "Health": "Health",
            "Science": "Science",
            "Hospitality": "Hospitality",            
            "Construction": "Construction",
            "Automobile": "Automobile",
            "Electric": "Electric",
            "Beauty": "Beauty",
            "Healthcare": "Healthcare",
            "Std8": "Std8",
            "Fun": "Fun",
            "Story": "Story",
        }
    },
    "or": {
        "language_en": "Odiya",
        "gamesrepo_suffixes": ['_OD'],
        "strings": {}
    },
    "bn": {
        "language_en": "Bangali",
        "gamesrepo_suffixes": ['_BN'],
        "strings": {}
    },
    "pnb": {
        "language_en": "Punjabi",
        "gamesrepo_suffixes": ['_PN'],
        "strings": {}
    },
    "kn": {
        "language_en": "Kannada",
        "gamesrepo_suffixes": ['_KN'],
        "strings": {}
    },
    "ta": {
        "language_en": "Tamil",
        "gamesrepo_suffixes": ['_TM'],
        "strings": {}
    },
    "te": {
        "language_en": "Telugu",
        "gamesrepo_suffixes": ['_TL'],
        "strings": {}
    },
    "mr": {
        "language_en": "Marathi",
        "gamesrepo_suffixes": ['_MR'],
        "strings": {}
    },
    "gu": {
        "language_en": "Gujarati",
        "gamesrepo_suffixes": ['_KKS', '_GJ'],
        "strings": {}
    },
    "as": {
        "language_en": "Assamese",
        "gamesrepo_suffixes": ['_AS', 'AS_Assamese'],
        "strings": {}
    },
}
# TODO: get lang strings for all other languages in the gamesrepo





# In debug mode, only one topic is downloaded.
LOGGER.setLevel(logging.INFO)
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





def find_games_for_lang(name, lang):
    data = json.load(open('chefdata/trees/pradigi_games_all_langs.json','r'))
    language_en = PRADIGI_STRINGS[lang]['language_en']
    suffixes = PRADIGI_STRINGS[lang]['gamesrepo_suffixes']
    assert data["kind"] == "index_page", 'wrong web resource tree loaded'
    games = []
    for gameslang_page in data['children']:
        if gameslang_page['language_en'] == language_en:
            for game in gameslang_page['children']:                
                title = game['title']
                for suffix in suffixes:
                    if title.strip().endswith(suffix):
                        title = title.replace(suffix, '').strip()
                if name == title:
                    games.append(game)
            return games 
    return None

def flatten_tree(tree):
    if len(tree['children'])==0:
        return [tree]
    else:
        result = []
        for child in tree['children']:
            flat_child = flatten_tree(child)
            result.extend(flat_child)
        return result
        


# TODO: get from google sheet....
TEST_GAMENAMES = [
    'Aakar',
    'ABCD',
    'AgePiche',
    'Aksharkhadi',
    'Atulya Bharat',
    'AwazChitra',
    'AwazPehchano',
    'Barakhadi',
    'Coloring',
    'CountAndKnow',
    'CountIt',
    'CrumbleTumble',
    'De dana dan',
    'Dhoom_1',
    'Dhoom_2',
    'fixUpMixUp',
    'FlipIt',
    'GaltiMaafSudharo',
    'GuessWho',
    'JaanoNumber',
    'Kahaniyaan',
    'LetterBox',
    'LineLagao',
    'MujhePehchano',
    'Number123',
    'NumberKas',
    'UlatPalat',
    'Sangeet',
    'ShabdhChitra',
    'ThikThak',
    'UlatPalat',
]

def compute_games_by_language_csv():
    """
    Checks which game names exist in all the PraDigi languages
    Matching is performed based on language code suffix, e.g. _MR for Marathi.
    Returns list of all languages matched.
    """
    languages_matches = []
    languages_en = [PRADIGI_STRINGS[lang]['language_en'] for lang in PRADIGI_LANGUAGES]
    fieldnames = ['Name on gamerepo'] + languages_en
    
    with open('games_by_language_matrix.csv', 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for game_name in TEST_GAMENAMES:
            row_dict = {}
            row_dict['Name on gamerepo'] = game_name
            for lang in PRADIGI_LANGUAGES:
                games = find_games_for_lang(game_name, lang)
                if games:
                    value = ' and '.join([game['title'] for game in games])
                    languages_matches.extend(games)
                else:
                    value = "N/A"
                languages_en = PRADIGI_STRINGS[lang]['language_en']
                row_dict[languages_en] = value
            writer.writerow(row_dict)
    return languages_matches

def getlang_by_language_en(language_en):
    if language_en == 'Odiya':
        language_en = 'Oriya'
    elif language_en == 'Bangali':
        language_en = 'Bengali'
    lang_obj = getlang_by_name(language_en)
    return lang_obj


def find_undocumented_games():
    # all games
    data = json.load(open('chefdata/trees/pradigi_games_all_langs.json','r'))
    gamelist = flatten_tree(data)
    all_set = set([game['url'] for game in gamelist])
    
    # the ones in TEST_GAMENAMES
    found_gamelist = compute_games_by_language_csv()
    found_set = set([game['url'] for game in found_gamelist])
    
    diff_set = all_set.difference(found_set)
    diff_gamelist = []
    for diff_url in diff_set:
        for game in gamelist:
            if game['url'] == diff_url:
                diff_gamelist.append(game)
    
    sorted_by_lang = sorted(diff_gamelist, key=lambda s:s['title'])
    for game in sorted_by_lang:
        print(game['title']+'\t'+game['language_en']+'\t'+game['url'])
    
    diff_game_names = set()
    for game in sorted_by_lang:
        title = game['title']
        if '_' in title:
            root = '_'.join(title.split('_')[0:-1])
        else:
            root = title
        diff_game_names.add(root)
    for name in sorted(diff_game_names):
        print(name)
            
    













class PrathamGamesRepoCrawler(BasicCrawler):
    """
    Get links fro all games from http://www.gamerepo.prathamcms.org/index.html
    """
    MAIN_SOURCE_DOMAIN = 'http://www.gamerepo.prathamcms.org'
    CRAWLING_STAGE_OUTPUT = 'chefdata/trees/pradigi_games_all_langs.json'
    START_PAGE_CONTEXT = {'kind': 'index_page'}
    kind_handlers = {
        'index_page': 'on_index_page',
        'gameslang_page': 'on_gameslang_page',
    }

    def on_index_page(self, url, page, context):
        LOGGER.info('in on_index_page ' + url)
        page_dict = dict(
            kind='index_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)
        
        languagelist_divs = page.find_all('div', attrs={'ng-repeat': "lang in languagelist"})
        for languagelist_div in languagelist_divs:
            link = languagelist_div.find('a')
            language_en = get_text(link)
            language_url = urljoin(url, link['href'])
            context = dict(
                parent=page_dict,
                kind='gameslang_page',
                language_en=language_en,
            )
            self.enqueue_url_and_context(language_url, context)

    def on_gameslang_page(self, url, page, context):
        LOGGER.info('in on_gameslang_page ' + url)
        page_dict = dict(
            kind='gameslang_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)
        
        gamelist = page.find_all('div', attrs={'ng-repeat':"gamedata in gamelist|filter:gametitle|filter:gamedata.gameurl.length"})
        for game in gamelist:
            title = get_text(game.find('h3'))
            last_modified = get_text(game.find('h6')).replace('Last modified : ', '')
            links = game.find_all('a')
            game_link, zipfile_link = links[0], links[1]
            main_file = urljoin(url, game_link['href'])
            zipfile_url = urljoin(url, zipfile_link['href'])

            # Handle special case of broken links (no title, and not main file)
            if len(title) == 0:
                zip_path = urlparse(zipfile_url).path
                zip_filename = os.path.basename(zip_path)
                title, _ = os.path.splitext(zip_filename)
                main_file = None

            game_dict = dict(
                url=zipfile_url,
                kind='PradigiGameZipResource',
                title=title,
                last_modified=last_modified,
                main_file=main_file,
                language_en=context['language_en'],
                children=[],
            )
            page_dict['children'].append(game_dict)


    def download_page(self, url, *args, **kwargs):
        """
        Download `url` using a JS-enabled web client.
        """
        LOGGER.info('Downloading ' +  url + ' then pausing for 15 secs for JS to run.')
        html = downloader.read(url, loadjs=True, loadjs_wait_time=3)
        page = BeautifulSoup(html, "html.parser")
        LOGGER.debug('Downloaded page ' + str(url) + ' using PhantomJS. Title:' + self.get_title(page))
        return (url, page)
























class PraDigiCrawler(BasicCrawler):
    MAIN_SOURCE_DOMAIN = FULL_DOMAIN_URL
    START_PAGE_CONTEXT = {'kind': 'lang_page'}
    kind_handlers = {
        'lang_page': 'on_lang_page',
        'topic_page': 'on_topic_page',
        'subtopic_page': 'on_subtopic_page',
        'lesson_page': 'on_lesson_page',
        'fun_page': 'on_fun_page',
        'fun_resource_page': 'on_fun_resource_page',
        'story_page': 'on_story_page',
        'story_resource_page': 'on_story_resource_page',
    }



    # CRALWING
    ############################################################################

    def __init__(self, lang=None, **kwargs):
        """
        Extend base class constructor to handle two-letter language code `lang`.
        """
        if lang is None:
            raise ValueError('Must specify `lang` argument for PraDigiCrawler.')
        if lang not in PRADIGI_LANGUAGES:
            raise ValueError('Bad lang. Use one of ' + str(PRADIGI_LANGUAGES))
        self.lang = lang
        start_page = PRADIGI_LANG_URL_MAP[self.lang]
        self.CRAWLING_STAGE_OUTPUT = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
        super().__init__(start_page=start_page)


    def crawl(self, **kwargs):
        """
        Extend base crawl method to add PraDigi channel metadata. 
        """
        web_resource_tree = super().crawl(**kwargs)

        # channel metadata
        lang_obj = getlang(self.lang)
        channel_metadata = dict(
            title='PraDigi ({})'.format(lang_obj.native_name),
            description = 'PraDigi video lessons and games.',  # TODO(ivan): what should be the longer descitpiton?
            source_domain = DOMAIN,
            source_id='pratham-open-school-{}'.format(self.lang),
            language=self.lang,
            thumbnail=None, # get_absolute_path('img/logop.png'),
        )
        web_resource_tree.update(channel_metadata)

        # convert tree format expected by scraping functions
        # restructure_web_resource_tree(web_resource_tree)
        # remove_sections(web_resource_tree)
        self.write_web_resource_tree_json(web_resource_tree)
        return web_resource_tree



    

    # HANDLERS
    ############################################################################

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
                
                # metadata
                topic_url = urljoin(url, topic['href'])
                title = topic.get_text().strip()
                source_id = get_source_id(topic['href'])
                subject_en = source_id    # short string to match on top-level categories
                context = dict(
                    parent=page_dict,
                    title=title,
                    source_id=source_id,
                    subject_en=subject_en,
                )
                
                # what type of tab is it?
                if 'Fun' in topic['href']:
                    LOGGER.info('found fun page: %s: %s' % (source_id, title))
                    context['kind'] = 'fun_page'
                elif 'Story' in topic['href']:
                    LOGGER.info('found story page: %s: %s' % (source_id, title))
                    context['kind'] = 'story_page'
                else:
                    LOGGER.info('found topic: %s: %s' % (source_id, title))
                    context['kind'] = 'topic_page'
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
                    children=[],
                )
                self.enqueue_url_and_context(subtopic_url, context)
            except Exception as e:
                LOGGER.error('on_topic_page: %s : %s' % (e, subtopic))


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
                caption = lesson.find('div', class_='caption')
                description = lesson.get_text().strip() if lesson else ''
                lesson_url = urljoin(url, lesson.find('a')['href'])
                thumbnail_src = lesson.find('a').find('img')['src']
                thumbnail_url = urljoin(url, thumbnail_src)
                source_id = get_source_id(lesson.find('a')['href'])
                LOGGER.info('     lesson: %s: %s' % (source_id, title))
                context = dict(
                    parent=page_dict,
                    kind='lesson_page',
                    title=title,
                    description=description,
                    source_id=source_id,
                    thumbnail_url=thumbnail_url,
                    children=[],
                )
                self.enqueue_url_and_context(lesson_url, context)
                # get_contents(node, link)
            except Exception as e:
                LOGGER.error('on_subtopic_page: %s : %s' % (e, lesson))


    # LESSONS
    ############################################################################

    def on_lesson_page(self, url, page, context):
        print('      in on_lesson_page', url)
        page_dict = dict(
            kind='lessons_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'row-exu'})
        except Exception as e:
            LOGGER.error('on_lesson_page: %s : %s' % (e, page))
            return

        contents = menu_row.find_all('div', {'class': 'col-md-3'})
        for content in contents:
            try:
                title = content.find('div', {'class': 'txtline'}).get_text()
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)
                main_file, master_file, source_id = get_content_link(content)
                LOGGER.info('      content: %s: %s' % (source_id, title))

                if main_file.endswith('mp4'):
                    video = dict(
                        url=main_file,
                        kind='PrathamVideoResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(video)

                elif main_file.endswith('pdf'):
                    pdf = dict(
                        url=main_file,
                        kind='PrathamPdfResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(pdf)

                elif main_file.endswith('html') and master_file.endswith('zip'):
                    zipfile = dict(
                        url=master_file,
                        kind='PrathamZipResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        main_file=main_file,     # needed to rename to index.html if different
                        children=[],
                    )
                    page_dict['children'].append(zipfile)

                else:
                    LOGGER.error('Content not supported: %s, %s' % (main_file, master_file))
            except Exception as e:
                LOGGER.error('zz _process_contents: %s : %s' % (e, content))



    # FUN PAGES
    ############################################################################
    
    def on_fun_page(self, url, page, context):
        print('     in on_fun_page', url)
        page_dict = dict(
            kind='fun_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            contents_row = body_row.find('div', {'class': 'row'})
        except Exception as e:
            LOGGER.error('on_fun_page: %s : %s' % (e, page))
            return
        contents = contents_row.find_all('div', {'class': 'col-md-3'})

        for content in contents:
            try:
                title = get_text(content.find('div', {'class': 'txtline'}))
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)

                # get_fun_content_link
                link = content.find('a')
                source_id = link['href'][1:]
                fun_resource_url = get_absolute_path(link['href'])
                download_href = content.find('a', class_='dnlinkfunstory')['href']
                download_url = get_absolute_path(download_href)

                LOGGER.info('      content: %s: %s' % (source_id, title))

                if download_url.endswith('mp4'):
                    video = dict(
                        url=download_url,
                        kind='PrathamVideoResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(video)

                elif download_url.endswith('pdf'):
                    pdf = dict(
                        url=download_url,
                        kind='PrathamPdfResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(pdf)

                elif download_url.endswith('zip'):
                    # Need to go get the actual page since main_file is not in avail. in list
                    html = requests.get(fun_resource_url).content.decode('utf-8')
                    respath_url = get_respath_url_from_html(html)
                    zipfile = dict(
                        url=download_url,
                        kind='PrathamZipResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        main_file=respath_url,   # needed to rename to index.html if different
                        children=[],
                    )
                    page_dict['children'].append(zipfile)

                else:
                    LOGGER.error('Fun resource not supported: %s, %s' % (fun_resource_url, download_url))

            except Exception as e:
                LOGGER.error('on_fun_page: %s : %s' % (e, content))

    def on_story_resource_page(self, url, page, context):
        print('     in on_story_resource_page', url)
        RESOURCE_PATH_PATTERN = re.compile('var respath = "(?P<resource_path>.*?)";')
        html= str(page)
        m = RESOURCE_PATH_PATTERN.search(html)
        if m is None:
            LOGGER.error('Failed to find story_resource_url on page %s' % url)
        story_resource_url = get_absolute_path('/' + m.groupdict()['resource_path'])
        page_dict = dict(
            url=story_resource_url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)



    # STORIES
    ############################################################################

    def on_story_page(self, url, page, context):
        print('     in on_story_page', url)
        page_dict = dict(
            kind='story_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            contents_row = body_row.find('div', {'class': 'row'})
        except Exception as e:
            LOGGER.error('on_story_page: %s : %s' % (e, page))
            return
        contents = contents_row.find_all('div', {'class': 'col-md-3'})

        for content in contents:
            try:
                title = get_text(content.find('div', {'class': 'txtline'}))
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)

                # get_fun_content_link
                link = content.find('a')
                source_id = link['href'][1:]
                story_resource_url = get_absolute_path(link['href'])
                LOGGER.info('      story_resource_page: %s: %s' % (source_id, title))
                context = dict(
                    parent = page_dict,
                    kind='story_resource_page',
                    title=title,
                    source_id=source_id,
                    thumbnail_url=thumbnail,
                )
                self.enqueue_url_and_context(story_resource_url, context)

            except Exception as e:
                LOGGER.error('on_story_page: %s : %s' % (e, content))

    def on_story_resource_page(self, url, page, context):
        print('     in on_story_resource_page', url)
        html = str(page)
        story_resource_url = get_respath_url_from_html(html)
        if story_resource_url:
            page_dict = dict(
                url=story_resource_url,
                children=[],
            )
            page_dict.update(context)
            context['parent']['children'].append(page_dict)
        else:
            LOGGER.error('Failed to find story_resource_url on page %s' % url)


# Helper functions
################################################################################
def get_absolute_path(path):
    return urljoin('http://www.' + DOMAIN, path)


_RESOURCE_PATH_PATTERN = re.compile('var respath = "(?P<resource_path>.*?)";')
def get_respath_url_from_html(html):
    m = _RESOURCE_PATH_PATTERN.search(html)
    if m is None:
        return None
    respath_url =  get_absolute_path('/' + m.groupdict()['resource_path'])
    return respath_url



def make_request(url):
    response = session.get(url)
    if response.status_code != 200:
        LOGGER.error("NOT FOUND: %s" % (url))
    return response


def get_page(path):
    url = get_absolute_path(path)
    resp = make_request(url)
    return BeautifulSoup(resp.content, 'html.parser')

def get_text(element):
    """
    Extract text contents of `element`, normalizing newlines to spaces and stripping.
    """
    if element is None:
        return ''
    else:
        return element.get_text().replace('\r', '').replace('\n', ' ').strip()

def get_source_id(path):
    return path.strip('/').split('/')[-1]


def get_content_link(content):
    """
    The link to a content has an onclick attribute that executes
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




def get_fun_content_link(content):
    """
    Same as the above but works for resources on the Fun page.
    """



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
            source_id='pradigi-videos-and-games',
            thumbnail=None, # get_absolute_path('img/logop.png'),
            language='en', # language
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

