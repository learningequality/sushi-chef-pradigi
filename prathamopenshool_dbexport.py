from collections import defaultdict
import json
import os
import pickle
import pyodbc
import yaml
from itertools import groupby
from operator import itemgetter



from chef import FULL_DOMAIN_URL, PRADIGI_STRINGS


PRADIGI_DB_LANGS = [
    'Hindi',
    'Marathi',
    'Kannada',
    'Assamese',
    'Bengali',
    'Gujarati',
    'Odia',
    'Punjabi',
    'Tamil',
    'Telugu',
    'Urdu',
    'English',
]




# DATABASE
#########################################################################################

# Reading API credentials from parameters.yml
with open("credentials/parameters.yml", "r") as f:
    parameters = yaml.load(f)
    dbparams = parameters['database']

cnxn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    + "Server={};".format(dbparams['Server']) \
    + "Database={};".format(dbparams['Database']) \
    + "uid={};".format(dbparams['uid']) \
    + "pwd={}".format(dbparams['pwd'])
)
db = cnxn.cursor()

def dbex(query):
    """
    Execure a DB query and return results as a list of dicts.
    Usage:
        rows = dbex("SELECT * FROM CntCategory;")
        print(len(rows))
        rows[71]
    """
    print('Running DB query', query)
    cursor = db.execute(query)
    results = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    #
    # Note: this code is useful becuase Database contains \r\n in certain fields...
    clean_results = []
    for result in results:
        clean_result = {}
        for k, v in result.items():
            if isinstance(v, str):
                clean_result[k] = v.strip()
            else:
                clean_result[k] = v
        clean_results.append(clean_result)
    return clean_results


def load_data():
    DB_CACHE_DIR = 'dbcache'
    db_cache_path = os.path.join(DB_CACHE_DIR, 'prathamopenschool_db.pickle')
    if os.path.exists(db_cache_path):
        print("Loaded cached DB data from", db_cache_path)
        dbc = pickle.load( open(db_cache_path, "rb" ) )
        return dbc
    else:
        # Get entire DB contents as rows of dicts
        category_rows = dbex("SELECT * FROM CntCategory;")
        course_rows = dbex("SELECT * FROM CntCourse;")
        courselesson_rows = dbex("SELECT * FROM CntCourseLession;")
        lesson_rows = dbex("SELECT * FROM CntLession;")
        lessonresources_rows = dbex("SELECT * FROM CntLessionResource;")
        resource_rows = dbex("SELECT * FROM CntResource;")
        dbc = dict(
            category_rows = category_rows,
            course_rows = course_rows,
            courselesson_rows = courselesson_rows,
            lesson_rows = lesson_rows,
            lessonresources_rows = lessonresources_rows,
            resource_rows = resource_rows,
        )
        pickle.dump(dbc, open(db_cache_path, "wb" ) )
        return dbc

dbc = load_data()
category_rows = dbc['category_rows']
course_rows = dbc['course_rows']
courselesson_rows = dbc['courselesson_rows']
lesson_rows = dbc['lesson_rows']
lessonresources_rows = dbc['lessonresources_rows']
resource_rows = dbc['resource_rows']



# BASIC ORM
#########################################################################################

def dbfilter(rows, **kwargs):
    """
    Return all the `rows` that match the `key=value` conditions, where keys are DB column
    names and value is a row's value.
    """
    selected = []
    for row in rows:
        accept = True
        for key, value in kwargs.items():
            if key not in row or row[key] != value:
                accept = False
        if accept:
            selected.append(row)
    return selected

def filter_key_in_values(rows, key, values):
    """
    Return all the `rows` whose value for `key` is in the list `values`.
    """
    if isinstance(values, str):
        values = [values]
    return list(filter(lambda r: r[key] in values, rows))



def dbget(rows, **kwargs):
    """
    Return all the `rows` that match the `key=value` conditions, where keys are DB column
    names and value is a row's value.
    """
    selected = dbfilter(rows, **kwargs)
    assert len(selected) < 2, 'mulitple results found'
    if selected:
        return selected[0]
    else:
        return None

def dbvalues_list(rows, *args, flat=False):
    results = []
    for row in rows:
        result = []
        for arg in args:
            result.append(row[arg])
        results.append(result)
    if flat:
        return [result[0] for result in results]
    else:
        return results




