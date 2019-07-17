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

import copy
import csv
import hashlib
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

from bs4 import BeautifulSoup
from le_utils.constants import content_kinds, file_types, licenses
from le_utils.constants.languages import getlang
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from cachecontrol.heuristics import OneDayCache
from ricecooker.utils.caching import (FileCache, CacheControlAdapter)
from ricecooker.utils.jsontrees import write_tree_to_json_tree
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip


PRADIGI_DOMAIN = 'prathamopenschool.org'
FULL_DOMAIN_URL = 'https://www.' + PRADIGI_DOMAIN
PRADIGI_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='PraDigi').as_dict()
PRADIGI_WEBSITE_LANGUAGES = ['hi', 'mr', 'en', 'gu', 'kn', 'bn', 'ur', 'or', 'pnb', 'ta', 'te']
PRADIGI_DESCRIPTION = 'PraDigi, developed by Pratham, consists of educational '   \
    + 'games, videos, and ebooks on language learning, math, science, English, '  \
    + 'health, and vocational training. The learning material, available for '    \
    + 'children and youth, is offered in multiple languages: Punjabi, Assamese, ' \
    + 'Bengali, Odiya, Telugu, Tamil, Kannada, Marathi, Gujarati, Hindi, and English.'


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
}
# assert set(PRADIGI_WEBSITE_LANGUAGES) == set(PRADIGI_LANG_URL_MAP.keys()), 'need url for lang'

GAME_THUMBS_LOCAL_DIR = 'chefdata/gamethumbnails'
HTML5APP_ZIPS_LOCAL_DIR = 'chefdata/zipfiles'


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
            'KhelBadi': "KhelBadi",           # "खेल-बाड़ी"       3-6    # Game-box
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
            'KhelBadi': "KhelBadi",       # "खेळ-वाडी",
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
            "Music": "Sangeet",
            "Fun": "Fun",
            "Story": "Story",
            "FinancialLiteracy": "Financial Literacy",
            "KhelBadi": "Khel-Baadi",
        },
        'course_ids_by_subject_en': {
            'KhelBadi': "CRS157",
            # 'FinancialLiteracy': 'CRS228',
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
            'KhelBadi': "CRS110",
            'WatchAndDo': "CRS188",
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
            'KhelBadi': "CRS107",
            'WatchAndDo': "CRS186",
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
            'KhelBadi': "CRS111",
            'WatchAndDo': "CRS192",
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
            'KhelBadi': "CRS168",
            'WatchAndDo': "CRS170",
            'KhelPuri': "CRS169",
            #
            # Health and Sport for webscraping
            'Health': 'CRS153',
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
            'KhelBadi': "CRS195",
            'WatchAndDo': "CRS196",
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
            'KhelBadi': "CRS113",
            'WatchAndDo': "CRS177",
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
            'KhelBadi': "CRS174",
            'WatchAndDo': "CRS175",
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
            'KhelBadi': "CRS199",
            'WatchAndDo': "CRS200",
            'KhelPuri': "CRS106",
        }
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
GAMENAME_KEY = 'Game Name'
TAKE_FROM_KEY = 'Take From Repo'
USE_ONLY_IN_KEY = 'Use Only In'
PRATHAM_COMMENTS_KEY = 'Pratham'
LE_COMMENTS_KEY = 'LE Comments'
PRADIGI_AGE_GROUPS = ['3-6 years', '6-10 years', '8-14 years', '14 and above']
PRADIGI_SUBJECTS = [
    'Mathematics',      #                             math games
    'Language',         # Koibri-only folder just for langauge games
    'English',
    'Science',
    #
    'Health',
    'Sports',
    'Music',
    'Theatre',
    'Art Project',
    #
    'Fun',              # Contains website /Fun content + all games not in the other categories
    'Story',
    #
    'Hospitality',
    'Automobile',
    'Beauty',
    'Electric',
    'Healthcare',
    'Construction',
    'Financial Literacy',
    '14_To_18',
    #
    # Games pages
    'KhelBadi',           # "खेल-बाड़ी"       3-6    # Game-box
    'WatchAndDo',         # "देखो और करों     3-6,   # Watch and Do
    'KhelPuri',           # "खेल-पुरी",       6-10   # Games Sport-puri
    #
    'LanguageAndCommunication',     # currently missing from website
]
PRADIGI_RESOURCE_TYPES = ['Game', 'Website Resources']
# Note: can add 'Video Resources', 'Interactive Resoruces' and 'Book Resources'
# as separate categories for more flexibility in the future
PRADIGI_SHEET_CSV_FILEDNAMES = [
    AGE_GROUP_KEY,
    SUBJECT_KEY,
    RESOURCE_TYPE_KEY,
    GAMENAME_KEY,
    TAKE_FROM_KEY,
    USE_ONLY_IN_KEY,
    PRATHAM_COMMENTS_KEY,
    LE_COMMENTS_KEY,
]

