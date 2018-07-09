PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


Fixes TODO
----------
  - Add 'All Resources' and change logic (might be needed to skip games from Fun/ page)

  - Investigate what is wrong with the localStorage errors in the translation games
    `Uncaught DOMException: Failed to read the 'localStorage' property from 'Window':`
    `The document is sandboxed and lacks the 'allow-same-origin' flag.`
    - http://www.prathamopenschool.org/CourseContent/Games/TranslateHindiEnglish.zip
    - http://www.prathamopenschool.org/CourseContent/Games/TranslateHindiEnglishLevel2.zip
    - http://www.prathamopenschool.org/CourseContent/Games/TranslateHindiEnglishLevel3.zip
    - http://www.prathamopenschool.org/CourseContent/Games/TranslateHindiEnglishLevel4.zip
    - http://www.prathamopenschool.org/CourseContent/Games/TranslateMarathiToEnglish.zip

  - Exclude list for games for HI and MR web resources to avoid duplication (prefer gamerepo versions)
    - Doesn't seem to be much overlap, so will do this later if needed

  - Add two folders under English channel, under English subject folder
  - 8-14 years and 14 and above years

    - English
      - 8-14 years
        - English
          - For Hindi Speakers
            http://pradigi-demo.learningequality.org/learn/#/topics/t/c739f6c5680054d1b11b24529eae6277
            http://pradigi-demo.learningequality.org/learn/#/topics/t/ab9abf5c6d3952ff8efb5f8b4903e0ef

          - For Marathi speakers
            http://pradigi-demo.learningequality.org/learn/#/topics/t/3e010574571d56408053f9c24aa296ce


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