def sane_group_by(items, key):
    """
    Wrapper for itertools.groupby to make it easier to use.
    Returns a dict with keys = possible values of key in items
    and corresponding values being lists of items that have that key.
    """
    sorted_items = sorted(items, key=itemgetter(key))
    return dict((k, list(g)) for k, g in groupby(sorted_items, key=itemgetter(key)))





# TABLE OF CONTENTS
#########################################################################################


PRADIGI_CATEGORIES = [
    'Mathematics',
    # 'Language' = games-only topic added manually while contructing the ricecooker tree
    'English',
    'Science',
    # special handline for 'Health', --- implemented as gamelist/ URL
    # special handline for 'Sports', --- implemented as gamelist/ URL
    # Fun = special resources with fun=yes      -- generated by using DB queries
    # Story = special resources with story=yes  -- generated by using DB queries
    #
    # Special hanling for links in the 'Game' menu: three subtopics implemented as gamelist/ URLs
    # - "KhelBadi": "खेळ-वाडी" 3-6 years old only (flatlist)
    # - "WatchAndDo": "बघा आणि शिका" 3-6 years old only, group by lesson
    # - "KhelPuri": "खेळ-पुरी", 6-20 years old only (flatlist)
    #
    # vocational stuff shown for 14+ only
    'Hospitality',
    'Automobile',
    'Beauty',
    'Electric',
    'Healthcare',
    'Construction',
]


def get_subtree_for_subject(lang, subject_en):
    """
    Returns subtree of data resources for subject `subject_en` in language `lang`.
    """
    language_en = PRADIGI_STRINGS[lang]['language_en']
    assert language_en in PRADIGI_DB_LANGS, 'Wrong language name found'
    if 'website_lang' in PRADIGI_STRINGS[lang]:
        website_lang = PRADIGI_STRINGS[lang]['website_lang']
    else:
        website_lang = lang

    # Prepare result dict....
    subtree = dict(
        lang=lang,
        language_en=language_en,
        subject_en=subject_en,
        children = [],
    )

    # Handle special cases of Fun and Story
    if subject_en == 'Fun':
        subtree["kind"] = "fun_page"
        subtree["source_id"] = "Fun"
        subtree["title"] = PRADIGI_STRINGS[lang]['subjects'].get('Fun', 'Fun')
        subtree["url"] = FULL_DOMAIN_URL + '/' + website_lang + '/Fun'
        lang_resource_rows = dbfilter(resource_rows, lang_name=language_en)
        if lang_resource_rows:
            funs = filter_key_in_values(lang_resource_rows, 'fun', ['yes', 'Yes'])
            subtree['children'] = funs
        else:
            return None

    elif subject_en == 'Story':
        subtree["kind"] = "story_page"
        subtree["source_id"] = "Story"
        subtree["title"] = PRADIGI_STRINGS[lang]['subjects'].get('Story', 'Story')
        subtree["url"] = FULL_DOMAIN_URL + '/' + website_lang + '/Story'
        lang_resource_rows = dbfilter(resource_rows, lang_name=language_en)
        if lang_resource_rows:
            stories = dbfilter(lang_resource_rows, course_source='Story')
            subtree['children'] = stories
        else:
            return None
    
    # Handle games specially
    elif subject_en in ['KhelBadi', 'WatchAndDo', 'KhelPuri']:
        if not PRADIGI_STRINGS[lang]['course_ids_by_subject_en']:
            return None
        course_id = PRADIGI_STRINGS[lang]['course_ids_by_subject_en'][subject_en]
        course_dict = get_subtree_for_course(lang, course_id)
        subtree.update(course_dict)
        subtree['url'] = FULL_DOMAIN_URL + '/' + website_lang + '/gamelist/' + course_id

    # Handle Sprots and Health specially
    elif subject_en in ['Sports', 'Health']:
        category = dbget(category_rows, cat_name=subject_en, cat_lang=language_en)
        if category is None:
            return None
        courses = dbfilter(course_rows, cat_id=category['cat_id'])
        if courses:
            assert len(courses) < 2, 'too many courses found---assuming Sports and Health have single course in them'
            course = courses[0]
            course_id = course['course_id']
            course_dict = get_subtree_for_course(lang, course_id)
            subtree.update(course_dict)
            subtree['url'] = FULL_DOMAIN_URL + '/' + website_lang + '/gamelist/' + course_id
        else:
            return None

    # Handle generic subjects by returning all children in the category with this name
    elif subject_en in PRADIGI_CATEGORIES:
        
        # special handling for Urdu cat_name=Angrezi instead of cat_name=English
        if subject_en in PRADIGI_STRINGS[lang]['course_ids_by_subject_en']:
            category_name = PRADIGI_STRINGS[lang]['course_ids_by_subject_en'][subject_en]
        else:
            category_name = subject_en  # for all langs except Urdu, cat_name==subject_en
        category = dbget(category_rows, cat_name=category_name, cat_lang=language_en)
        subtree['url'] = FULL_DOMAIN_URL + '/' + website_lang + '/Course/' + category_name
        subtree["kind"] = "topic_page"
        subtree["source_id"] = category_name
        subtree["title"] = PRADIGI_STRINGS[lang]['subjects'].get(subject_en, subject_en)
        if category:
            courses = dbfilter(course_rows, cat_id=category['cat_id'])
            for course in courses:
                course_id = course['course_id']
                course_dict = get_subtree_for_course(lang, course_id)
                if course_dict:
                    subtree['children'].append(course_dict)
        else:
            return None

    else:
        raise ValueError('Unknown subject_en', subject_en, 'for lang', lang)

    return subtree


