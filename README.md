PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


Fixes TODO
----------

    [eslgenie.com:1] out: Unknown resource type English- Hindi in row {'Name on gamerepo (before lang underscore)': None, 'Pratham': None, 'Age Group': '14 and above', 'Subject': 'English', 'LE Comments': 'What does "English- Hindi" refer to?', 'Name': None, 'Resource Type': 'English- Hindi'}


TODO
----
  - run with --thumbnail
  - remove empty folders (post process tree)
  - Get game thumbnails from
    http://www.prodigi.openiscool.org/repository/Images/AwazPehchano_KN.png
  - skip mp4 that have 404 (two beauty videoes)
  - get subject strings for all other languages (shared spreadsheet workflow)



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


