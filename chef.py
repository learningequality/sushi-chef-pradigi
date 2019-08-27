#!/usr/bin/env python
"""
The PraDigi chef uses a mix of content from three sources:

1/ PRATHAM Open School website prathamopenschool.org is organized as follow:
    - There is top level set of topics (e.g. Mathematics, English, Science, ...)
        - Each topic has subtopics (e.g. Geometry, Algebra, ...)
            - Each subtopic has lessons (e.g. Triangle, Circle, Polygons, ...)
                - Each lesson has contents like videos, pdfs and html5 apps
        - The Fun/ page contains various videos and HTML5 visaulisations
        - The Stories/ page contains PDFs

We use an Spreadsheet in order to unify and organize the content from these three
sources into a single channel:
https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=342105160
"""

from cachecontrol.heuristics import OneDayCache
import copy
import json
import logging
import os
import requests
import shutil

from le_utils.constants import content_kinds, file_types, licenses
from le_utils.constants.languages import getlang
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils.caching import (FileCache, CacheControlAdapter)
from ricecooker.utils.jsontrees import write_tree_to_json_tree

from structure import GAMENAME_KEY, TAKE_FROM_KEY
from structure import TEMPLATE_FOR_LANG
from structure import get_resources_for_age_group_and_subject
from structure import load_pradigi_structure
from transform import HTML5APP_ZIPS_LOCAL_DIR
from transform import get_zip_file
from transform import get_phet_zip_file
from corrections import should_skip_file




PRADIGI_DOMAIN = 'prathamopenschool.org'
PRADIGI_SOURCE_ID__VARIANT_PRATHAM = 'pradigi-videos-and-games'  # Pratham internal 
PRADIGI_SOURCE_ID__VARIANT_LE = 'pradigi-channel'                # Studio PUBLIC channel
FULL_DOMAIN_URL = 'https://www.' + PRADIGI_DOMAIN
PRADIGI_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='PraDigi').as_dict()
PRADIGI_WEBSITE_LANGUAGES = ['hi', 'mr', 'en', 'gu', 'kn', 'bn', 'ur', 'or', 'pnb', 'ta', 'te', 'as']
PRADIGI_DESCRIPTION = 'Developed by Pratham, these educational games, videos, ' \
    'and ebooks are designed to teach language learning, math, science, English, ' \
    'health, and vocational training in Hindi, Marathi, Odia, Bengali, Urdu, ' \
    'Punjabi, Kannada, Tamil, Telugu, Gujarati and Assamese. Materials are ' \
    'designed for learners of all ages, including those outside the formal classroom setting.'


# In debug mode, only one topic is downloaded.
LOGGER.setLevel(logging.DEBUG)
DEBUG_MODE = True  # source_urls in content desriptions

# WebCache logic (downloaded web resources cached for one day -- good for dev)
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
develop_adapter = CacheControlAdapter(heuristic=OneDayCache(), cache=cache)
session = requests.Session()
session.mount('http://www.' + PRADIGI_DOMAIN, develop_adapter)
session.mount('https://www.' + PRADIGI_DOMAIN, develop_adapter)


# SOURCE WEBSITES
################################################################################
PRADIGI_LANG_URL_MAP = {
    'hi': 'https://www.prathamopenschool.org/hn/',
    'mr': 'https://www.prathamopenschool.org/mr/',
    'en': 'https://www.prathamopenschool.org/en/',
    'gu': 'https://www.prathamopenschool.org/Gj',
    'kn': 'https://www.prathamopenschool.org/kn/',
    'bn': 'https://www.prathamopenschool.org/bn/',
    'ur': 'https://www.prathamopenschool.org/ur/',
    'or': 'https://www.prathamopenschool.org/Od/',
    'pnb': 'https://www.prathamopenschool.org/pn/',
    'ta': 'https://www.prathamopenschool.org/Tm/',
    'te': 'https://www.prathamopenschool.org/Tl/',
    'as': 'https://www.prathamopenschool.org/as/'
}
# assert set(PRADIGI_WEBSITE_LANGUAGES) == set(PRADIGI_LANG_URL_MAP.keys()), 'need url for lang'



