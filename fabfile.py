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
env.password = os.environ.get('VADER_PASSWORD')

STUDIO_TOKEN = os.environ.get('STUDIO_TOKEN')



CHEF_USER = 'chef'
CHEF_REPO_URL = 'https://github.com/fle-internal/sushi-chef-pratham-open-school.git'
GIT_BRANCH = 'master'
CHEFS_DATA_DIR = '/data'
CHEF_PROJECT_SLUG = 'sushi-chef-pratham-open-school'
CHEF_DATA_DIR = os.path.join(CHEFS_DATA_DIR, CHEF_PROJECT_SLUG)

CRAWLING_STAGE_OUTPUT = 'web_resource_tree.json'
SCRAPING_STAGE_OUTPUT = 'ricecooker_json_tree.json'


@task
def chef_info():
    with cd(CHEF_DATA_DIR):
        sudo("ls")
        sudo("whoami")
        run("ls")
        run("whoami")



# RUN CHEF
################################################################################

@task
def run_pradigi(debug="False", lang='hn'):
    if debug == "False":
        debug_str = ''
    else:
        debug_str = 'debug=T'

    with cd(CHEF_DATA_DIR):
        with prefix('source ' + os.path.join(CHEF_DATA_DIR, 'venv/bin/activate')):
            cmd = './chef.py  -v --reset --token={} language={} '.format(STUDIO_TOKEN, lang)
            cmd += debug_str
            sudo(cmd, user=CHEF_USER)



# GET RUN TREE OUTPUTS
################################################################################

@task
def get_trees(lang='all'):
    trees_dir = os.path.join(CHEF_DATA_DIR, 'chefdata', 'trees')
    local_dir = os.path.join('chefdata', 'vader', 'trees')
    web_resource_tree_filename = CRAWLING_STAGE_OUTPUT
    ricecooker_json_tree_filename = SCRAPING_STAGE_OUTPUT
    get(os.path.join(trees_dir, web_resource_tree_filename),
        os.path.join(local_dir, web_resource_tree_filename))
    get(os.path.join(trees_dir, ricecooker_json_tree_filename),
        os.path.join(local_dir, ricecooker_json_tree_filename))



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

