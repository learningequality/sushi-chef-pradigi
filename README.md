PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


Fixes TODO
----------
  - Add 'All Resources' and change logic (might be needed to skip games from Fun/ page)

  - Exclude list for games for HI and MR web resources to avoid duplication (prefer gamerepo versions)
    - Doesn't seem to be much overlap, so will do this later if needed

  - load string translations for all languages from shared spreadsheet (not needed)


Install
-------

    git clone https://github.com/learningequality/sushi-chef-pradigi.git
    cd sushi-chef-pradigi/
    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt
    #npm install phantomjs-prebuilt  # needed for scraping gamerepo
    # wget phantomjs...


Running
-------

    ssh chef@vader
      cd sushi-chef-pradigi
      export PHANTOMJS_PATH=/data/sushi-chef-pradigi/phantomjs-2.1.1-linux-x86_64/bin/phantomjs
      source venv/bin/activate
      nohup ./chef.py -v --reset --thumbnails --token=<your_token> &

Use the `--update` option to force re-downloading all files and clear the local
cache directory of zip files (`chefdata/zipfiles`).

