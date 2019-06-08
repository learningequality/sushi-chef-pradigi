import os

from fabric.api import env, task, local, sudo, run, get
from fabric.contrib.files import exists
from fabric.context_managers import cd, prefix, show, hide, shell_env
from fabric.colors import red, green, blue, yellow
from fabric.utils import puts

env.hosts = [
    'eslgenie.com:1',  # vader runs ssh on port 1
]
env.user = os.environ.get('USER')
env.password = os.environ.get('SUDO_PASSWORD')
env.timeout = 100

STUDIO_TOKEN = os.environ.get('STUDIO_TOKEN')



CHEF_USER = 'chef'
CHEF_REPO_URL = 'https://github.com/learningequality/sushi-chef-pradigi.git'
GIT_BRANCH = 'master'
CHEFS_DATA_DIR = '/data'
CHEF_PROJECT_SLUG = 'sushi-chef-pradigi'
CHEF_DATA_DIR = os.path.join(CHEFS_DATA_DIR, CHEF_PROJECT_SLUG)


STUCTURE_CACHE_FILENAME = 'pradigi_structure.csv'
ENGLISH_STUCTURE_CACHE_FILENAME = 'pradigi_english_structure.csv'
CORRECTIONS_CACHE_FILENAME = 'pradigi_corrections.csv'
WEBSITE_GAMES_JSON_FILENAME = 'website_games_all_langs.json'
CRAWLING_STAGE_OUTPUT_TMPL = 'pradigi_{}_web_resource_tree.json'
SCRAPING_STAGE_OUTPUT = 'pradigi_ricecooker_json_tree.json'
from chef import PRADIGI_WEBSITE_LANGUAGES



# RUN CHEF
################################################################################

@task
def run_pradigi():
    with cd(CHEF_DATA_DIR):
        with prefix('source ' + os.path.join(CHEF_DATA_DIR, 'venv/bin/activate')):
            with shell_env(STUDIO_URL="http://develop.studio.learningequality.org",
                           PHANTOMJS_PATH="/data/sushi-chef-pradigi/phantomjs-2.1.1-linux-x86_64/bin/phantomjs"):
                cmd = 'nohup ./chef.py  -v --reset --stage --token={} crawlonly=t &'.format(STUDIO_TOKEN)
                output = sudo(cmd, user=CHEF_USER)
                print(output.stdout)


# GET RUN TREE OUTPUTS
################################################################################

@task
def get_trees(langs='all'):
    chefdata_dir = os.path.join(CHEF_DATA_DIR, 'chefdata')
    trees_dir = os.path.join(CHEF_DATA_DIR, 'chefdata', 'trees')
    local_dir = os.path.join('chefdata', 'vader', 'trees')
    if langs == 'all':
        langs = PRADIGI_WEBSITE_LANGUAGES
    # crawling trees
    for lang in langs:
        web_resource_tree_filename = CRAWLING_STAGE_OUTPUT_TMPL.format(lang)
        get(os.path.join(trees_dir, web_resource_tree_filename),
            os.path.join(local_dir, web_resource_tree_filename))

    # website games
    get(os.path.join(trees_dir, WEBSITE_GAMES_JSON_FILENAME),
        os.path.join(local_dir, WEBSITE_GAMES_JSON_FILENAME))
    

    # structure
    structure_filename = STUCTURE_CACHE_FILENAME
    get(os.path.join(chefdata_dir, structure_filename),
        os.path.join(local_dir, structure_filename))
    english_structure_filename = ENGLISH_STUCTURE_CACHE_FILENAME
    get(os.path.join(chefdata_dir, english_structure_filename),
        os.path.join(local_dir, english_structure_filename))

    # corrections
    corrections_filename = CORRECTIONS_CACHE_FILENAME
    get(os.path.join(chefdata_dir, corrections_filename),
        os.path.join(local_dir, corrections_filename))

    # ricecooker tree
    ricecooker_json_tree_filename = SCRAPING_STAGE_OUTPUT
    get(os.path.join(trees_dir, ricecooker_json_tree_filename),
        os.path.join(local_dir, ricecooker_json_tree_filename))



# CLEAR CACHES
################################################################################

@task
def clear_caches(zipfiles='False'):
    zipfiles = (zipfiles == 'True' or zipfiles == 'true')  # defaults to False
    with cd(CHEF_DATA_DIR):
        sudo('rm -rf cache.sqlite')
        sudo('rm -rf prathamopenshcool_org.sqlite')
        sudo('rm -rf .webcache')
        if zipfiles:
            sudo('rm -rf chefdata/zipfiles')


# SETUP
################################################################################

@task
def setup_chef():
    with cd(CHEFS_DATA_DIR):
        sudo('git clone  --quiet  ' + CHEF_REPO_URL)
        sudo('chown -R {}:{}  {}'.format(CHEF_USER, CHEF_USER, CHEF_DATA_DIR))
        # setup python virtualenv
        with cd(CHEF_DATA_DIR):
            sudo('virtualenv -p python3.5  venv', user=CHEF_USER)
        # install requirements
        activate_sh = os.path.join(CHEF_DATA_DIR, 'venv/bin/activate')
        reqs_filepath = os.path.join(CHEF_DATA_DIR, 'requirements.txt')
        # Nov 23: workaround____ necessary to avoid HOME env var being set wrong
        with prefix('export HOME=/data && source ' + activate_sh):
            sudo('pip install --no-input --quiet -r ' + reqs_filepath, user=CHEF_USER)
        puts(green('Cloned chef code from ' + CHEF_REPO_URL + ' in ' + CHEF_DATA_DIR))

@task
def unsetup_chef():
    sudo('rm -rf  ' + CHEF_DATA_DIR)
    puts(green('Removed chef direcotry ' + CHEF_DATA_DIR))




# GIT-BASED DEPLOYMENT
################################################################################

@task
def git_fetch():
    with cd(CHEF_DATA_DIR):
        sudo('git fetch origin  ' + GIT_BRANCH, user=CHEF_USER)

@task
def update():
    git_fetch()
    with cd(CHEF_DATA_DIR):
        sudo('git checkout ' + GIT_BRANCH, user=CHEF_USER)
        sudo('git reset --hard origin/' + GIT_BRANCH, user=CHEF_USER)
    # update requirements
    activate_sh = os.path.join(CHEF_DATA_DIR, 'venv/bin/activate')
    reqs_filepath = os.path.join(CHEF_DATA_DIR, 'requirements.txt')
    with prefix('export HOME=/data && source ' + activate_sh):
        sudo('pip install -U --no-input --quiet -r ' + reqs_filepath, user=CHEF_USER)