# NEW: July 12 load data from separate sheet for English folder structure
PRADIGI_ENGLISH_STRUCTURE_SHEET_GID = '1812185465'
PRADIGI_ENGLISH_SHEET_CSV_URL = GSHEETS_BASE + PRADIGI_SHEET_ID + '/export?format=csv&gid=' + PRADIGI_ENGLISH_STRUCTURE_SHEET_GID
PRADIGI_ENGLISH_SHEET_CSV_PATH = 'chefdata/pradigi_english_structure.csv'


def download_structure_csv(which=None):
    if which == 'English':
        response = requests.get(PRADIGI_ENGLISH_SHEET_CSV_URL)
        csv_data = response.content.decode('utf-8')
        with open(PRADIGI_ENGLISH_SHEET_CSV_PATH, 'w') as csvfile:
            csvfile.write(csv_data)
            LOGGER.info('Succesfully saved ' + PRADIGI_ENGLISH_SHEET_CSV_PATH)
        return PRADIGI_ENGLISH_SHEET_CSV_PATH
    else:
        response = requests.get(PRADIGI_SHEET_CSV_URL)
        csv_data = response.content.decode('utf-8')
        with open(PRADIGI_SHEET_CSV_PATH, 'w') as csvfile:
            csvfile.write(csv_data)
            LOGGER.info('Succesfully saved ' + PRADIGI_SHEET_CSV_PATH)
        return PRADIGI_SHEET_CSV_PATH

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

def load_pradigi_structure(which=None):
    csv_path = download_structure_csv(which=which)
    struct_list = []
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=PRADIGI_SHEET_CSV_FILEDNAMES)
        next(reader)  # Skip Headers row
        next(reader)  # Skip info line
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[SUBJECT_KEY] is None:
                continue  # skip blank lines (identified by missing subject col)
            if clean_row[AGE_GROUP_KEY] in PRADIGI_AGE_GROUPS and clean_row[SUBJECT_KEY] in PRADIGI_SUBJECTS:
                resource_type = clean_row[RESOURCE_TYPE_KEY]
                if resource_type == 'Game' and clean_row[GAMENAME_KEY]:
                    # make sure Game Name is present when specifying a game
                    struct_list.append(clean_row)
                elif resource_type == 'Website Resources':
                    struct_list.append(clean_row)
                else:
                    LOGGER.warning('Problem with structure row {}'.format(str(clean_row)))
            else:
                LOGGER.warning('Unrecognized structure row {}'.format(str(clean_row)))
    return struct_list


PRADIGI_STRUCT_LIST = load_pradigi_structure()
PRADIGI_ENGLISH_STRUCT_LIST = load_pradigi_structure(which='English')





def get_tree_for_lang_from_structure():
    """
    Build the template structure for language-subtree based on structure in CSV.
    """
    lang_tree = dict(
        kind=content_kinds.TOPIC,
        children=[],
    )
    struct_list = PRADIGI_STRUCT_LIST + PRADIGI_ENGLISH_STRUCT_LIST
    struct_list = sorted(struct_list, key=itemgetter(AGE_GROUP_KEY, SUBJECT_KEY))
    age_groups_dict = dict((k, list(g)) for k, g in groupby(struct_list, key=itemgetter(AGE_GROUP_KEY)))
    for age_group_title in PRADIGI_AGE_GROUPS:
        age_groups_subtree = dict(
            title=age_group_title,
            kind=content_kinds.TOPIC,
            children=[],
        )
        lang_tree['children'].append(age_groups_subtree)
        items_in_age_group = list(age_groups_dict[age_group_title])
        items_in_age_group = sorted(items_in_age_group, key=itemgetter(SUBJECT_KEY))
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

