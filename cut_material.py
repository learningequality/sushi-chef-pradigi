playlists = []
    # TODO: handle 
    elif row[RESOURCE_TYPE_KEY].startswith('YouTubePlaylist:'):
        playlist_url = row[RESOURCE_TYPE_KEY].replace('YouTubePlaylist:', '')
        playlist_subtree = get_youtube_playlist_subtree(playlist_url)
        playlists.append(playlist_subtree)







# B1. Load Vocational videos from youtube playlists (only available in Hindi)
if lang == 'hi':
    for playlist in resources['playlists']:
        ricecooker_subtree = wrt_to_ricecooker_tree(playlist, lang)
        subject_subtree['source_id'] = ricecooker_subtree['source_id']
        subject_subtree['description'] = ricecooker_subtree['description']
        for child in ricecooker_subtree['children']:
            subject_subtree['children'].append(child)




# YouTube playlist download helper
################################################################################

def get_youtube_playlist_subtree(playlist_url):
    """
    Uses the `get_youtube_info` helper method to download the complete
    list of videos from a youtube playlist and create web resource tree.
    """
    data = youtube_helper.get_youtube_info(playlist_url)

    # STEP 1: Create main dict for playlist
    playlist_description = data['description']
    if DEBUG_MODE:
        playlist_description += 'source_url=' + playlist_url
    subtree = dict(
        kind='youtube_playlist',
        source_id=data['id'],
        title=data['title'],
        description=playlist_description,
        # thumbnail_url=None,  # intentinally not set
        children=[],
    )

    # STEP 2. Process each video in playlist
    for video_data in data['children']:
        video_description = video_data['description']
        if DEBUG_MODE:
            video_description += 'source_url=' + video_data['source_url']
        video_dict = dict(
            kind='YouTubeVideoResource',
            source_id=video_data['id'],
            title=video_data['title'],
            description=video_description,
            thumbnail_url=video_data['thumbnail'],
            youtube_id=video_data['id'],
        )
        subtree['children'].append(video_dict)

    return subtree

