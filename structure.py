import csv
from itertools import groupby
from operator import itemgetter


import logging
import requests

from ricecooker.config import LOGGER

from le_utils.constants import content_kinds

LOGGER.setLevel(logging.DEBUG)

# NEW VOCATIONAL STRUCTURE
################################################################################

LANGS_WITH_NEW_VOCATIONAL_STRUCTURE = ['mr']
VOCATIONAL_SUBJECTS = [
    'Hospitality',
    'Automobile',
    'Beauty',
    'Electric',
    'Healthcare',
    'Construction',
    'Financial Literacy',
    '14_To_18',
]



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
    'Vocational',  # new top-level menu that includes all others in MR only
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
    'DekhiyeaurKariye',   # only for urdu same as khelpuri but needs to be in 3-6
    'Recipe',             # for marathi 8-14
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



