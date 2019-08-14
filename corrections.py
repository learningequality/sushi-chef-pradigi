import csv
import logging
import re
import requests

from ricecooker.config import LOGGER

from structure import _clean_dict

LOGGER.setLevel(logging.DEBUG)



# CORRECTIONS = Excel sheet to edit or specify correction tasks
################################################################################
GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
PRADIGI_SHEET_ID = '1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg'
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