TEMPLATE_FOR_LANG = get_tree_for_lang_from_structure()



def get_resources_for_age_group_and_subject(age_group, subject_en, language_en):
    """
    Select the rows from the structure CSV with matching age_group and subject_en.
    Returns a dictionary:
    { 
        'website': [subject_en, ...],  # Include all from /subject_en on website
        'games': [{game struct row}, {anothe game row}, ...]   # Include localized verison of games in this list
    }
    """
    # print('in get_resources_for_age_group_and_subject with', age_group, subject_en, flush=True)
    if language_en == 'English':
        struct_list = PRADIGI_ENGLISH_STRUCT_LIST
    else:
        struct_list = PRADIGI_STRUCT_LIST
    website = []
    games = []
    for row in struct_list:
        if row[AGE_GROUP_KEY] == age_group and row[SUBJECT_KEY] == subject_en:
            if row[USE_ONLY_IN_KEY] and not row[USE_ONLY_IN_KEY] == language_en:
                # skip row if USE_ONLY set and different from current language
                continue
            if row[RESOURCE_TYPE_KEY] == 'Game':
                games.append(row)
            elif row[RESOURCE_TYPE_KEY] == 'Website Resources':
                website.append(subject_en)
            else:
                print('Unknown resource type', row[RESOURCE_TYPE_KEY], 'in row', row)
    # print('games=', games, flush=True)
    return {'website':website, 'games':games}




# CORRECTIONS = Excel sheet to edit or specify correction tasks
################################################################################

PRADIGI_CORRECTIONS_SHEET_GID = '93933238'
PRADIGI_CORRECTIONS_CSV_URL = GSHEETS_BASE + PRADIGI_SHEET_ID + '/export?format=csv&gid=' + PRADIGI_CORRECTIONS_SHEET_GID
PRADIGI_CORRECTIONS_CSV_PATH = 'chefdata/pradigi_corrections.csv'
CORRECTIONS_ID_KEY = 'Correction ID'
CORRECTIONS_BUG_TYPE_KEY = 'Bug Type'
CORRECTIONS_GAME_NAME_KEY = 'Game Name'
CORRECTIONS_SOURCE_URL_PAT_KEY = 'Source URL (Regular Expression)'
CORRECTIONS_ACTION_KEY = 'Action'
CORRECTIONS_COMMENT_KEY = 'Comment'
PRADIGI_CORRECTIONS_CSV_FILEDNAMES = [
    CORRECTIONS_ID_KEY,
    CORRECTIONS_BUG_TYPE_KEY,
    CORRECTIONS_GAME_NAME_KEY,
    CORRECTIONS_SOURCE_URL_PAT_KEY,
    CORRECTIONS_ACTION_KEY,
    CORRECTIONS_COMMENT_KEY,
]
SKIP_GAME_ACTION = 'SKIP GAME'
ADD_MARGIN_TOP_ACTION = 'ADD MARGIN-TOP'
# Third possible action 'REPLACE WITH:{URL}' handled manually in code
PRADIGI_CORRECTIONS_ACTIONS = [SKIP_GAME_ACTION, ADD_MARGIN_TOP_ACTION]



