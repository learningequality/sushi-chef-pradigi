import logging
import os
import re
import requests
from urllib.parse import urljoin, urlparse



from basiccrawler.crawler import BasicCrawler
from bs4 import BeautifulSoup



from ricecooker.config import LOGGER
LOGGER.setLevel(logging.INFO)
from le_utils.constants.languages import getlang, getlang_by_name
from ricecooker.utils import downloader


from chef import (
    DOMAIN,
    FULL_DOMAIN_URL,
    PRADIGI_LANGUAGES,
    DEBUG_MODE,
)


PRADIGI_LANG_URL_MAP = {
    'hi': 'http://www.prathamopenschool.org/hn/',
    'mr': 'http://www.prathamopenschool.org/mr/',
}


class PrathamGamesRepoCrawler(BasicCrawler):
    """
    Get links fro all games from http://www.gamerepo.prathamcms.org/index.html
    """
    MAIN_SOURCE_DOMAIN = 'http://www.gamerepo.prathamcms.org'
    CRAWLING_STAGE_OUTPUT = 'chefdata/trees/pradigi_games_all_langs.json'
    START_PAGE_CONTEXT = {'kind': 'index_page'}
    kind_handlers = {
        'index_page': 'on_index_page',
        'gameslang_page': 'on_gameslang_page',
    }

    def on_index_page(self, url, page, context):
        LOGGER.info('in on_index_page ' + url)
        page_dict = dict(
            kind='index_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)
        
        languagelist_divs = page.find_all('div', attrs={'ng-repeat': "lang in languagelist"})
        for languagelist_div in languagelist_divs:
            link = languagelist_div.find('a')
            language_en = get_text(link)
            language_url = urljoin(url, link['href'])
            context = dict(
                parent=page_dict,
                kind='gameslang_page',
                language_en=language_en,
            )
            self.enqueue_url_and_context(language_url, context)

    def on_gameslang_page(self, url, page, context):
        LOGGER.info('in on_gameslang_page ' + url)
        page_dict = dict(
            kind='gameslang_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)
        
        gamelist = page.find_all('div', attrs={'ng-repeat':"gamedata in gamelist|filter:gametitle|filter:gamedata.gameurl.length"})
        for game in gamelist:
            title = get_text(game.find('h3'))
            last_modified = get_text(game.find('h6')).replace('Last modified : ', '')
            links = game.find_all('a')
            game_link, zipfile_link = links[0], links[1]
            main_file = urljoin(url, game_link['href'])
            zipfile_url = urljoin(url, zipfile_link['href'])

            # Handle special case of broken links (no title, and not main file)
            if len(title) == 0:
                zip_path = urlparse(zipfile_url).path
                zip_filename = os.path.basename(zip_path)
                title, _ = os.path.splitext(zip_filename)
                main_file = None

            game_dict = dict(
                url=zipfile_url,
                kind='PradigiGameZipResource',
                title=title,
                last_modified=last_modified,
                main_file=main_file,
                language_en=context['language_en'],
                children=[],
            )
            page_dict['children'].append(game_dict)


    def download_page(self, url, *args, **kwargs):
        """
        Download `url` using a JS-enabled web client.
        """
        LOGGER.info('Downloading ' +  url + ' then pausing for 15 secs for JS to run.')
        html = downloader.read(url, loadjs=True, loadjs_wait_time=20)
        page = BeautifulSoup(html, "html.parser")
        LOGGER.debug('Downloaded page ' + str(url) + ' using PhantomJS. Title:' + self.get_title(page))
        return (url, page)
























class PraDigiCrawler(BasicCrawler):
    MAIN_SOURCE_DOMAIN = FULL_DOMAIN_URL
    START_PAGE_CONTEXT = {'kind': 'lang_page'}
    kind_handlers = {
        'lang_page': 'on_lang_page',
        'topic_page': 'on_topic_page',
        'subtopic_page': 'on_subtopic_page',
        'lesson_page': 'on_lesson_page',
        'fun_page': 'on_fun_page',
        'story_page': 'on_story_page',
        'story_resource_page': 'on_story_resource_page',
    }



    # CRALWING
    ############################################################################

    def __init__(self, lang=None, **kwargs):
        """
        Extend base class constructor to handle two-letter language code `lang`.
        """
        if lang is None:
            raise ValueError('Must specify `lang` argument for PraDigiCrawler.')
        if lang not in PRADIGI_LANGUAGES:
            raise ValueError('Bad lang. Use one of ' + str(PRADIGI_LANGUAGES))
        self.lang = lang
        start_page = PRADIGI_LANG_URL_MAP[self.lang]
        self.CRAWLING_STAGE_OUTPUT = 'chefdata/trees/pradigi_{}_web_resource_tree.json'.format(lang)
        super().__init__(start_page=start_page)


    def crawl(self, **kwargs):
        """
        Extend base crawl method to add PraDigi channel metadata. 
        """
        web_resource_tree = super().crawl(**kwargs)

        # channel metadata
        lang_obj = getlang(self.lang)
        channel_metadata = dict(
            title='PraDigi ({})'.format(lang_obj.native_name),
            description = 'PraDigi video lessons and games.',  # TODO(ivan): what should be the longer descitpiton?
            source_domain = DOMAIN,
            source_id='pratham-open-school-{}'.format(self.lang),
            language=self.lang,
            thumbnail=None, # get_absolute_path('img/logop.png'),
        )
        web_resource_tree.update(channel_metadata)

        # convert tree format expected by scraping functions
        # restructure_web_resource_tree(web_resource_tree)
        # remove_sections(web_resource_tree)
        self.write_web_resource_tree_json(web_resource_tree)
        return web_resource_tree



    

    # HANDLERS
    ############################################################################

    def on_lang_page(self, url, page, context):
        LOGGER.debug('in on_lang_page ' + url)
        page_dict = dict(
            kind='lang_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'menu-row'})
        except Exception as e:
            LOGGER.error('on_lang_page: %s : %s' % (e, page))
            return
        for topic in menu_row.find_all('a'):
            try:
                if topic['href'] == '#':
                    print('skipping', topic)
                    continue
                
                # metadata
                topic_url = urljoin(url, topic['href'])
                title = topic.get_text().strip()
                source_id = get_source_id(topic['href'])
                subject_en = source_id    # short string to match on top-level categories
                context = dict(
                    parent=page_dict,
                    title=title,
                    source_id=source_id,
                    subject_en=subject_en,
                )
                
                # what type of tab is it?
                if 'Fun' in topic['href']:
                    LOGGER.info('found fun page: %s: %s' % (source_id, title))
                    context['kind'] = 'fun_page'
                elif 'Story' in topic['href']:
                    LOGGER.info('found story page: %s: %s' % (source_id, title))
                    context['kind'] = 'story_page'
                else:
                    LOGGER.info('found topic: %s: %s' % (source_id, title))
                    context['kind'] = 'topic_page'
                self.enqueue_url_and_context(topic_url, context)

                if DEBUG_MODE:
                    return

            except Exception as e:
                LOGGER.error('on_lang_page: %s : %s' % (e, topic))


    def on_topic_page(self, url, page, context):
        LOGGER.debug('in on_topic_page ' + url)
        page_dict = dict(
            kind='topic_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            menu_row = body_row.find('div', {'class': 'col-md-2'})
        except Exception as e:
            LOGGER.error('get_subtopics: %s : %s' % (e, page))
            return
        for subtopic in menu_row.find_all('a'):
            try:
                subtopic_url = urljoin(url, subtopic['href'])
                title = subtopic.get_text().strip()
                source_id = get_source_id(subtopic['href'])
                LOGGER.info('  found subtopic: %s: %s' % (source_id, title))
                context = dict(
                    parent=page_dict,
                    kind='subtopic_page',
                    title=title,
                    source_id=source_id,
                    children=[],
                )
                self.enqueue_url_and_context(subtopic_url, context)
            except Exception as e:
                LOGGER.error('on_topic_page: %s : %s' % (e, subtopic))


    def on_subtopic_page(self, url, page, context):
        print('     in on_subtopic_page', url)
        page_dict = dict(
            kind='subtopic_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'body-row'})
            menu_row = menu_row.find('div', {'class': 'col-md-9'})
        except Exception as e:
            LOGGER.error('on_subtopic_page: %s : %s' % (e, page))
            return
        for lesson in menu_row.find_all('div', {'class': 'thumbnail'}):
            try:
                title = lesson.find('div', {'class': 'txtline'}).get_text().strip()
                caption = lesson.find('div', class_='caption')
                description = caption.get_text().strip() if caption else ''
                lesson_url = urljoin(url, lesson.find('a')['href'])
                thumbnail_src = lesson.find('a').find('img')['src']
                thumbnail_url = urljoin(url, thumbnail_src)
                source_id = get_source_id(lesson.find('a')['href'])
                LOGGER.info('     lesson: %s: %s' % (source_id, title))
                context = dict(
                    parent=page_dict,
                    kind='lesson_page',
                    title=title,
                    description=description,
                    source_id=source_id,
                    thumbnail_url=thumbnail_url,
                    children=[],
                )
                self.enqueue_url_and_context(lesson_url, context)
                # get_contents(node, link)
            except Exception as e:
                LOGGER.error('on_subtopic_page: %s : %s' % (e, lesson))


    # LESSONS
    ############################################################################

    def on_lesson_page(self, url, page, context):
        print('      in on_lesson_page', url)
        page_dict = dict(
            kind='lessons_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            menu_row = page.find('div', {'id': 'row-exu'})
        except Exception as e:
            LOGGER.error('on_lesson_page: %s : %s' % (e, page))
            return

        contents = menu_row.find_all('div', {'class': 'col-md-3'})
        for content in contents:
            try:
                title = content.find('div', {'class': 'txtline'}).get_text()
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)
                main_file, master_file, source_id = get_content_link(content)
                LOGGER.info('      content: %s: %s' % (source_id, title))

                if main_file.endswith('mp4'):
                    video = dict(
                        url=main_file,
                        kind='PrathamVideoResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(video)

                elif main_file.endswith('pdf'):
                    pdf = dict(
                        url=main_file,
                        kind='PrathamPdfResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(pdf)

                elif main_file.endswith('html') and master_file.endswith('zip'):
                    zipfile = dict(
                        url=master_file,
                        kind='PrathamZipResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        main_file=main_file,     # needed to rename to index.html if different
                        children=[],
                    )
                    page_dict['children'].append(zipfile)

                else:
                    LOGGER.error('Content not supported: %s, %s' % (main_file, master_file))
            except Exception as e:
                LOGGER.error('zz _process_contents: %s : %s' % (e, content))



    # FUN PAGES
    ############################################################################
    
    def on_fun_page(self, url, page, context):
        print('     in on_fun_page', url)
        page_dict = dict(
            kind='fun_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            contents_row = body_row.find('div', {'class': 'row'})
        except Exception as e:
            LOGGER.error('on_fun_page: %s : %s' % (e, page))
            return
        contents = contents_row.find_all('div', {'class': 'col-md-3'})

        for content in contents:
            try:
                title = get_text(content.find('div', {'class': 'txtline'}))
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)

                # get_fun_content_link
                link = content.find('a')
                source_id = link['href'][1:]
                fun_resource_url = get_absolute_path(link['href'])
                download_href = content.find('a', class_='dnlinkfunstory')['href']
                download_url = get_absolute_path(download_href)

                LOGGER.info('      content: %s: %s' % (source_id, title))

                if download_url.endswith('mp4'):
                    video = dict(
                        url=download_url,
                        kind='PrathamVideoResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(video)

                elif download_url.endswith('pdf'):
                    pdf = dict(
                        url=download_url,
                        kind='PrathamPdfResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        children=[],
                    )
                    page_dict['children'].append(pdf)

                elif download_url.endswith('zip'):
                    # Need to go get the actual page since main_file is not in avail. in list
                    html = requests.get(fun_resource_url).content.decode('utf-8')
                    respath_url = get_respath_url_from_html(html)
                    zipfile = dict(
                        url=download_url,
                        kind='PrathamZipResource',
                        title=title,
                        source_id=source_id,
                        thumbnail_url=thumbnail,
                        main_file=respath_url,   # needed to rename to index.html if different
                        children=[],
                    )
                    page_dict['children'].append(zipfile)

                else:
                    LOGGER.error('Fun resource not supported: %s, %s' % (fun_resource_url, download_url))

            except Exception as e:
                LOGGER.error('on_fun_page: %s : %s' % (e, content))



    # STORIES
    ############################################################################

    def on_story_page(self, url, page, context):
        print('     in on_story_page', url)
        page_dict = dict(
            kind='story_page',
            url=url,
            children=[],
        )
        page_dict.update(context)
        context['parent']['children'].append(page_dict)

        try:
            body_row = page.find('div', {'id': 'body-row'})
            contents_row = body_row.find('div', {'class': 'row'})
        except Exception as e:
            LOGGER.error('on_story_page: %s : %s' % (e, page))
            return
        contents = contents_row.find_all('div', {'class': 'col-md-3'})

        for content in contents:
            try:
                title = get_text(content.find('div', {'class': 'txtline'}))
                # TODO: description
                thumbnail = content.find('a').find('img')['src']
                thumbnail = get_absolute_path(thumbnail)

                # get_fun_content_link
                link = content.find('a')
                source_id = link['href'][1:]
                story_resource_url = get_absolute_path(link['href'])
                LOGGER.info('      story_resource_page: %s: %s' % (source_id, title))
                context = dict(
                    parent = page_dict,
                    kind='story_resource_page',
                    title=title,
                    source_id=source_id,
                    thumbnail_url=thumbnail,
                )
                self.enqueue_url_and_context(story_resource_url, context)

            except Exception as e:
                LOGGER.error('on_story_page: %s : %s' % (e, content))

    def on_story_resource_page(self, url, page, context):
        print('     in on_story_resource_page', url)
        html = str(page)
        story_resource_url = get_respath_url_from_html(html)
        if story_resource_url:
            page_dict = dict(
                url=story_resource_url,
                children=[],
            )
            page_dict.update(context)
            context['parent']['children'].append(page_dict)
        else:
            LOGGER.error('Failed to find story_resource_url on page %s' % url)




# Helper functions
################################################################################
def get_absolute_path(path):
    return urljoin('http://www.' + DOMAIN, path)


_RESOURCE_PATH_PATTERN = re.compile('var respath = "(?P<resource_path>.*?)";')
def get_respath_url_from_html(html):
    m = _RESOURCE_PATH_PATTERN.search(html)
    if m is None:
        return None
    respath_url =  get_absolute_path('/' + m.groupdict()['resource_path'])
    return respath_url



def get_text(element):
    """
    Extract text contents of `element`, normalizing newlines to spaces and stripping.
    """
    if element is None:
        return ''
    else:
        return element.get_text().replace('\r', '').replace('\n', ' ').strip()


def get_source_id(path):
    return path.strip('/').split('/')[-1]




def get_content_link(content):
    """
    The link to a content has an onclick attribute that executes
    the res_click function. This function has 4 parameters:
    - The main file (e.g. an mp4 file, an entry html page to a game).
    - The type of resource (video, internal link, ...).
    - A description.
    - A master file (e.g. for a game, it is a zip file).
    """
    link = content.find('a', {'id': 'navigate'})
    source_id = link['href'][1:]
    regex = re.compile(r"res_click\('(.*)','.*','.*','(.*)'\)")
    match = regex.search(link['onclick'])
    link = match.group(1)
    main_file = get_absolute_path(link)
    master_file = match.group(2)
    if master_file:
        master_file = get_absolute_path(master_file)
    return main_file, master_file, source_id
