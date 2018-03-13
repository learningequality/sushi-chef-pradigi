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

import copy
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








# CSV EXPORT AND PARSING for the Google Sheet: Kolibri- Content structure 
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
PRATHAM_COMMENTS_KEY = 'Pratham'
LE_COMMENTS_KEY = 'LE Comments'
PRADIGI_AGE_GROUPS = ['3-6 years', '6-10 years', '8-14 years', '14 and above']
PRADIGI_SUBJECTS = ['Math', 'Language', 'English', 'Fun', 'Science',
                    'Automotive', 'Beauty', 'Construction', 'Electrical', 'Healthcare', 'Hospitality']
PRADIGI_SHEET_CSV_FILEDNAMES = [
    AGE_GROUP_KEY,
    SUBJECT_KEY,
    RESOURCE_TYPE_KEY,
    NAME_KEY,
    CODENAME_KEY,
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
    games_info = []
    with open(PRADIGI_SHEET_CSV_PATH, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=PRADIGI_SHEET_CSV_FILEDNAMES)
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[AGE_GROUP_KEY] in PRADIGI_AGE_GROUPS and clean_row[SUBJECT_KEY] in PRADIGI_SUBJECTS:
                games_info.append(clean_row)
    return games_info


def get_all_game_names():
    """
    Used for debugging chef
    """
    game_names = []
    games_info = load_pradigi_structure()
    for game in games_info:
        codename = game[CODENAME_KEY]
        if codename is not None and codename not in game_names:
            game_names.append(game[CODENAME_KEY])
    return game_names


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
            "Automotive": "वाहन",      # alt spelling used in spreadsheet
            "Electric": "इलेक्ट्रिक",
            "Electrical": "इलेक्ट्रिक",   # alt spelling used in spreadsheet
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
        "gamesrepo_suffixes": ['_AS', 'AS_Assamese'],
        "subjects": {}
    },
}






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



TEMPLATE_FOR_LANG = {
    'kind': content_kinds.TOPIC,
    'children': [
        {   'title': '3-6 years',
            'children': [
                {'title': 'Language',       'children': []},
                {'title': 'Mathematics',    'children': []},
                {'title': 'Story',          'children': []},  # should include here?
                {'title': 'Fun',            'children': []},
            ],
        },
        {   'title': '6-10 years',
            'children': [
                {'title': 'Mathematics',    'children': []},
                {'title': 'Language',       'children': []},
                {'title': 'English',        'children': []},
                {'title': 'Story',          'children': []},
                {'title': 'Fun',            'children': []},
            ],
        },
        {   'title': '8-14 years',
            'children': [
                {'title': 'Mathematics',    'children': []},
                {'title': 'Language',       'children': []},
                {'title': 'English',        'children': []},
                {'title': 'Health',         'children': []},
                {'title': 'Science',        'children': []},
                {'title': 'Std8',           'children': []},
                {'title': 'Fun',            'children': []},
            ],
        },
        {   'title': '14 and above',
            'children': [
                {'title': 'English',        'children': []},
                {'title': 'Beauty',         'children': []}, 
                {'title': 'Automotive',     'children': []},
                {'title': 'Healthcare',     'children': []},
                {'title': 'Construction',   'children': []},
                {'title': 'Hospitality',    'children': []},
                {'title': 'Electrical',     'children': []},
                {'title': 'Fun',            'children': []},
            ],
        },
    ]
}








# GAMESREPO UTILS
################################################################################

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


def getlang_by_language_en(language_en):
    """
    Convert language names used on PraDigi websites to le_utils language object.
    """
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







# ZIP FILE TRANFORMS AND FIXUPS
################################################################################

def make_request(url):
    response = session.get(url)
    if response.status_code != 200:
        LOGGER.error("NOT FOUND: %s" % (url))
    return response

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





# RICECOOKER JSON TRANSFORMATIONS
################################################################################

def get_subtree_by_subject_en(lang, subject, topic=None):
    if lang not in ['mr', 'hi']:
        raise ValueError('Language `lang` must mr or hi (only two langs on website)')
    wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
    with open(wrt_filename) as jsonfile:
        web_resource_tree = json.load(wrt_filename)
    subjects = web_resource_tree['children']
    for subject in subjects:
        if subject['subject_en'] == subject:
            return subject
    return None