def download_corrections_csv():
    response = requests.get(PRADIGI_CORRECTIONS_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(PRADIGI_CORRECTIONS_CSV_PATH, 'w') as csvfile:
        csvfile.write(csv_data)
        LOGGER.info('Succesfully saved ' + PRADIGI_CORRECTIONS_CSV_PATH)

def load_pradigi_corrections():
    download_corrections_csv()
    struct_list = []
    with open(PRADIGI_CORRECTIONS_CSV_PATH, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=PRADIGI_CORRECTIONS_CSV_FILEDNAMES)
        next(reader)  # Skip Headers row
        next(reader)  # Skip info line
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[CORRECTIONS_ACTION_KEY] is None:
                continue  # skip blank lines (identified by missing action col)
            action = clean_row[CORRECTIONS_ACTION_KEY]
            if action in PRADIGI_CORRECTIONS_ACTIONS or action.startswith('REPLACE WITH:'):
                try:
                    pat_str = clean_row[CORRECTIONS_SOURCE_URL_PAT_KEY]
                    pat = re.compile(pat_str)
                    clean_row[CORRECTIONS_SOURCE_URL_PAT_KEY] = pat
                    struct_list.append(clean_row)
                except re.error as e:
                    print('RE error {} when parsing pat {}'.format(e, pat_str))
            elif action == 'FIXED':
                pass  # nothing to do for fixed games...
            else:
                print('Unrecognized corrections row', clean_row)
    return struct_list

PRADIGI_CORRECTIONS_LIST = load_pradigi_corrections()


def should_skip_file(url):
    """
    Checks `url` against list of SKIP GAME corrections.
    Returns True if `url` should be skipped, False otherwise
    """
    should_skip = False
    for row in PRADIGI_CORRECTIONS_LIST:
        if row[CORRECTIONS_ACTION_KEY] == SKIP_GAME_ACTION:
            pat = row[CORRECTIONS_SOURCE_URL_PAT_KEY]
            m = pat.match(url)
            if m:
                should_skip = True
    return should_skip


def should_replace_with(url):
    """
    Checks `url` against list of REPLACE WITH: corrections and returns the
    replaceement url if match found. Used to replace zips with manual fixes.
    """
    for row in PRADIGI_CORRECTIONS_LIST:
        action = row[CORRECTIONS_ACTION_KEY]
        if action.startswith('REPLACE WITH:'):
            pat = row[CORRECTIONS_SOURCE_URL_PAT_KEY]
            m = pat.match(url)
            if m:
                replacement_url = action.replace('REPLACE WITH:', '')
                return replacement_url.strip()
    return None


# ZIP FILE DOWNLOADING, TRANFORMS, AND FIXUPS
################################################################################

def make_request(url):
    response = session.get(url)
    if response.status_code != 200:
        LOGGER.error("ERROR when GETting: %s" % (url))
    return response

def make_temporary_dir_from_key(key_str):
    """
    Creates a subdirectory of HTML5APP_ZIPS_LOCAL_DIR to store
    the downloded, unzipped, and final version of each HTML5Zip file.
    """
    key_bytes = key_str.encode('utf-8')
    m = hashlib.md5()
    m.update(key_bytes)
    subdir = m.hexdigest()
    dest = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, subdir)
    if not os.path.exists(dest):
        os.mkdir(dest)
    return dest

def add_body_margin_top(zip_folder, filename, margin='44px'):
    file_path = os.path.join(zip_folder, filename)
    with open(file_path, 'r') as inf:
        html = inf.read()
    page = BeautifulSoup(html, "html.parser")  # Load index.html as BS4
    body = page.find('body')
    if body.has_attr('style'):
        prev_style_str = body['style']
    else:
        prev_style_str = ''
    body['style'] = prev_style_str + " margin-top:" + margin + ";"
    with open(file_path, 'w') as outf:
        outf.write(str(page))


