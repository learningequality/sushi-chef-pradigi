PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.

Design
------
This chef combines data from both the prathamopenschool.org website and the gamerepo:
  - Hindi
    - mix of website resource and games (games taken from website preferentially)
    - some extra vocational material taken from youtube playlists
  - Marathi
    - mix of website resource and games (games taken from website preferentially)
  - English and other languages
    - games taken from gamerepo

The following google spreadhseet are used to determine placement of content nodes within the channel:
  - English https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=1812185465
  - All other languages https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=342105160

The following corrections are applied to content before uploading to Kolibri:
https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=93933238




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
  - Game Name instead of Name on gamerepo (before lang underscore)
  - Get full game namelist
  - Extract known games from webpage
  - Combine tree
    - web resources
    - pyalysts
    - games from (website > repo > take from lang in repo)
  - Manually add special CRS folders [TODO]




TODO
----

Check what's wrong with these:

```

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_Hi/index.html', 'kind': 'PrathamZipResource', 'title': 'भालू की बारहखड़ी', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/RES5609.png', 'children': [], 'source_id': 'hn/game/5609', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_Hi.zip', 'title_en': 'BhalooKiBarakhadi_KKS_Hi', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_Hi.zip'}

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_MR/index.html', 'kind': 'PrathamZipResource', 'title': 'भभलू ची बाराखडी', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/BhalooKiBarakhadi_KKS_MR.png', 'children': [], 'source_id': 'mr/game/7431', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_MR.zip', 'title_en': 'BhalooKiBarakhadi_KKS_MR', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/BhalooKiBarakhadi_KKS_MR.zip'}

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M/CoverPage.html', 'kind': 'PrathamZipResource', 'title': 'या चित्रात दडलंय काय?', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/RES1113.png', 'children': [], 'source_id': 'mr/FunResource/1113', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M.zip', 'title_en': 'JigsawGame_M', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M.zip'}

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M/CoverPage.html', 'kind': 'PrathamZipResource', 'title': 'या चित्रात दडलंय काय?', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/RES1113.png', 'children': [], 'source_id': 'mr/FunResource/1113', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M.zip', 'title_en': 'JigsawGame_M', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/JigsawGame_M.zip'}In main loop lang=mr age_group=8-14 years subject_en=Mathematics

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_HI/index.html', 'kind': 'PrathamZipResource', 'title': 'उलट पलट', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/UlatpalatCover.png', 'children': [], 'source_id': 'hn/game/3524', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_HI.zip', 'title_en': 'UlatPalat_HI', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_HI.zip'}

>>>>> skipping game_resource {'main_file': 'http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_MR/index.html', 'kind': 'PrathamZipResource', 'title': 'उलट पलट', 'thumbnail_url': 'http://www.prathamopenschool.org/CourseContent/coverImages/RES4080.png', 'children': [], 'source_id': 'mr/game/4080', 'description': 'source_url=http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_MR.zip', 'title_en': 'UlatPalat_MR', 'url': 'http://www.prathamopenschool.org/CourseContent/Games/UlatPalat_MR.zip'}
skipping <a class="dropdown-toggle" data-toggle="dropdown" href="#" style="background: transparent;">

```


- Cross check games on website http://www.prathamopenschool.org/CourseContent/Games/
  vs combined list of games from gamerepo
