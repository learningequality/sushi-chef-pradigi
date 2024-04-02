import hashlib
import logging
import os
import requests
import shutil
import tempfile
import zipfile
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from ricecooker.config import LOGGER
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip


from corrections import (PRADIGI_CORRECTIONS_LIST, CORRECTIONS_ACTION_KEY,
                         ADD_MARGIN_TOP_ACTION, CORRECTIONS_SOURCE_URL_PAT_KEY)
from corrections import should_replace_with


LOGGER.setLevel(logging.DEBUG)



# GAME_THUMBS_LOCAL_DIR = 'chefdata/gamethumbnails'
HTML5APP_ZIPS_LOCAL_DIR = 'chefdata/zipfiles'




# ZIP FILE DOWNLOADING, TRANFORMS, AND FIXUPS
################################################################################

def make_request(url):
    response = requests.get(url)
    if response.status_code != 200:
        LOGGER.error("ERROR when GETting: %s" % (url))
    return response

def make_temporary_dir_from_key(key_str):
    """
    Creates a subdirectory of HTML5APP_ZIPS_LOCAL_DIR to store
    the downloded, unzipped, and final version of each HTML5Zip file.
    """
    key_bytes = key_str.encode('utf-8')
    m = hashlib.md5()
    m.update(key_bytes)
    subdir = m.hexdigest()
    dest = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, subdir)
    if not os.path.exists(dest):
        os.mkdir(dest)
    return dest

def add_body_margin_top(zip_folder, filename, margin='44px'):
    file_path = os.path.join(zip_folder, filename)
    with open(file_path, 'r') as inf:
        html = inf.read()
    page = BeautifulSoup(html, "html.parser")  # Load index.html as BS4
    body = page.find('body')
    if body.has_attr('style'):
        prev_style_str = body['style']
    else:
        prev_style_str = ''
    body['style'] = prev_style_str + " margin-top:" + margin + ";"
    with open(file_path, 'w') as outf:
        outf.write(str(page))