# LOCALIZATION AND TRANSLATION STRINGS
################################################################################
PRADIGI_STRINGS = {
    'hi': {
        'language_en': 'Hindi',
        'website_lang': 'hn',
        'gamesrepo_suffixes': ['_KKS', '_HI', '_Hi'],
        'subjects': {
            'Language': 'भाषा',
            'Mathematics': 'गणित',
            'English': 'अंग्रेजी',
            'Science': 'विज्ञान',
            'Health': 'स्वास्थ्य',
            'Sports': 'खेलकूद',
            'Fun': 'मौज',
            'Story': 'कहानियाँ',
            'Hospitality': 'अतिथी सत्कार',
            'Construction': 'भवन-निर्माण',
            'Automobile': 'वाहन',
            'Electric': 'इलेक्ट्रिक',
            'Beauty': 'ब्युटी',
            'Healthcare': 'स्वास्थ्य सेवा',
            'Game': 'खेल',
            'KhelBadi': 'खेल-बाड़ी',
            'WatchAndDo': 'देखो और करों',
            'KhelPuri': 'खेल-पुरी',
            'Music': 'संगीत',
            'Theatre': 'नाटक'
        },
        # Subject (a.k.a. cat_name)  -->  course_id  lookup table
        # this is necessary for special handing of games and visibility in different age groups
        'course_ids_by_subject_en': {
            # Hindi games pages = खेल
            'WatchAndDo': "somethingthatdoesnexist",     # intentionally set to somethingthatdoesnexist
            'KhelPuri': "CRS123",           # "खेल-पुरी",       6-10   # Games Sport-puri
            #
            # Health and Sport for webscraping
            'Sports': 'CRS136',
            'Music': 'Sangeet',
            'Theatre': 'CRS217',
            #
            "Healthcare": "CRS91",
            "Beauty": "CRS130",
            "Electric": "CRS131",
            "Automobile": "CRS129",
            # "Construction": "Construction",
            "Hospitality": "CRS128",
            'Financial Literacy': 'CRS226',
        }
    },
    "mr": {
        "language_en": "Marathi",
        'website_lang': 'mr',
        "gamesrepo_suffixes": ['_KKS', '_MR', '_M'],
        "subjects": {
            'Language': 'भाषा',
            'Mathematics': 'गणित',
            'English': 'इंग्रजी',
            'Science': 'विज्ञान',
            'Health': 'स्वास्थ्य',
            'Sports': 'क्रीडा',
            'Fun': 'मजा',
            'Story': 'गोष्टी',
            'Hospitality': 'आदरातिथ्य',
            'Construction': 'भवन-निर्माण',
            'Electric': 'इलेक्ट्रिकल',
            'Beauty': 'ब्युटी',
            'Healthcare': 'स्वास्थ्य सेवा',
            # 'Financial Literacy': '????',
            'Game': 'खेळ',
            'KhelBadi': 'खेळ-वाडी',
            'WatchAndDo': 'बघा आणि शिका',
            'KhelPuri': 'खेळ-पुरी',
            'Music': 'संगीत',
            'Theatre': 'नाटक'
        },
        'course_ids_by_subject_en': {
            'WatchAndDo': "somethingthatdoesnexist",     # intentionally set to somethingthatdoesnexist
            'KhelPuri': "CRS126",       # "खेळ-पुरी",
            #
            # Health and Sport for webscraping
            'Sports': 'CRS138',
            'Music': 'Sangeet',
            'Theatre': 'CRS234',
            #
            # "Healthcare": "Healthcare",
            "Electric": "CRS141",
            # "Construction": "Construction",
            "Hospitality": "CRS143",
            "Beauty": "CRS144",
            'Financial Literacy': 'CRS227',
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
            "Music": "Music",
            "Fun": "Fun",
            "Story": "Story",
            "Financial Literacy": "Financial Literacy",
            "KhelBadi": "Khel-Baadi",
        },
        'course_ids_by_subject_en': {
            'KhelBadi': "CRS157",
            'Financial Literacy': 'CRS228',
            'Music': 'Sangeet',
            'Health': 'CRS205',
        },
    },
    "or": {
        "language_en": "Odia",     # also appears as Odia in CntResource.lang_name
        'website_lang': 'Od',
        "gamesrepo_suffixes": ['_OD'],
        "subjects": {
            'Language': 'ଭାଷା',
            'Mathematics': 'ଗଣିତ',
            'English': 'ଇଂରାଜୀ',
            'Science': 'ବିଜ୍ଞାନ',
            'Fun': 'ମଜା',
            'Game': 'ଖେଳ',
            'KhelBadi': 'ଖେଳର ବଗିଚା',
            'WatchAndDo': 'ଦେଖ ଏବଂ କର',
            'KhelPuri': 'ଖେଳର ମହଲ'
        },
        'course_ids_by_subject_en': {
            'KhelPuri': "CRS189",
        }
    },
    "bn": {
        "language_en": "Bengali",   # Bengali in CntResource.lang_name
        "gamesrepo_suffixes": ['_BN'],
        "subjects": {
            'Language': 'ভাষা',
            'Mathematics': 'অংক',
            'English': 'ইংরেজি',
            'Science': 'বিজ্ঞান',
            'Health': 'স্বাস্থ্য',
            'Fun': 'মজা',
            'Story': 'গল্প',
            'Game': 'খেলা',
            'KhelBadi': 'আঙিনায় খেলা',
            'WatchAndDo': 'দেখো এবং করো',
            'KhelPuri': 'শহরে খেলা'
        },
        'course_ids_by_subject_en': {
            'Music': 'Sangeet',
            'KhelPuri': "CRS187",
        }
    },
    "ur": {
        "language_en": "Urdu",
        "gamesrepo_suffixes": ['_UD'],
        "subjects": {
            'Language': 'زبان',
            'Mathematics': 'ریاضی',
            'English': 'انگریزی',
            'Science': 'سائنس',
            'Fun': 'Tamasha',
            'Game': 'Khel',
            'KhelBadi': 'Khel-Baadi',
            'WatchAndDo': 'Dekhiye aur Kariye'
        },
        'course_ids_by_subject_en': {
            'KhelBadi': "CRS149",
            'WatchAndDo': "CRS203",
            'English': "Angrezi",  # technically a cat_name, not a course_id ...
        }
    },
    "pnb": {
        "language_en": "Punjabi",
        'website_lang': 'Pn',
        "gamesrepo_suffixes": ['_PN'],
        "subjects": {
            'Language': 'ਭਾਸ਼ਾ',
            'Mathematics': 'ਗਣਿਤ',
            'English': 'ਇੰਗਲਿਸ਼',
            'Science': 'ਵਿਗਿਆਨ',
            'Fun': 'ਮੌਜ-ਮਸਤੀ',
            'Game': 'ਖੇਡ',
            'KhelBadi': 'ਖੇਲਵਾੜੀ',
            'WatchAndDo': 'ਦੇਖੋ ਅਤੇ ਕਰੋ',
            'KhelPuri': 'ਖੇਲ-ਪੁਰ'
        },
        'course_ids_by_subject_en': {
            'KhelPuri': "CRS194",
        }
    },
    "kn": {
        "language_en": "Kannada",
        "gamesrepo_suffixes": ['_KN'],
        "subjects": {
            'Language': 'ಭಾಷೆ',
            'Mathematics': 'ಗಣಿತ',
            'English': 'ಇಂಗ್ಲೀಷ್',
            'Science': 'ವಿಜ್ಞಾನ',
            'Health': 'ಆರೋಗ್ಯ',
            'Fun': 'ಮೋಜು',
            'Game': 'ಗೇಮ್',
            'KhelBadi': 'ಆಟದ ಅಂಗಳ',
            'WatchAndDo': 'ನೋಡು ಮತ್ತು ಮಾಡು',
            'KhelPuri': 'ಆಟದ ನಗರಿ'
        },
        'course_ids_by_subject_en': {
            'Music': 'Sangeet',
            'KhelPuri': "CRS169",
        }
    },
    "ta": {
        "language_en": "Tamil",
        'website_lang': 'Tm',
        "gamesrepo_suffixes": ['_TM'],
        "subjects": {
            'Language': 'மொழி',
            'Mathematics': 'கணிதம்',
            'English': 'ஆங்கிலம்',
            'Science': 'அறிவியல்',
            'Health': 'உடல் நலம்',
            'Fun': 'கேளிக்கை',
            'Game': 'விளையாட்டு',
            'KhelBadi': 'வீதி விளையாட்டு',
            'WatchAndDo': 'பார்த்து செய்யவும்',
            'KhelPuri': 'விளையாட்டுத் திடல்'
        },
        'course_ids_by_subject_en': {
            'KhelPuri': "CRS112",
        }
    },
    "te": {
        "language_en": "Telugu",
        'website_lang': 'Tl',
        "gamesrepo_suffixes": ['_TL'],
        "subjects": {
            'Language': 'భాషా',
            'Mathematics': 'గణితం',
            'English': 'ఇంగ్లీష్',
            'Science': 'సైన్స్',
            'Health': 'ఆరోగ్యం',
            'Fun': 'సరదా',
            'Game': 'ఆట',
            'KhelBadi': 'ఆట - ప్రాంగణం',
            'WatchAndDo': 'చూడండి మరియు చేయండి',
            'KhelPuri': 'ఆట - నగరం'
        },
        'course_ids_by_subject_en': {
            'Music': 'Sangeet',
            'KhelPuri': "CRS176",
        }
    },
    "gu": {
        'website_lang': 'Gj',
        "language_en": "Gujarati",
        "gamesrepo_suffixes": ['_KKS', '_GJ', '_Gj'],
        "subjects": {
            'Language': 'ભાષાી',
            'Mathematics': 'ગણિતશાસ્ત્ર',
            'English': 'અંગ્રેજી',
            'Science': 'વિજ્ઞાન',
            'Health': 'સ્વાસ્થ્ય',
            'Fun': 'મનોરંજન',
            'Game': 'રમત',
            'KhelBadi': 'ખેલ-વાડી',
            'WatchAndDo': 'જુઓ અને કરો',
            'KhelPuri': 'ખેલ-પૂરી'
        },
        'course_ids_by_subject_en': {
            'Music': 'Sangeet',
            'KhelPuri': "CRS108",
        }
    },
    "as": {
        "language_en": "Assamese",
        "gamesrepo_suffixes": ['_AS'],
        "subjects": {
            'Language': 'ভাষা',
            'Mathematics': 'গণিত',
            'English': 'ইংৰাজী',
            'Science': 'বিজ্ঞান',
            'Fun': 'ধেমালি',
            'Game': 'খেল',
            'KhelBadi': 'খেল-পথাৰ',
            'WatchAndDo': 'চোৱা আৰু কৰা',
            'KhelPuri': 'খেল- ধেমালী'
        },
        'course_ids_by_subject_en': {
            'KhelPuri': "CRS106",
            'Music': 'Sangeet',
        }
    },
}

