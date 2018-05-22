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
      (not used, instead use games form http://repository.prathamopenschool.org)
"""

import copy
import csv
from itertools import groupby
import json
import logging
from operator import itemgetter
import os
import re
import requests
import shutil
import tempfile
import zipfile
from urllib.parse import urlparse


from le_utils.constants import content_kinds, file_types, licenses
from le_utils.constants.languages import getlang, getlang_by_name
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils.caching import (CacheForeverHeuristic, FileCache, CacheControlAdapter)
from ricecooker.utils.jsontrees import write_tree_to_json_tree
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip



DOMAIN = 'prathamopenschool.org'
FULL_DOMAIN_URL = 'http://www.' + DOMAIN
PRADIGI_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='PraDigi').as_dict()
PRADIGI_LANGUAGES = ['hi', 'en', 'or', 'bn', 'pnb', 'kn', 'ta', 'te', 'mr', 'gu', 'as']
PRADIGI_WEBSITE_LANGUAGES = ['hi', 'mr']


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


# SOURCE WEBSITES
################################################################################
PRADIGI_LANG_URL_MAP = {
    'hi': 'http://www.prathamopenschool.org/hn/',
    'mr': 'http://www.prathamopenschool.org/mr/',
}
GAMEREPO_MAIN_SOURCE_DOMAIN = 'http://repository.prathamopenschool.org'
GAME_THUMBS_REMOTE_DIR = 'http://www.prodigi.openiscool.org/repository/Images/'
GAME_THUMBS_LOCAL_DIR = 'chefdata/gamethumbnails'

# LOCALIZATION AND TRANSLATION STRINGS
################################################################################

PRADIGI_STRINGS = {
    'hi': {
        'language_en': 'Hindi',
        'gamesrepo_suffixes': ['_KKS', '_HI'],
        'subjects': {
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
        'subjects': {
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
        "subjects": {}
    },
    "bn": {
        "language_en": "Bangali",
        "gamesrepo_suffixes": ['_BN'],
        "subjects": {}
    },
    "pnb": {
        "language_en": "Punjabi",
        "gamesrepo_suffixes": ['_PN'],
        "subjects": {}
    },
    "kn": {
        "language_en": "Kannada",
        "gamesrepo_suffixes": ['_KN'],
        "subjects": {}
    },
    "ta": {
        "language_en": "Tamil",
        "gamesrepo_suffixes": ['_TM'],
        "subjects": {}
    },
    "te": {
        "language_en": "Telugu",
        "gamesrepo_suffixes": ['_TL'],
        "subjects": {}
    },
    "mr": {
        "language_en": "Marathi",
        "gamesrepo_suffixes": ['_MR'],
        "subjects": {}
    },
    "gu": {
        "language_en": "Gujarati",
        "gamesrepo_suffixes": ['_KKS', '_GJ'],
        "subjects": {}
    },
    "as": {
        "language_en": "Assamese",
        "gamesrepo_suffixes": ['_AS'],
        "subjects": {}
    },
}

# lookup helper function, e.g. English --> en
LANGUAGE_EN_TO_LANG = {}
for lang, lang_data in PRADIGI_STRINGS.items():
    language_en = lang_data['language_en']
    LANGUAGE_EN_TO_LANG[language_en] = lang







# STRUCTURE = CSV EXPORT of the Google Sheet titled "Kolibri- Content structure"
################################################################################
GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
PRADIGI_SHEET_ID = '1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg'
PRADIGI_STRUCTURE_SHEET_GID = '342105160'
PRADIGI_SHEET_CSV_URL = GSHEETS_BASE + PRADIGI_SHEET_ID + '/export?format=csv&gid=' + PRADIGI_STRUCTURE_SHEET_GID
PRADIGI_SHEET_CSV_PATH = 'chefdata/pradigi_structure.csv'
AGE_GROUP_KEY = 'Age Group'
SUBJECT_KEY = 'Subject'
RESOURCE_TYPE_KEY = 'Resource Type'
NAME_KEY = 'Name'
CODENAME_KEY = 'Name on gamerepo (before lang underscore)'
TAKE_FROM_KEY = 'Take From Repo'
PRATHAM_COMMENTS_KEY = 'Pratham'
LE_COMMENTS_KEY = 'LE Comments'
PRADIGI_AGE_GROUPS = ['3-6 years', '6-10 years', '8-14 years', '14 and above']
PRADIGI_SUBJECTS = ['Mathematics', 'Language', 'English', 'Fun', 'Science',
                    'Health', 'Std5', 'Std6', 'Std7', 'Std8', 'Std9', 'Std10', 'Story',
                    'Automobile', 'Beauty', 'Construction', 'Electric', 'Healthcare', 'Hospitality']
PRADIGI_RESOURCE_TYPES = ['Game', 'Video Resources', 'All Resources']  # English- Hindi?
# TODO(ivan): add 'Interactive Resoruces' and 'Book Resources' as separate resoruce type categories
PRADIGI_SHEET_CSV_FILEDNAMES = [
    AGE_GROUP_KEY,
    SUBJECT_KEY,
    RESOURCE_TYPE_KEY,
    NAME_KEY,
    CODENAME_KEY,
    TAKE_FROM_KEY,
    PRATHAM_COMMENTS_KEY,
    LE_COMMENTS_KEY,
]

def download_structure_csv():
    response = requests.get(PRADIGI_SHEET_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(PRADIGI_SHEET_CSV_PATH, 'w') as csvfile:
        csvfile.write(csv_data)
        LOGGER.info('Succesfully saved ' + PRADIGI_SHEET_CSV_PATH)

def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val.strip()
    return row_cleaned

def load_pradigi_structure():
    download_structure_csv()
    struct_list = []
    with open(PRADIGI_SHEET_CSV_PATH, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=PRADIGI_SHEET_CSV_FILEDNAMES)
        next(reader)  # Skip Headers row
        next(reader)  # Skip info line
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[SUBJECT_KEY] is None:
                continue  # skip blank lines (identified by missing subject col)
            if clean_row[AGE_GROUP_KEY] in PRADIGI_AGE_GROUPS and clean_row[SUBJECT_KEY] in PRADIGI_SUBJECTS:
                struct_list.append(clean_row)
            else:
                print('Unrecognized structure row', clean_row)
    return struct_list

PRADIGI_STRUCT_LIST = load_pradigi_structure()


def get_tree_for_lang_from_structure():
    """
    Build the template structure for language-subtree based on structure in CSV.
    """
    struct_list = PRADIGI_STRUCT_LIST
    struct_list = sorted(struct_list, key=itemgetter(AGE_GROUP_KEY, SUBJECT_KEY))
    lang_tree = dict(
        kind=content_kinds.TOPIC,
        children=[],
    )
    age_groups_dict = dict((k, list(g)) for k, g in groupby(struct_list, key=itemgetter(AGE_GROUP_KEY)))
    for age_group_title in PRADIGI_AGE_GROUPS:
        age_groups_subtree = dict(
            title=age_group_title,
            kind=content_kinds.TOPIC,
            children=[],
        )
        lang_tree['children'].append(age_groups_subtree)
        items_in_age_group = list(age_groups_dict[age_group_title])
        subjects_dict = dict((k, list(g)) for k, g in groupby(items_in_age_group, key=itemgetter(SUBJECT_KEY)))
        for subject_en in PRADIGI_SUBJECTS:
            if subject_en in subjects_dict:
                subject_subtree = dict(
                    title=subject_en,
                    kind=content_kinds.TOPIC,
                    children=[],
                )
                age_groups_subtree['children'].append(subject_subtree)
    # print('lang_tree=', lang_tree, flush=True)
    return lang_tree

def get_resources_for_age_group_and_subject(age_group, subject_en):
    """
    Select the rows from the PraDigi structure CSV with matching age_group and subject_en.
    Returns a dictionary:
    { 
        'videos': [subject_en, ...],  # Include all videos from /subject_en on website
        'games': [{game struct row}, {anothe game row}, ...]   # Include localized verison of games in this list
    }
    """
    # print('in get_resources_for_age_group_and_subject with', age_group, subject_en, flush=True)
    struct_list = PRADIGI_STRUCT_LIST
    videos = []
    games = []
    for row in struct_list: # self.struct_list:
        if row[AGE_GROUP_KEY] == age_group and row[SUBJECT_KEY] == subject_en:
            if row[RESOURCE_TYPE_KEY] == 'Game':
                games.append(row)
            elif row[RESOURCE_TYPE_KEY] == 'Video Resources':
                videos.append(subject_en)
            else:
                print('Unknown resource type', row[RESOURCE_TYPE_KEY], 'in row', row)
    # print('games=', games, flush=True)
    return {'videos':videos, 'games':games}


TEMPLATE_FOR_LANG = get_tree_for_lang_from_structure()
# 
# TEMPLATE_FOR_LANG = {
#     'kind': content_kinds.TOPIC,
#     'children': [
#         {   'title': '3-6 years',
#             'children': [
#                 {'title': 'Language',       'children': []},
#                 {'title': 'Mathematics',    'children': []},
#                 {'title': 'Story',          'children': []},  # should include here?
#                 {'title': 'Fun',            'children': []},
#             ],
#         },
#         {   'title': '6-10 years',
#             'children': [
#                 {'title': 'Mathematics',    'children': []},
#                 {'title': 'Language',       'children': []},
#                 {'title': 'English',        'children': []},
#                 {'title': 'Story',          'children': []},
#                 {'title': 'Fun',            'children': []},
#             ],
#         },
#         {   'title': '8-14 years',
#             'children': [
#                 {'title': 'Mathematics',    'children': []},
#                 {'title': 'Language',       'children': []},
#                 {'title': 'English',        'children': []},
#                 {'title': 'Health',         'children': []},
#                 {'title': 'Science',        'children': []},
#                 {'title': 'Std5',           'children': []},
#                 {'title': 'Std6',           'children': []},
#                 {'title': 'Std7',           'children': []},
#                 {'title': 'Std8',           'children': []},
#                 {'title': 'Fun',            'children': []},
#             ],
#         },
#         {   'title': '14 and above',
#             'children': [
#                 {'title': 'English',        'children': []},
#                 {'title': 'Std9',           'children': []},
#                 {'title': 'Std10',          'children': []},
#                 {'title': 'Automobile',     'children': []},
#                 {'title': 'Beauty',         'children': []}, 
#                 {'title': 'Construction',   'children': []},
#                 {'title': 'Healthcare',     'children': []},
#                 {'title': 'Hospitality',    'children': []},
#                 {'title': 'Electric',       'children': []},
#                 {'title': 'Fun',            'children': []},
#             ],
#         },
#     ]
# }





# GAMESREPO UTILS
################################################################################

def find_games_for_lang(name, lang, take_from=None):
    data = json.load(open('chefdata/trees/pradigi_games_all_langs.json','r'))
    language_en = PRADIGI_STRINGS[lang]['language_en']
    suffixes = PRADIGI_STRINGS[lang]['gamesrepo_suffixes']
    assert data["kind"] == "index_page", 'wrong web resource tree loaded'
    games = []
    # Get game from pradigi_games json by ignoring _LANG suffixes
    for gameslang_page in data['children']:
        if gameslang_page['language_en'] == language_en:
            for game in gameslang_page['children']:
                title = game['title']
                for suffix in suffixes:
                    if title.strip().endswith(suffix):
                        title = title.replace(suffix, '').strip()
                if name == title:
                    games.append(game)
    # Extra pass to get English games to be included in other languages
    if len(games) == 0 and take_from is not None:
        take_lang = LANGUAGE_EN_TO_LANG[take_from]
        take_suffixes = PRADIGI_STRINGS[take_lang]['gamesrepo_suffixes']
        for gameslang_page in data['children']:
            if gameslang_page['language_en'] == take_from:
                for game in gameslang_page['children']:
                    title = game['title']
                    for suffix in take_suffixes:
                        if title.strip().endswith(suffix):
                            title = title.replace(suffix, '').strip()
                    if name == title:
                        games.append(game)
    return games






# ZIP FILE TRANFORMS AND FIXUPS
################################################################################

def make_request(url):
    response = session.get(url)
    if response.status_code != 200:
        LOGGER.error("NOT FOUND: %s" % (url))
    return response

def get_zip_file(zip_file_url, main_file):
    """
    HTML games are provided as zip files, the entry point of the game is `main_file`.
    THe `main_file` needs to be renamed to index.html to make it compatible with Kolibri.
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



PHET_INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
</head>
<body>
  <div><p>Redirecting to phet simulation {sim_id} now...</p></div>
</body>
<script type="text/javascript">
    window.location.href = "phetindex.html?id={sim_id}";
</script>
</html>
"""


def get_phet_zip_file(zip_file_url, main_file_and_query):
    """
    Phet simulations are provided in the zip file `phet.zip`, and the entry point
    is passed as a GET parameter in `main_file_and_query`. To make these compatible
    with Kolibri's default behaviour of loading index.html, we will:
      - Rename index.html to phetindex.thml
      - Add a custom index.html that uses javascrpt redirect to phetindex.thml?{sim_id}
    """
    u = urlparse(main_file_and_query)
    idk, sim_id = u.query.split('=')
    assert idk == 'id', 'unknown query sting format found' + main_file_and_query
    main_file = u.scheme + '://' + u.netloc + u.path  # skip querystring
    
    destpath = tempfile.mkdtemp()
    LOGGER.info('saving phet zip file in dir ' + destpath)
    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]
        zip_basename = zip_filename.rsplit('.', 1)[0]
        zip_folder = os.path.join(destpath, zip_basename)

        # Extract zip file contents.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            zf.extractall(destpath)

        # Rename main_file to phetindex.html.
        main_file = main_file.split('/')[-1]
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'phetindex.html')
        os.rename(src, dest)
        
        # Create the 
        index_html = PHET_INDEX_HTML_TEMPLATE.format(sim_id=sim_id)
        with open(os.path.join(zip_folder, 'index.html'), 'w') as indexf:
            indexf.write(index_html)
        
        # Always be zipping!
        return create_predictable_zip(zip_folder)

    except Exception as e:
        # LOGGER.error
        print("get_phet_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file_and_query, destpath, e))
        return None



# RICECOOKER JSON TRANSFORMATIONS
################################################################################

def get_subtree_by_subject_en(lang, subject, topic=None):
    if lang not in ['mr', 'hi']:
        raise ValueError('Language `lang` must mr or hi (only two langs on website)')
    wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
    with open(wrt_filename) as jsonfile:
        web_resource_tree = json.load(jsonfile)
    subject_subtrees = web_resource_tree['children']
    for subject_subtree in subject_subtrees:
        if subject_subtree['subject_en'] == subject:
            return subject_subtree
    return None


def _only_videos(node):
    """
    Set this as the `filter_fn` to `wrt_to_ricecooker_tree` to select only videos.
    """
    allowed_kinds = ['lang_page', 'topic_page', 'subtopic_page', 'lesson_page', 'fun_page', 'story_page',
                     'PrathamVideoResource']
    return node['kind'] in allowed_kinds


def wrt_to_ricecooker_tree(tree, lang, filter_fn=lambda node: True):
    """
    Transforms web resource subtree `tree` into a riccecooker tree of topics nodes,
    and content nodes, using `filter_fn` to determine if each node should be included or not.
    """
    kind = tree['kind']
    if kind in ['topic_page', 'subtopic_page', 'lesson_page', 'fun_page', 'story_page']:
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        topic_node = dict(
            kind=content_kinds.TOPIC,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],  # or could get from Strings based on subject_en...
            description='',
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            children=[],
        )
        for child in tree['children']:
            if filter_fn(child):
                try:
                    ricocooker_node = wrt_to_ricecooker_tree(child, lang, filter_fn=filter_fn)
                    topic_node['children'].append(ricocooker_node)
                except Exception as e:
                    LOGGER.error("Failed to generate node for %s in %s %s " % (child['title'], lang, e) )
                    pass
        return topic_node

    elif kind == 'PrathamVideoResource':
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        video_node = dict(
            kind=content_kinds.VIDEO,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],
            description=tree.get('description', ''),
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            files=[],
        )
        video_file = dict(
            file_type=file_types.VIDEO,
            path=tree['url'],
            language=lang,
        )
        if should_compress_video(tree):
            video_file['ffmpeg_settings'] = {"crf": 28}   # average quality
        video_node['files'].append(video_file)
        return video_node

    elif kind == 'PrathamZipResource':
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        html5_node = dict(
            kind=content_kinds.HTML5,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],
            description=tree.get('description', ''),
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            files=[],
        )
        if 'phet.zip' in tree['url']:
            zip_tmp_path  = get_phet_zip_file(tree['url'], tree['main_file'])
        else:
            zip_tmp_path  = get_zip_file(tree['url'], tree['main_file'])
        if zip_tmp_path is None:
            raise ValueError('Could not get zip file from %s' % tree['url'])
        html5zip_file = dict(
            file_type=file_types.HTML5,
            path=zip_tmp_path,
            language=lang,
        )
        html5_node['files'].append(html5zip_file)
        return html5_node

    elif kind == 'PrathamPdfResource' or kind == 'story_resource_page':
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        pdf_node = dict(
            kind=content_kinds.DOCUMENT,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],
            description=tree.get('description', ''),
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            files=[],
        )
        pdf_file = dict(
            file_type=file_types.DOCUMENT,
            path=tree['url'],
            language=lang,
        )
        pdf_node['files'].append(pdf_file)
        return pdf_node

    else:
        raise ValueError('Uknown web resource kind ' + kind + ' encountered.')


def should_compress_video(video_web_resource):
    """
    Web-optimized videos do not need to be re-encoded and compressed: it's better
    to upload to Studio the original files. We compress large vidoes (> 30MB) in
    order to limit storage and transfers needs.
    """
    size_bytes = video_web_resource['content-length']
    size_mb = int(size_bytes)/1024/1024
    if size_mb > 30:
        return True
    else:
        return False



# GAME REPO JSON to RICECOOKER JSON
################################################################################

def game_info_to_ricecooker_node(lang, title, game_info):
    """
    Create Ricecooker Json structure for game with human-readable title `title`
    and gamesrepo info in `game_info`.
    """
    game_node = dict(
        kind=content_kinds.HTML5,
        source_id=game_info['title'],
        language=lang,
        title=title,
        description='',
        license=PRADIGI_LICENSE,
        thumbnail=game_info.get('thumbnail_url'),
        files=[],
    )
    zip_file = dict(
        file_type=file_types.HTML5,
        path=game_info['url'],
        language=lang,
    )
    game_node['files'].append(zip_file)
    LOGGER.debug('Created HTML5AppNode for game ' + game_info['title'])
    return game_node





# CHEF
################################################################################

class PraDigiChef(JsonTreeChef):
    """
    SushiChef script for importing and merging the content from these two sites:
      - Videos from http://www.prathamopenschool.org/
      - Games from http://repository.prathamopenschool.org
    """
    RICECOOKER_JSON_TREE = 'pradigi_ricecooker_json_tree.json'
    
    
    def crawl(self, args, options):
        """
        Crawl website and gamerepo. Save web resource trees in chefdata/trees/.
        """
        from pradigi_crawlers import PraDigiCrawler, PrathamGameRepoCrawler
        
        # website
        for lang in ['hi', 'mr']:
            website_crawler = PraDigiCrawler(lang=lang)
            wrt = website_crawler.crawl()

        # gamerepo
        gamerepo_start_page = GAMEREPO_MAIN_SOURCE_DOMAIN
        gamerepo_crawler = PrathamGameRepoCrawler(start_page=gamerepo_start_page)
        gamerepo_crawler.crawl()



    def build_subtree_for_lang(self, lang):
        print('Building subtree for lang', lang)
        
        lang_subtree = copy.deepcopy(TEMPLATE_FOR_LANG)
        lang_obj = getlang(lang)
        first_native_name = lang_obj.native_name.split(',')[0].split('(')[0]
        lang_subtree['title'] = first_native_name
        lang_subtree['language'] = lang
        lang_subtree['source_id'] = 'pradigi_'+str(lang)

        # Go through template age groups and subjects
        age_groups_subtrees = lang_subtree['children']
        for age_groups_subtree in age_groups_subtrees:
            age_group = age_groups_subtree['title']
            age_groups_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group
            subject_subtrees = age_groups_subtree['children']
            for subject_subtree in subject_subtrees:
                subject_en = subject_subtree['title']
                subject_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group+'_'+subject_en
                
                # localize subject titles when translation is available
                if subject_en in PRADIGI_STRINGS[lang]['subjects']:
                    subject_subtree['title'] = PRADIGI_STRINGS[lang]['subjects'][subject_en]
                
                # MAIN LOOKUP FUNCTION -- GETS INFOR FORM CSV
                resources = get_resources_for_age_group_and_subject(age_group, subject_en)
                print('In main loop', lang, age_group, subject_en)
                
                # A. Load video resources
                if lang in PRADIGI_WEBSITE_LANGUAGES:
                    for desired_subject_en in resources['videos']:
                        wrt_subtree = get_subtree_by_subject_en(lang, desired_subject_en)
                        if wrt_subtree:
                            # print('wrt_subtree=', wrt_subtree)
                            # ricecooker_subtree = wrt_to_ricecooker_tree(wrt_subtree, lang, filter_fn=_only_videos)
                            # Apr 23, get all resources and not just videos
                            ricecooker_subtree = wrt_to_ricecooker_tree(wrt_subtree, lang)
                            # print('ricecooker_subtree=', ricecooker_subtree)
                            for ch in ricecooker_subtree['children']:
                                subject_subtree['children'].append(ch)

                # B. Load game resources
                game_rows = resources['games']
                for game_row in game_rows:
                    game_title = game_row[NAME_KEY]
                    game_name = game_row[CODENAME_KEY]
                    take_from = game_row[TAKE_FROM_KEY]
                    games = find_games_for_lang(game_name, lang, take_from=take_from)
                    # print('Processing games', games, 'under game_title', game_title, 'for lang', lang, 'found take_from=', take_from, flush=True)
                    for game in games:
                        node = game_info_to_ricecooker_node(lang, game_title, game)
                        subject_subtree['children'].append(node)
            
            # Remove empty subject_tree topic nodes
            nonempty_subject_subtrees = []
            for subject_subtree in subject_subtrees:
                if len(subject_subtree['children']) == 0:
                    pass
                else:
                    nonempty_subject_subtrees.append(subject_subtree)
            age_groups_subtree['children'] = nonempty_subject_subtrees

        return lang_subtree


    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel
        """
        print('in pre_run...')

        if 'nocrawl' not in options:
            self.crawl(args, options)

        # this is used for lookups by `get_games_for_age_group_and_subject` so pre-load here
        self.struct_list = load_pradigi_structure()

        ricecooker_json_tree = dict(
            title='PraDigi',
            source_domain=DOMAIN,
            source_id='pradigi-videos-and-games',
            description='Combined PraDigi channel with all languages',
            thumbnail='https://learningequality.org/static/img/kickstarter/pratham-open-school.png',
            language='en',   # Using EN as top-level language because mixed content
            children=[],
        )
        for lang in PRADIGI_LANGUAGES:
            lang_subtree = self.build_subtree_for_lang(lang)
            ricecooker_json_tree['children'].append(lang_subtree)
        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


    def run(self, args, options):
        print('options=', options, flush=True)
        self.pre_run(args, options)
        if 'crawlonly' in options:
            print('Crawling done. Skipping rest of chef run since `crawlonly` is set.')
            return
        super(PraDigiChef, self).run(args, options)




# CLI
################################################################################

if __name__ == '__main__':
    pradigi_chef = PraDigiChef()
    pradigi_chef.main()











# STRUCTURE DIAGNOSE AND DEBUG TOOLS
################################################################################

def getlang_by_language_en(language_en):
    """
    Convert language names used on PraDigi websites to le_utils language object.
    """
    if language_en == 'Odiya' or language_en == 'Odisa':
        language_en = 'Oriya'
    elif language_en == 'Bangali':
        language_en = 'Bengali'
    elif language_en == 'Telagu':
        language_en = 'Telugu'
    lang_obj = getlang_by_name(language_en)
    return lang_obj

def get_all_game_names():
    """
    Used for debugging chef
    """
    game_names = []
    struct_list = load_pradigi_structure()
    for struct_row in struct_list:
        codename = struct_row[CODENAME_KEY]
        if codename is not None and codename not in game_names:
            game_names.append(struct_row[CODENAME_KEY])
    return game_names

def compute_games_by_language_csv(game_names):
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
        
        for game_name in game_names:
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


def flatten_tree(tree):
    if len(tree['children'])==0:
        return [tree]
    else:
        result = []
        for child in tree['children']:
            flat_child = flatten_tree(child)
            result.extend(flat_child)
        return result


def find_undocumented_games():
    # all games
    data = json.load(open('chefdata/trees/pradigi_games_all_langs.json','r'))
    gamelist = flatten_tree(data)
    all_set = set([game['url'] for game in gamelist])
    
    # the ones in TEST_GAMENAMES
    game_names = get_all_game_names()
    found_gamelist = compute_games_by_language_csv(game_names)
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
    
    # Print just names
    # diff_game_names = set()
    # for game in sorted_by_lang:
    #     title = game['title']
    #     if '_' in title:
    #         root = '_'.join(title.split('_')[0:-1])
    #     else:
    #         root = title
    #     diff_game_names.add(root)
    # for name in sorted(diff_game_names):
    #     print(name)



# WEBSITE DIAGNOSE AND DEBUG TOOLS
################################################################################


def find_large_video_files(tree, parent):
    if tree['kind'] == 'PrathamVideoResource':
        url_p = urlparse(tree['url'])
        filename = os.path.basename(url_p.path)
        if 'content-length' in tree:
            size_bytes = tree['content-length']
            size_mb = int(size_bytes)/1024/1024
            if size_mb > 100:
                print('Large video file' + '\t' + filename + '\t'+ tree['url'] + \
                    '\t' + parent['url'] + '\t' + 'File size is %.2fMB, so not good for web' % size_mb)
        else:
            print('404 video file' + '\t' + filename + '\t' + tree['url'] + '\t' + parent['url'])




def find_missing_zip_resources(tree, parent):
    if tree['kind'] == 'PrathamZipResource':
        url = tree['url']
        url_p = urlparse(url)
        filename = os.path.basename(url_p.path)
        
        resp = requests.head(url)
        if resp.status_code == 404:
            print('404 zip file' + '\t' + filename + '\t' + url + '\t' + parent['url'])



def walk_tree(tree, parent={'url':None}, el_fn=lambda x: x):
    el_fn(tree,parent)
    for child in tree['children']:
        walk_tree(child, parent=tree, el_fn=el_fn)


def find_problem_resources_files():
    for lang in ['hi', 'mr']:
        wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
        with open(wrt_filename) as jsonfile:
            web_resource_tree = json.load(jsonfile)
            # walk_tree(web_resource_tree, el_fn=find_large_video_files)
            walk_tree(web_resource_tree, el_fn=find_missing_zip_resources)