def get_zip_file(zip_file_url, main_file):
    """
    HTML games are provided as zip files, the entry point of the game is `main_file`.
    THe `main_file` needs to be renamed to index.html to make it compatible with Kolibri.
    """
    key = zip_file_url + main_file
    destpath = make_temporary_dir_from_key(key)
    
    # Check for "REPLACE WITH:" correction rule for the current `zip_file_url`
    replacement_url = should_replace_with(zip_file_url)
    if replacement_url:
        zip_file_url = replacement_url

    # return cached version if already there
    final_webroot_path = os.path.join(destpath, 'webroot.zip')
    if os.path.exists(final_webroot_path):
        return final_webroot_path
    else:
        LOGGER.error("Now we need local files so we can process them: %s" % final_webroot_path)

    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]         # e.g. Mathematics.zip
        zip_basename = zip_filename.rsplit('.', 1)[0]      # e.g. Mathematics/

        # July 31: handle ednge cases where zip filename doesn't match folder name inside it
        awazchitras = ['Awazchitra_HI', 'Awazchitra_TL', 'Awazchitra_KN',
            'Awazchitra_BN', 'Awazchitra_OD', 'Awazchitra_PN', 'Awazchitra_TM']
        for awazchitra in awazchitras:
            if awazchitra in zip_basename:
                zip_basename = zip_basename.replace('Awazchitra', 'AwazChitra')
        if '_KKS_Hi' in zip_basename:
            zip_basename = zip_basename.replace('_KKS_Hi', '_KKS_HI')

        # Mar 2: more edge cases where zip filename doesn't match folder name inside it
        if 'Memorygamekb' in zip_basename:
            zip_basename = zip_basename.replace('Memorygamekb', 'MemoryGamekb')
        if 'cityofstories' in zip_basename:
            zip_basename = zip_basename.replace('cityofstories', 'CityOfStories')

        # Jun 12: fix more edge cases where .zip filename doesn't match dir name
        if '_KKS_Gj' in zip_basename:
            zip_basename = zip_basename.replace('_KKS_Gj', '_KKS_GJ')
        if 'ShabdKhel' in zip_basename:
            zip_basename = zip_basename.replace('ShabdKhel', 'Shabdkhel')

        zip_folder = os.path.join(destpath, zip_basename)  # e.g. destpath/Mathematics/
        main_file = main_file.split('/')[-1]               # e.g. activity_name.html or index.html

        if 'KhelbadiKahaniyan_MR' in zip_basename:
            # Inconsistency --- `main_file` contains dir name, and not index.html
            main_file = 'index.html'

        # Jul 8th: handle weird case-insensitive webserver main_file
        if main_file == 'mainexpand.html':
            main_file = 'mainExpand.html'  # <-- this is the actual filename in the zip

        # Zip files from Pratham website have the web content inside subfolder
        # of the same as the zip filename. We need to recreate these zip files
        # to make sure the index.html is in the root of the zip.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            # If main_file is in the root (like zips from the game repository)
            # then we need to extract the zip contents to subfolder zip_basename/
            for zfileinfo in zf.filelist:
                if zfileinfo.filename == main_file:
                    destpath = os.path.join(destpath, zip_basename)
            # Extract zip so main file will be in destpath/zip_basename/index.html
            zf.extractall(destpath)

        # In some cases, the files are under the www directory,
        # let's move them up one level.
        www_dir = os.path.join(zip_folder, 'www')
        if os.path.isdir(www_dir):
            files = os.listdir(www_dir)
            for f in files:
                shutil.move(os.path.join(www_dir, f), zip_folder)

        # Rename `main_file` to index.html
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'index.html')
        os.rename(src, dest)

        # Logic to add margin-top:44px; for games that match Corrections tab
        add_margin_top = False
        for row in PRADIGI_CORRECTIONS_LIST:
            if row[CORRECTIONS_ACTION_KEY] == ADD_MARGIN_TOP_ACTION:
                pat = row[CORRECTIONS_SOURCE_URL_PAT_KEY]
                m = pat.match(zip_file_url)
                if m:
                    add_margin_top = True
        if add_margin_top:
            if zip_file_url.endswith('CourseContent/Games/Mathematics.zip'):
                LOGGER.info("adding body.margin-top:44px; to ALL .html files in: %s" % zip_file_url)
                for root, dirs, files in os.walk(zip_folder):
                    for file in files:
                        if file.endswith(".html"):
                            add_body_margin_top(root, file)
            else:
                LOGGER.info("adding body.margin-top:44px; to index.html in: %s" % zip_file_url)
                add_body_margin_top(zip_folder, 'index.html')

        # Replace occurences of `main_file` with index.html to avoid broken links
        for root, dirs, files in os.walk(zip_folder):
            for file in files:
                if file.endswith(".html") or file.endswith(".js"):
                    file_path = os.path.join(root, file)
                    # use bytes to avoid Unicode errors "invalid start/continuation byte"
                    bytes_in = open(file_path, 'rb').read()
                    bytes_out = bytes_in.replace(main_file.encode('utf-8'), b'index.html')
                    open(file_path, 'wb').write(bytes_out)

        for root, dirs, files in os.walk(zip_folder):
            for file in files:
                if file.endswith(".js"):
                    LOGGER.info("Fixing Android bug in JS file: %s" % file)
                    with open(file, 'w') as f:
                        content = f.read()
                        content = content.replace(
                            'Utils.mobileDeviceFlag=true', 
                            'Utils.mobileDeviceFlag=false'
                        )
                        f.write(content)
                        f.close()
        # create the zip file and copy it to 
        tmp_predictable_zip_path = create_predictable_zip(zip_folder)
        shutil.copyfile(tmp_predictable_zip_path, final_webroot_path)
        return final_webroot_path

    except Exception as e:
        LOGGER.error("get_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file, destpath, e))
        return None


PHET_INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
</head>
<body>
  <div><p>Redirecting to phet simulation {sim_id} now...</p></div>
</body>
<script type="text/javascript">
    window.location.href = "phetindex.html?id={sim_id}";
</script>
</html>
"""


def get_phet_zip_file(zip_file_url, main_file_and_query):
    """
    Phet simulations are provided in the zip file `phet.zip`, and the entry point
    is passed as a GET parameter in `main_file_and_query`. To make these compatible
    with Kolibri's default behaviour of loading index.html, we will:
      - Rename index.html to phetindex.thml
      - Add a custom index.html that uses javascrpt redirect to phetindex.thml?{sim_id}
    """
    u = urlparse(main_file_and_query)
    idk, sim_id = u.query.split('=')
    assert idk == 'id', 'unknown query sting format found' + main_file_and_query
    main_file = u.scheme + '://' + u.netloc + u.path  # skip querystring
    
    destpath = tempfile.mkdtemp()
    LOGGER.info('saving phet zip file in dir ' + destpath)
    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]
        zip_basename = zip_filename.rsplit('.', 1)[0]
        zip_folder = os.path.join(destpath, zip_basename)

        # Extract zip file contents.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            zf.extractall(destpath)

        # Rename main_file to phetindex.html
        main_file = main_file.split('/')[-1]
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'phetindex.html')
        os.rename(src, dest)

        # Create the 
        index_html = PHET_INDEX_HTML_TEMPLATE.format(sim_id=sim_id)
        with open(os.path.join(zip_folder, 'index.html'), 'w') as indexf:
            indexf.write(index_html)
        
        # Always be zipping!
        return create_predictable_zip(zip_folder)

    except Exception as e:
        LOGGER.error("get_phet_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file_and_query, destpath, e))
        return None