# # lookup helper function, e.g. English --> en
# LANGUAGE_EN_TO_LANG = {}
# for lang, lang_data in PRADIGI_STRINGS.items():
#     language_en = lang_data['language_en']
#     LANGUAGE_EN_TO_LANG[language_en] = lang








# RICECOOKER JSON TRANSFORMATIONS
################################################################################

def get_subtree_by_subject_en(lang, subject):
    if lang not in PRADIGI_LANG_URL_MAP:
        raise ValueError('Language `lang` must be in PRADIGI_LANG_URL_MAP')
    wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
    with open(wrt_filename) as jsonfile:
        web_resource_tree = json.load(jsonfile)
    subject_subtrees = web_resource_tree['children']
    try:
        for subject_subtree in subject_subtrees:
            if 'subject_en' in subject_subtree and subject_subtree['subject_en'] == subject:
                return subject_subtree
            elif 'source_id' in subject_subtree and subject_subtree['source_id'] == subject:
                return subject_subtree
            else:
                pass
                # print('no subject_en in '+ subject_subtree['source_id'])
    except Exception as e:
        LOGGER.error("in get_subtree_by_subject_en: %s, %s, %s, %s" %
                     (lang, subject, subject_subtree, e))
    return None


def get_subtree_by_source_id(lang, source_id):
    """
    Walk the `lang` web resouce tree and finds the subtree that has `source_id`.
    """
    if lang not in PRADIGI_LANG_URL_MAP:
        raise ValueError('Language `lang` must be in PRADIGI_LANG_URL_MAP')
    wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
    with open(wrt_filename) as jsonfile:
        web_resource_tree = json.load(jsonfile)
    # setup recusive find function
    def recursive_find_by_source_id(subtree, source_id):
        if subtree['source_id'] == source_id:
            return subtree
        if 'children' in subtree:
            for child in subtree['children']:
                result = recursive_find_by_source_id(child, source_id)
                if result is not None:
                    return result
        return None
    # use it on wrt
    return recursive_find_by_source_id(web_resource_tree, source_id)