def get_zip_file(zip_file_url, main_file):
    """
    HTML games are provided as zip files, the entry point of the game is `main_file`.
    THe `main_file` needs to be renamed to index.html to make it compatible with Kolibri.
    """
    key = zip_file_url + main_file
    destpath = make_temporary_dir_from_key(key)
    
    # Check for "REPLACE WITH:" correction rule for the current `zip_file_url`
    replacement_url = should_replace_with(zip_file_url)
    if replacement_url:
        zip_file_url = replacement_url

    # return cached version if already there
    final_webroot_path = os.path.join(destpath, 'webroot.zip')
    if os.path.exists(final_webroot_path):
        return final_webroot_path

    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]         # e.g. Mathematics.zip
        zip_basename = zip_filename.rsplit('.', 1)[0]      # e.g. Mathematics/

        # Oct 9: handle ednge cases where zip filename doesn't match folder name inside it
        if 'Awazchitra_HI' in zip_basename:
            zip_basename = zip_basename.replace('Awazchitra_HI', 'AwazChitra_HI')
        if '_KKS_Hi' in zip_basename:
            zip_basename = zip_basename.replace('_KKS_Hi', '_KKS_HI')
        # Mar 2: more edge cases where zip filename doesn't match folder name inside it
        if 'Memorygamekb' in zip_basename:
            zip_basename = zip_basename.replace('Memorygamekb', 'MemoryGamekb')
        if 'cityofstories' in zip_basename:
            zip_basename = zip_basename.replace('cityofstories', 'CityOfStories')
        # Jun 12: fix more edge cases where .zip filename doesn't match dir name
        if '_KKS_Gj' in zip_basename:
            zip_basename = zip_basename.replace('_KKS_Gj', '_KKS_GJ')
        if 'ShabdKhel' in zip_basename:
            zip_basename = zip_basename.replace('ShabdKhel', 'Shabdkhel')

        zip_folder = os.path.join(destpath, zip_basename)  # e.g. destpath/Mathematics/
        main_file = main_file.split('/')[-1]               # e.g. activity_name.html or index.html

        if 'KhelbadiKahaniyan_MR' in zip_basename:
            # Inconsistency --- `main_file` contains dir name, and not index.html
            main_file = 'index.html'

        # Jul 8th: handle weird case-insensitive webserver main_file
        if main_file == 'mainexpand.html':
            main_file = 'mainExpand.html'  # <-- this is the actual filename in the zip

        # Zip files from Pratham website have the web content inside subfolder
        # of the same as the zip filename. We need to recreate these zip files
        # to make sure the index.html is in the root of the zip.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            # If main_file is in the root (like zips from the game repository)
            # then we need to extract the zip contents to subfolder zip_basename/
            for zfileinfo in zf.filelist:
                if zfileinfo.filename == main_file:
                    destpath = os.path.join(destpath, zip_basename)
            # Extract zip so main file will be in destpath/zip_basename/index.html
            zf.extractall(destpath)

        # In some cases, the files are under the www directory,
        # let's move them up one level.
        www_dir = os.path.join(zip_folder, 'www')
        if os.path.isdir(www_dir):
            files = os.listdir(www_dir)
            for f in files:
                shutil.move(os.path.join(www_dir, f), zip_folder)

        # Rename `main_file` to index.html
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'index.html')
        os.rename(src, dest)

        # Logic to add margin-top:44px; for games that match Corrections tab
        add_margin_top = False
        for row in PRADIGI_CORRECTIONS_LIST:
            if row[CORRECTIONS_ACTION_KEY] == ADD_MARGIN_TOP_ACTION:
                pat = row[CORRECTIONS_SOURCE_URL_PAT_KEY]
                m = pat.match(zip_file_url)
                if m:
                    add_margin_top = True
        if add_margin_top:
            if zip_file_url.endswith('CourseContent/Games/Mathematics.zip'):
                LOGGER.info("adding body.margin-top:44px; to ALL .html files in: %s" % zip_file_url)
                for root, dirs, files in os.walk(zip_folder):
                    for file in files:
                        if file.endswith(".html"):
                            add_body_margin_top(root, file)
            else:
                LOGGER.info("adding body.margin-top:44px; to index.html in: %s" % zip_file_url)
                add_body_margin_top(zip_folder, 'index.html')

        # Replace occurences of `main_file` with index.html to avoid broken links
        for root, dirs, files in os.walk(zip_folder):
            for file in files:
                if file.endswith(".html") or file.endswith(".js"):
                    file_path = os.path.join(root, file)
                    # use bytes to avoid Unicode errors "invalid start/continuation byte"
                    bytes_in = open(file_path, 'rb').read()
                    bytes_out = bytes_in.replace(main_file.encode('utf-8'), b'index.html')
                    open(file_path, 'wb').write(bytes_out)

        # create the zip file and copy it to 
        tmp_predictable_zip_path = create_predictable_zip(zip_folder)
        shutil.copyfile(tmp_predictable_zip_path, final_webroot_path)
        return final_webroot_path

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

        # Rename main_file to phetindex.html
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
        LOGGER.error("get_phet_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file_and_query, destpath, e))
        return None



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


# NOT USED RIGHT NOW --- getting all website resources instead.
# Use blacklist approach in Corrections if you want to ignore/skip specific resource.
#
# def _only_videos(node):
#     """
#     Set this as the `filter_fn` to `wrt_to_ricecooker_tree` to select only videos.
#     """
#     allowed_kinds = ['lang_page', 'topic_page', 'subtopic_page', 'lesson_page',
#                      'fun_page', 'story_page', 'PrathamVideoResource']
#     return node['kind'] in allowed_kinds


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

    # load gamrewpo game infos
    # gamerepo_data = json.load(open('chefdata/trees/pradigi_games_all_langs.json','r'))
    # assert gamerepo_data["kind"] == "index_page", 'wrong web resource tree loaded'

    games = []
    # game_source_ids = []
    #
    # First try to get game from website_games json by title_en (ignoring _LANG suffixes)
    for game_resource in website_data_lang:
        title = game_resource['title_en']
        for suffix in suffixes:
            if title.strip().endswith(suffix):
                title = title.replace(suffix, '').strip()
        if name == title:
            # source_id = game_resource['source_id']
            if len(games) == 0:
                games.append(game_resource)
                # game_source_ids.append(source_id)
        else:
            if game_resource['title_en'].startswith(name):
                print('>>>>> skipping game_resource', game_resource, 'even though it is similar', name, 'in lang', lang)

    if len(games) == 0:
        pass
        # print('game', name, 'not found for lang', lang)

    return games

    # if len(games) == 0:
    #     # Get game from pradigi_games json by ignoring _LANG suffixes
    #     for gameslang_page in gamerepo_data['children']:
    #         if gameslang_page['language_en'] == language_en:
    #             for game in gameslang_page['children']:
    #                 title = game['title']
    #                 for suffix in suffixes:
    #                     if title.strip().endswith(suffix):
    #                         title = title.replace(suffix, '').strip()
    #                 if name == title:
    #                     source_id = game['title']
    #                     if len(games) == 0:
    #                         games.append(game)
    #                         # game_source_ids.append(source_id)
    # 
    # if take_from is not None and len(games) == 0:
    #     # Extra pass to get English games to be included in other languages
    #     take_lang = LANGUAGE_EN_TO_LANG[take_from]
    #     take_suffixes = PRADIGI_STRINGS[take_lang]['gamesrepo_suffixes']
    #     take_suffixes = take_suffixes*2
    #     for gameslang_page in gamerepo_data['children']:
    #         if gameslang_page['language_en'] == take_from:
    #             for game in gameslang_page['children']:
    #                 title = game['title']
    #                 for suffix in take_suffixes:
    #                     if title.strip().endswith(suffix):
    #                         title = title.replace(suffix, '').strip()
    #                 if name == title and len(games) == 0:
    #                     games.append(game)
    #                     # game_source_ids.append(source_id)




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
    Extracts all games from the normal web resource tree so they can be
    deduplicated with gamerepo games and manually placed within subject folders.
    Modifies tree in place + returns `website_games` (list) for given `lang`.
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
            # DISABLE subtree['children'] = new_children
            #
            # recurse
            for child in subtree['children']:
                recursive_extract_website_games(child)
    recursive_extract_website_games(web_resource_tree)
    # DISABLE WRITOUT
    # DISABLE with open(wrt_filename, 'w') as wrt_file:
    # DISABLE     json.dump(web_resource_tree, wrt_file, ensure_ascii=False, indent=2, sort_keys=True)
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

        return lang_subtree


    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel
        """
        LOGGER.info('in pre_run...')

        if args['update']:
            LOGGER.info('Deleting all zips in cache dir {}'.format(HTML5APP_ZIPS_LOCAL_DIR))
            for rel_path in os.listdir(HTML5APP_ZIPS_LOCAL_DIR):
                abs_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, rel_path)
                if os.path.isdir(abs_path):
                    shutil.rmtree(abs_path)

        if 'nocrawl' not in options:
            self.crawl(args, options)

        ricecooker_json_tree = dict(
            title='PraDigi',
            source_domain=PRADIGI_DOMAIN,
            source_id='pradigi-videos-and-games',
            description=PRADIGI_DESCRIPTION,
            thumbnail='chefdata/prathamlogo_b01-v1.jpg',
            language='mul',   # Using mul as top-level language because mixed content
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

