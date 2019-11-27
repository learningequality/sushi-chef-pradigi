PraDigi Sushi Chef
==================
Scripts to import content from prathamopenschool.org website into Kolibri Studio.


Design
------
The following google spreadsheet are used to determine placement of content within the channel:
  - English https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=1812185465
  - All other languages https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=342105160

The following corrections are applied to content before uploading to Kolibri:
https://docs.google.com/spreadsheets/d/1kPOnTVZ5vwq038x1aQNlA2AFtliLIcc2Xk5Kxr852mg/edit#gid=93933238




Install
-------

### 1. get the code

    git clone https://github.com/learningequality/sushi-chef-pradigi.git
    cd sushi-chef-pradigi/

### 2. setup a python virtual environment

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements.txt



Running
-------
To run the chef script, follow these steps:

### 1. Go the the project directory


    cd sushi-chef-pradigi

### 2. Activate the virtual env

    source venv/bin/activate


### 3. Clear the web caches

    rm -rf .webcache
    rm -rf cache.sqlite


### 4. Run the chef script:

    ./sushichef.py -v --reset --thumbnails --token=<your_token> --stage


This commands takes 19+ hours the first time it runs and performs the following:

  - During the `pre_run` stage:
    - crawl all languages https://www.prathamopenschool.org website
      output: json data in `chefdata/trees/pradigi_{lang}_web_resource_tree.json`
    - Builds the channel ricecooker tree:
      output: json data in `chefdata/trees/pradigi_ricecooker_json_tree.json`
    - Build HTML5Zip files from PraDigi games and webapps (saved in `chefdata/zipfiles`)

  - During the `run` stage, it tuns the `uploadchannel` command (multiple steps:
    - Load tree spec from `chefdata/trees/pradigi_ricecooker_json_tree.json`
    - Build ricecooker class tree (Python classes) from json spec
    - Download all files to `storage/` (remembering paths downloaded to `.ricecookerfilecache/`)
    - Run compression steps for videos and store compressed output in `storage/` (also `.ricecookerfilecache/`)
    - Run validation logic (check required metadata and all files present)
    - Upload content to Kolibri Studio

On subsequent runs, the process will use cached version of files downloaded,
generated HTML5Zip files, and compressed videos to avoid the need to re-download
everything.

When source files change or are modified, you can run a "clean start" chef run
but doing the following steps:
  - clear zip file cache `rm -rf chefdata/zipfiles`
  - clear web caches `rm -rf .webcache` and `rm -rf cache.sqlite`
  - clear storage dir `rm -rf storage/`
Note this will take 15+ hours again since we have to redo all the download and
conversion steps.

The `sushichef.py` optional argument `--update` will force re-downloading all files
and clear the local cache directory of zip files (`chefdata/zipfiles`) but will
not clear web caches, which needs to be done manually.

IMPORTANT: We recommend that you run `rm -rf .webcache` and `rm -rf cache.sqlite`
manually every time the website changes.



LE variant of the channel
-------------------------
There are two variants of the PraDigi channel, the `LE` variant is the "official"
version that is PUBLIC channel on Studio that all Kolibri users can see and import.
The `PRATHAM` variant is almost identical, but includes extra "debug info" in the
descriptions of each content node. The PRATHAM variant is maintained by Pratham.

To run the Learning Equality (LE) variant use the following command:

    ./sushichef.py -v --reset --thumbnails --token=<your_token> --stage  variant=LE

Note the extra command line option `varian=LE` passed in to select the LE variant.


### Running on vader

To run the chef in the background using (useful when running on a remote server via ssh):

    ssh chef@vader
        cd sushi-chef-pradigi
            rm -rf .webcache
            source venv/bin/activate
            nohup ./sushichef.py -v --reset --thumbnails --token=<your_token> --stage variant=LE &

The output of the script will be saved to the local file `nohup.out`, which you
can "follow" by using `tail -f nohup.out` to monitor the chef run.



Content Structure Logic
-----------------------
Excel document provides the template for the `Age Group > Subject` structure that
is repeated within each language. The columns in the sheet are:
  - Game Name instead of Name on gamerepo (before lang underscore)
  - Get full game namelist
  - Extract known games from webpage
  - Take from (if a resource needs to be taken from another language)

The content of each subject folder is taken from the top-level website menu,
the yellow horizontal bar with links:
![](./chefdata/pradigi_subject_structure.png)

Special treatment is required for dropdown menus--we ignore the dropdown parent
and instead treat the submenu items as top-level subjects.

The resources under Games are handled differently depending on the age group:
  - `KhelBadi` is used instead of the `3-6 years` subfolder
  - `KhelPuri` are included only in the `6-10 years` subfolder

The games extracted from the `KhelPuri` folder can be included in the `Fun`,
`Mathematics`, `Language`, and `English` subjects according to the structure gsheet.




Backlog
-------

Cross check with all games from here:  http://www.prathamopenschool.org/CourseContent/Games/


