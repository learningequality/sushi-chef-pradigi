PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.



TODO
----

  - How to get thumbnails for games?
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
    ./chef.py -v --token=<your_token>


