PraDigi Sushi Chef
==================
Import content from prathamopenschool.org and the Pratham gamerepo into Studio.


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

