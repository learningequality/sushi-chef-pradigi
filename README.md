PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.

TODO
  - why are videos and games not being crawled from here? http://www.prathamopenschool.org/mr/gamelist/CRS125
  - triage new games https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=975191127
  - design tree building logic
    - hi and mr
    - english
    - other


Install
-------

    # 1. codes
    cd /data
    git clone https://github.com/learningequality/sushi-chef-pradigi.git
    cd sushi-chef-pradigi/
    
    # 2. pythons
    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt
    
    # 3. phantoms
    wget https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2
    tar -xjf phantomjs-2.1.1-linux-x86_64.tar.bz2
    rm phantomjs-2.1.1-linux-x86_64.tar.bz2



Running
-------

    ssh chef@vader
        cd sushi-chef-pradigi
        export PHANTOMJS_PATH=/data/sushi-chef-pradigi/phantomjs-2.1.1-linux-x86_64/bin/phantomjs
        source venv/bin/activate
        nohup ./chef.py -v --reset --thumbnails --token=<your_token> &

Use the `--update` option to force re-downloading all files and clear the local
cache directory of zip files (`chefdata/zipfiles`).



Future Updates
--------------
  - Revisit when games with Android API fixed
  - Revisit when missing English games added
  - Optional: load string translations for all languages from shared spreadsheet (not needed right now)





Content Merging Design
----------------------

New excel structure with "source info" columns
  - Resource Type
  - Web Folder
  - Game Name (instead of Name and Name on gamerepo (before lang underscore)
  - Take From Repo

Destination columns:
  - Use Only In
  - Age Group	
  - Subject

This will allow for many Web Folder to one dest. folder mapping.
Use case: get games from all three folders:
  - "CRS122": "खेल-बाड़ी",      # Playground
  - "CRS124": "देखो और करों",   # Look and
  - "CRS123": "खेल-पुरी",       # Games

