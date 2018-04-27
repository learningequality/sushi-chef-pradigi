PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


Fixes TODO
----------




TODO
----
  - Get game thumbnails from
    http://www.prodigi.openiscool.org/repository/Images/AwazPehchano_KN.png
  - get subject strings for all other languages (shared spreadsheet workflow)
  - Handle `PrathamHtmlResource` resources
  - Exclude games from HI and MR web resources to avoid duplication (prefer gamerepo versions)
  - Get English games from English repo
  - Create temp zip files under chefdata/ instead of /tmp (make sure files identical so no re-upload)
  - Handle English Resources uses in other langauges
  
      [eslgenie.com:1] out: Unknown resource type English- Hindi in row {'Name on gamerepo (before lang underscore)': None, 'Pratham': None, 'Age Group': '14 and above', 'Subject': 'English', 'LE Comments': 'What does "English- Hindi" refer to?', 'Name': None, 'Resource Type': 'English- Hindi'}

  - Ask for translations for `subject_en` strings

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
    npm install phantomjs  # needed for scraping gamerepo



Running
-------

    source venv/bin/activate
    ./chef.py -v --thumbnails --token=<your_token>