def wrt_to_ricecooker_tree(tree, lang, filter_fn=lambda node: True):
    """
    Transforms web resource subtree `tree` into a riccecooker tree of topics nodes,
    and content nodes, using `filter_fn` to determine if each node should be included or not.
    """
    kind = tree['kind']
    if kind in ['topic_page', 'subtopic_page', 'lesson_page', 'fun_page', 'story_page', 'special_subtopic_page']:
        thumbnail = tree['thumbnail_url'] if 'thumbnail_url' in tree else None
        topic_node = dict(
            kind=content_kinds.TOPIC,
            source_id=tree['source_id'],
            language=lang,
            title=tree['title'],  # or could get from Strings based on subject_en...
            description='source_id=' + tree['source_id'] if DEBUG_MODE else '',
            thumbnail=thumbnail,
            license=PRADIGI_LICENSE,
            children=[],
        )
        source_ids_seen_so_far = []
        for child in tree['children']:
            if filter_fn(child):
                try:
                    ricocooker_node = wrt_to_ricecooker_tree(child, lang, filter_fn=filter_fn)
                    if ricocooker_node:
                        new_source_id = ricocooker_node['source_id']
                        if new_source_id not in source_ids_seen_so_far:
                            topic_node['children'].append(ricocooker_node)
                            source_ids_seen_so_far.append(new_source_id)
                        else:
                            print('Skipping node with duplicate source_id', ricocooker_node)
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
        video_url = tree['url']
        if video_url.endswith('.MP4'):
            video_url = video_url.replace('.MP4', '.mp4')
        video_file = dict(
            file_type=file_types.VIDEO,
            path=video_url,
            language=lang,
        )
        if should_compress_video(tree):
            video_file['ffmpeg_settings'] = {"crf": 28}   # average quality
        video_node['files'].append(video_file)
        return video_node

    elif kind == 'PrathamZipResource':
        if should_skip_file(tree['url']):
            return None  # Skip games marked with the `SKIP GAME` correction actions
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
    order to limit storage and transfer needs.
    """
    size_bytes = video_web_resource['content-length']
    size_mb = int(size_bytes)/1024/1024
    if size_mb > 30:
        return True
    else:
        return False




# GAMESREPO UTILS
################################################################################

def find_games_for_lang(name, lang, take_from=None):
    """
    Find first game from the following sources:
      1. flattended website games list for `lang`
    """
    suffixes = PRADIGI_STRINGS[lang]['gamesrepo_suffixes']
    suffixes = suffixes*2   # Double list to implement two-passes (needed for multi-suffix games)
    suffixes.append('_KKS_Hi')  # Mar 2nd Hi game used in other laguages
    suffixes.append('_KKS_MR')  # Mar 2nd MR game used in other laguages
    language_en = PRADIGI_STRINGS[lang]['language_en'] # ???

    # load website game web resource data
    WEBSITE_GAMES_OUTPUT = 'chefdata/trees/website_games_all_langs.json'
    website_data = json.load(open(WEBSITE_GAMES_OUTPUT, 'r'))
    if lang in website_data:
        website_data_lang = website_data[lang]
    else:
        website_data_lang = []

    games = []
    #
    # Get game from website_games json by title_en (ignoring _LANG suffixes)
    for game_resource in website_data_lang:
        title = game_resource['title_en']
        for suffix in suffixes:
            if title.strip().endswith(suffix):
                title = title.replace(suffix, '').strip()
        if name == title:
            # source_id = game_resource['source_id']
            if len(games) == 0:
                games.append(game_resource)
        else:
            if game_resource['title_en'].startswith(name):
                print('>>>>> skipping game_resource', game_resource, 'even though it is similar', name, 'in lang', lang)

    if len(games) == 0:
        pass
        # print('game', name, 'not found for lang', lang)

    return games



# WEBSITE GAME JSON to RICECOOKER JSON
################################################################################

def website_game_webresouce_to_ricecooker_node(lang, web_resource):
    """
    Create Ricecooker Json structure for game from web resource dict `web_resource`.
    """
    game_node = dict(
        kind=content_kinds.HTML5,
        source_id=web_resource['source_id'],
        language=lang,
        title=web_resource['title'],
        description='source_url=' + web_resource['url'] if DEBUG_MODE else '',
        license=PRADIGI_LICENSE,
        thumbnail=web_resource.get('thumbnail_url'),
        files=[],
    )
    zip_tmp_path = get_zip_file(web_resource['url'], web_resource['main_file'])
    if zip_tmp_path:
        zip_file = dict(
            file_type=file_types.HTML5,
            path=zip_tmp_path,
            language=lang,
        )
        game_node['files'].append(zip_file)
        LOGGER.debug('Created HTML5AppNode for game ' + web_resource['title'])
        return game_node
    else:
        LOGGER.error('Failed to create zip for game at url=' + web_resource['url'])
        return None



# OCT updates helpers
################################################################################

def get_all_game_names():
    """
    Used for debugging chef
    """
    game_names = []
    struct_list = load_pradigi_structure()
    struct_list.extend(load_pradigi_structure(which='English'))
    for struct_row in struct_list:
        codename = struct_row[GAMENAME_KEY]
        if codename is not None and codename not in game_names:
            game_names.append(struct_row[GAMENAME_KEY])
    return game_names

ALL_MANUALLY_CURATED_GAME_NAMES = get_all_game_names()


def is_website_game(url):
    """
    Checks if a `url` is a website game.
    """
    if 'CourseContent/Games' not in url:
        return False
    url_path = url.replace('https://www.prathamopenschool.org/CourseContent/Games/', '')
    url_path = url_path.replace('http://www.prathamopenschool.org/CourseContent/Games/', '')
    for name in ALL_MANUALLY_CURATED_GAME_NAMES:
        if url_path.startswith(name):
            return True
    return False


def extract_website_games_from_tree(lang):
    """
    Extracts all games from the normal web resource tree so they be manually
    placed within additional subject folders.
    Returns `website_games` (list) for given `lang`.
    """
    if lang not in PRADIGI_LANG_URL_MAP:
        raise ValueError('Language `lang` must be in PRADIGI_LANG_URL_MAP')
    # READ IN
    wrt_filename = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
    with open(wrt_filename) as jsonfile:
        web_resource_tree = json.load(jsonfile)
    # PROCESS
    website_games = []
    def recursive_extract_website_games(subtree):
        """
        Processes all child nodes of the subtree then calls itself on any folder-like
        child nodes. Weird, I know, but it works so I'm not touching it.
        """
        if 'children' in subtree:
            # do processing
            new_children = []
            for child in subtree['children']:
                child_url = child['url']
                if child['kind'] == 'PrathamZipResource':
                    if is_website_game(child_url):
                        # extract all game names referenced in manual curation Excel file to process separately...
                        child_url = child_url.replace('https://www.prathamopenschool.org/CourseContent/Games/', '')
                        child_url = child_url.replace('http://www.prathamopenschool.org/CourseContent/Games/', '')
                        child['title_en'] = child_url.replace('.zip', '')
                        print('EXTRACTED game name', child['title_en'], 'form url', child['url'])
                        website_games.append(child)
                    else:
                        # leave other games where they are
                        LOGGER.info('Undocumented game-like web resource ' + child['url'])
                        new_children.append(child)
                else:
                    # leave other content as is
                    new_children.append(child)
            #
            # recurse
            for child in subtree['children']:
                recursive_extract_website_games(child)
    recursive_extract_website_games(web_resource_tree)
    return website_games








# CHEF
################################################################################

class PraDigiChef(JsonTreeChef):
    """
    SushiChef script for importing and merging the content from these sources:
      - Video, PDFs, and interactive demos from http://www.prathamopenschool.org/
      - Games from http://www.prathamopenschool.org/ 
    """
    RICECOOKER_JSON_TREE = 'pradigi_ricecooker_json_tree.json'


    def crawl(self, args, options):
        """
        Crawl website and save web resource trees in chefdata/trees/.
        """
        from pradigi_crawlers import PraDigiCrawler
        
        # website
        for lang in PRADIGI_WEBSITE_LANGUAGES:
            website_crawler = PraDigiCrawler(lang=lang)
            website_crawler.crawl()    # Output is saved to appropriate wrt file

        # extract
        website_games = {}
        for lang in PRADIGI_WEBSITE_LANGUAGES:
            lang_games = extract_website_games_from_tree(lang)
            website_games[lang] = lang_games
        WEBSITE_GAMES_OUTPUT = 'chefdata/trees/website_games_all_langs.json'
        # Save website games
        with open(WEBSITE_GAMES_OUTPUT, 'w') as json_file:
            json.dump(website_games, json_file, ensure_ascii=False, indent=2, sort_keys=True)


    def build_subtree_for_lang(self, lang):
        LOGGER.info('Building subtree for lang {}'.format(lang))
        
        lang_subtree = copy.deepcopy(TEMPLATE_FOR_LANG)
        lang_obj = getlang(lang)
        language_en = PRADIGI_STRINGS[lang]['language_en']
        first_native_name = lang_obj.native_name.split(',')[0].split('(')[0]
        lang_subtree['title'] = first_native_name
        lang_subtree['language'] = lang
        lang_subtree['source_id'] = 'pradigi_'+str(lang)
        thumbnail_path = os.path.join('chefdata', 'LanguagesImages', language_en + '.png')
        lang_subtree['thumbnail'] = thumbnail_path

        # Go through template age groups and subjects
        age_groups_subtrees = lang_subtree['children']
        for age_groups_subtree in age_groups_subtrees:
            age_group = age_groups_subtree['title']
            age_groups_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group
            subject_subtrees = age_groups_subtree['children']
            for subject_subtree in subject_subtrees:
                subject_en = subject_subtree['title']
                subject_subtree['source_id'] = 'pradigi_'+str(lang)+'_'+age_group+'_'+subject_en

                # MAIN LOOKUP FUNCTION -- GETS CHANNEL STRUCTURE FROM CSV
                resources = get_resources_for_age_group_and_subject(age_group, subject_en, language_en)
                assert 'website' in resources, 'Missing website key in resources dict'
                assert 'games' in resources, 'Missing games key in resources dict'

                ################################################################
                LOGGER.info('In main loop lang={} age_group={} subject_en={}'.format(lang, age_group, subject_en))

                # A. Load website resources
                if lang in PRADIGI_WEBSITE_LANGUAGES:
                    for desired_subject_en in resources['website']:
                        # manual course_id rename for courses where subject_en not the same as cateogy_id
                        lookup_table = PRADIGI_STRINGS[lang]['course_ids_by_subject_en']
                        if desired_subject_en in lookup_table:
                            desired_subject_en = lookup_table[desired_subject_en]
                        #
                        wrt_subtree = get_subtree_by_subject_en(lang, desired_subject_en)
                        if wrt_subtree:
                            ricecooker_subtree = wrt_to_ricecooker_tree(wrt_subtree, lang)
                            # Set title to localized name obtained from website
                            subject_subtree['title'] = ricecooker_subtree['title']
                            # overwsite subject titles when translation is available
                            if subject_en in PRADIGI_STRINGS[lang]['subjects']:
                                subject_subtree['title'] = PRADIGI_STRINGS[lang]['subjects'][subject_en]
                            for child in ricecooker_subtree['children']:
                                subject_subtree['children'].append(child)
                        else:
                            print('no wrt for subject ' + desired_subject_en + ' in language ' + lang)

                # Needed to avoid duplicates
                web_resources_source_ids = [ch['source_id'] for ch in subject_subtree['children']]

                # B. Load game resources
                game_rows = resources['games']
                print('Processing games:', [game_row[GAMENAME_KEY] for game_row in game_rows])
                for game_row in game_rows:
                    game_name = game_row[GAMENAME_KEY]
                    take_from = game_row[TAKE_FROM_KEY]
                    unfiltered_games = find_games_for_lang(game_name, lang, take_from=take_from)
                    # check if we filter out games in the action='SKIP GAME' list
                    games = [game for game in unfiltered_games if not should_skip_file(game['url'])]
                    # print('Processing games', games, 'under game_title', game_title, 'for lang', lang, 'found take_from=', take_from, flush=True)
                    for game in games:
                        # CASE website game
                        if 'title_en' in game:
                            game_source_id  = game['source_id']
                            if game_source_id not in web_resources_source_ids:
                                # website games:.
                                node = website_game_webresouce_to_ricecooker_node(lang, game)
                                web_resources_source_ids.append(game_source_id)
                            else:
                                node = None
                        else:
                            # gamerepo games
                            raise ValueError('Should be processing only website games now...')
                        if node:
                            subject_subtree['children'].append(node)

                # Set title to localized name (in case not already translated..)
                current_title = subject_subtree['title']
                if current_title in PRADIGI_STRINGS[lang]['subjects']:
                    subject_subtree['title'] = PRADIGI_STRINGS[lang]['subjects'][current_title]

            # Remove empty subject_tree topic nodes
            nonempty_subject_subtrees = []
            for subject_subtree in subject_subtrees:
                if len(subject_subtree['children']) == 0:
                    pass
                else:
                    nonempty_subject_subtrees.append(subject_subtree)
            # TODO: check for empty sub-folders too
            age_groups_subtree['children'] = nonempty_subject_subtrees

            # Flatten the '3-6 years' agre group to contain contents of KhelBadi
            if age_groups_subtree['title'] == '3-6 years' and len(age_groups_subtree['children']) == 1:
                khelbadi_subtree = age_groups_subtree['children'][0]
                age_groups_subtree['children'] = khelbadi_subtree['children']

        return lang_subtree


    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel
        """
        LOGGER.info('in pre_run...')

        # delete .zip files in temporary dir when running using update
        if args['update']:
            LOGGER.info('Deleting all zips in cache dir {}'.format(HTML5APP_ZIPS_LOCAL_DIR))
            for rel_path in os.listdir(HTML5APP_ZIPS_LOCAL_DIR):
                abs_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, rel_path)
                if os.path.isdir(abs_path):
                    shutil.rmtree(abs_path)

        # option to skip crawling stage
        if 'nocrawl' not in options:
            self.crawl(args, options)

        # Conditionally determine `source_id` depending on variant specified
        if 'variant' in options and options['variant'].upper() == 'LE':
            # Official PraDigi channel = 
            channel_name = 'PraDigi'
            channel_source_id = PRADIGI_SOURCE_ID__VARIANT_LE
            DEBUG_MODE = False
        else:
            # Pratham ETL (used to import content from website into Pratham app)
            # channel_id = f9da12749d995fa197f8b4c0192e7b2c
            channel_name = 'PraDigi Pratham'
            channel_source_id = PRADIGI_SOURCE_ID__VARIANT_PRATHAM

        ricecooker_json_tree = dict(
            title=channel_name,
            source_domain=PRADIGI_DOMAIN,
            source_id=channel_source_id,
            description=PRADIGI_DESCRIPTION,
            thumbnail='chefdata/prathamlogo_b01-v1.jpg',
            language='mul',
            children=[],
        )
        for lang in PRADIGI_WEBSITE_LANGUAGES:
            lang_subtree = self.build_subtree_for_lang(lang)
            ricecooker_json_tree['children'].append(lang_subtree)
        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


    def run(self, args, options):
        print('options=', options, flush=True)
        if 'crawlonly' in options:
            self.pre_run(args, options)
            print('Crawling done. Skipping rest of chef run since `crawlonly` is set.')
            return
        super(PraDigiChef, self).run(args, options)




# CLI
################################################################################

if __name__ == '__main__':
    pradigi_chef = PraDigiChef()
    pradigi_chef.main()