def _only_videos(node):
    """
    Set this as the `filter_fn` to `wrt_to_ricecooker_tree` to select only videos.
    """
    allowed = ['lang_page', 'topic_page', 'subtopic_page', 'lesson_page',
               'fun_page', 'story_page', 'PrathamVideoResource']
    return node['kind'] in allowed_kinds


def wrt_to_ricecooker_tree(tree, lang, filter_fn=lambda node: True):
    """
    Transforms web resource subtree `tree` into a riccecooker tree of topics nodes,
    and content nodes, using `filter_fn` to determine if each node should be included or not.
    """
    kind = tree['kind']
    if kind in ['topic_page', 'subtopic_page', 'lesson_page', 'story_page']:
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
                ricocooker_node = wrt_to_ricecooker_tree(child, lang, filter_fn=filter_fn)
                topic_node['children'].append(ricocooker_node)
                
    elif kind == 'PrathamVideoResource':
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        video_node = dict(
            kind=content_kinds.TOPIC,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],  # or could get from Strings based on subject_en...
            description='',
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            files=[],
        )
        video_file = dict(
            file_type=file_types.VIDEO,
            path=tree['url'],
            language=lang,
            ffmpeg_settings={"crf": 24},
        )
        video_node['files'].append(video_file)

    elif kind == 'PrathamZipResource':
        pass

    elif kind == 'PrathamPdfResource' or kind == 'story_resource_page':
        pass

    else:
        raise ValueError('Uknown web resource kind ' + kind + ' encountered.')
    
    





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
      - Games from http://www.gamerepo.prathamcms.org/index.html
    """
    RICECOOKER_JSON_TREE = 'pradigi_ricecooker_json_tree.json'
    
    
    def crawl(self, args, options):
        """
        Crawl website and gamerepo. Save web resource trees in chefdata/trees/.
        """
        pass  # HOOK UP crawlers


    def get_game_rows_for_age_group_and_subject(self, age_group, subject_en):
        """
        Get the relevant rows from the PraDigi structure CSV.
        """
        results = []
        for game_row in self.games_info:
            if game_row[AGE_GROUP_KEY] == age_group and game_row[SUBJECT_KEY] == subject_en:
                results.append(game_row)
        return results


    def build_subtree_for_lang(self, lang):
        print('Building subtree for lang', lang)
        # A. Go through template and populate children with outputs from
        lang_subtree = copy.deepcopy(TEMPLATE_FOR_LANG)
        lang_obj = getlang(lang)
        first_native_name = lang_obj.native_name.split(',')[0].split('(')[0]
        lang_subtree['title'] = first_native_name
        lang_subtree['language'] = lang
        lang_subtree['source_id'] = 'pradigi_'+str(lang)
        age_groups_subtrees = lang_subtree['children']
        for age_groups_subtree in age_groups_subtrees:
            age_group = age_groups_subtree['title']
            age_groups_subtree['kind'] = content_kinds.TOPIC
            age_groups_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group
            subject_subtrees = age_groups_subtree['children']
            for subject_subtree in subject_subtrees:
                subject_subtree['kind'] = content_kinds.TOPIC
                subject_en = subject_subtree['title']
                subject_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group+'_'+subject_en
                if subject_en in PRADIGI_STRINGS[lang]['subjects']:  # localize subject titles
                    subject_subtree['title'] = PRADIGI_STRINGS[lang]['subjects'][subject_en]
                game_rows = self.get_game_rows_for_age_group_and_subject(age_group, subject_en)
                for game_row in game_rows:
                    game_title = game_row[NAME_KEY]
                    game_name = game_row[CODENAME_KEY]
                    games = find_games_for_lang(game_name, lang)
                    for game in games:
                        node = game_info_to_ricecooker_node(lang, game_title, game)
                        subject_subtree['children'].append(node)
        return lang_subtree


    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel
        """
        # download_structure_csv()
        # self.crawl(args, options)

        # this is used for lookups by `get_games_for_age_group_and_subject` so pre-load here
        self.games_info = load_pradigi_structure()

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


    # def run(self, args, options):
    #     print('Not running for real...')





# CLI
################################################################################

if __name__ == '__main__':
    pradigi_chef = PraDigiChef()
    # args, options = pradigi_chef.parse_args_and_options()
    # if 'lang' not in options:
    #     raise ValueError('Need to specify command line option `lang=XY`, where XY in en, fr, ar, sw.')
    pradigi_chef.main()

