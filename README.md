# sushi-chef-pratham-open-school
Import content from prathamopenschool.org into kolibri format


Install
-------

    git clone https://github.com/fle-internal/sushi-chef-pratham-open-school.git
    cd sushi-chef-pratham-open-school/
    mkvirtualenv -p python3 sushi-chef-pratham-open-school
    pip install ricecooker


Running
-------
Besides ricecooker parameters, you also need to provide the language:
hn (Hindi) or mr (Marathi).

    workon sushi-chef-pratham-open-school
    python -m ricecooker uploadchannel chef.py -v --token=<your_token> language=mr