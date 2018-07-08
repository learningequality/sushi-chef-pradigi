PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


Fixes TODO
----------
  - Exclude list for games for HI and MR web resources to avoid duplication (prefer gamerepo versions)
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

  - Skip from Marathi Channel
    http://pradigi-demo.learningequality.org/learn/#/topics/t/3ef03910a8a55edf9965f65bcedfa42c
    Channels PraDigi मराठी 8-14 years English अंग्रेजी ओके प्लीज 
    http://pradigi-demo.learningequality.org/learn/#/topics/t/a0978c1842e953938453895ae77197d4
    ChannelsPraDigiमराठी14 and aboveEnglish



TODO
----
  - load string translations for all languages from shared spreadsheet
  - Create temp zip files under chefdata/ instead of /tmp (make sure files identical so no re-upload)
  - Add 'All Resources' and change logic (might be needed to skip games from Fun/ page)
  - Clairfy and handle English- Hindi edge case

      Unknown resource type English- Hindi in row {'Name': None, 'Pratham': None, 'Subject': 'English', 'Age Group': '14 and above', 'Take From Repo': None, 'Name on gamerepo (before lang underscore)': None, 'LE Comments': 'What does "English- Hindi" refer to?', 'Resource Type': 'English- Hindi'}

  - What is wrong with this one: http://studio.learningequality.org/channels/f9da12749d995fa197f8b4c0192e7b2c/view/1dd158c/5b37112

        Failed to load resource: the server responded with a status of 404 (Not Found)
        NumberScript.js Failed to load resource: the server responded with a status of 404 (Not Found)
        NumberData.js Failed to load resource: the server responded with a status of 404 (Not Found)
        NumberScript.js Failed to load resource: the server responded with a status of 404 (Not Found)
        NumberData.js Failed to load resource: the server responded with a status of 404 (Not Found)


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