def get_subtree_for_course(lang, course_id):
    course = dbget(course_rows, course_id=course_id)
    course["title"] = course['course_name']
    course["language"] = lang
    course["source_id"] = course['course_id']
    return course



def get_toc_for_lang(lang):
    language_en = PRADIGI_STRINGS[lang]['language_en']
    assert language_en in PRADIGI_DB_LANGS, 'Wrong language name found'



# for language_en in PRADIGI_DB_LANGS:
#     print("Active content for", language_en)
#     db_tree = {}
# 
#     # COURSES
#     active_course_rows = filter_key_in_values(course_rows, 'isactive', ['Yes', 'yes'])
#     lang_course_rows = dbfilter(active_course_rows, lang_name=language_en)
# 
#     # GROUP BY CATEGORYCRS128
#     for cat_id, courses in sane_group_by(lang_course_rows, 'cat_id').items():
#         cat = dbget(category_rows, cat_id=cat_id)
#         if cat['isactive'] == 'Yes':
#             print('  = ', 'Category', cat['cat_id'], cat['cat_name'], cat['isactive'] )
#             for course in courses:
#                 print('     - ', course['course_id'], course['course_name'])
#                 courselessons = dbfilter(courselesson_rows, course_id=course['course_id'])
#                 lession_ids = dbvalues_list(courselessons, 'lession_id', flat=True)
#                 for lession_id in lession_ids:
#                     lesson = dbget(lesson_rows, lession_id=lession_id)
#                     print('        *', lesson['lession_id'], lesson['lession_name'], 'publish='+str(lesson['publish']), 'fun='+str(lesson['fun']), 'know='+str(lesson['know'])) 
#         else:
#             pass
#             # print('   ', 'Skipping', cat['cat_name'], cat['isactive'] )
#     print('\n')
# 
















# EXPLORE/DEBUG HELPERS
#########################################################################################

# rows = db.execute("SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE';")
# for row in rows:
#     print(row)


def count_values_for_attr(resources, *attrs):
    counts = {}
    for attr in attrs:
        counts[attr] = defaultdict(int)
        for resource in resources:
            val = resource[attr]
            counts[attr][val] += 1
    return counts




# REUSED FROM OLD CRAWLER SCRIPT
#########################################################################################

def get_video_metadata(self, video_url):
    """
    Make HEAD request to obtain 'content-length' for video files
    """
    head_response = request.head(video_url)
    if head_response:
        video_metadata = {}
        content_type = head_response.headers.get('content-type', None)
        if content_type:
            video_metadata['content-type'] = content_type
        content_length = head_response.headers.get('content-length', None)
        if content_length:
            video_metadata['content-length'] = content_length
        return video_metadata
    else:
        return {}

