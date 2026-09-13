# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher scraping engine for TGDB.
#
# --- Information about scraping ---
# https://github.com/muldjord/skyscraper
# https://github.com/muldjord/skyscraper/blob/master/docs/SCRAPINGMODULES.md

# Copyright (c) Chrisism <crizizz@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import json
import re

from urllib.parse import quote_plus

# --- AKL packages ---
from akl import constants, platforms, settings
from akl.utils import io, net, kodi
from akl.scrapers import Scraper
from akl.api import ROMObj

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------
# TheGamesDB online scraper (metadata and assets).
# TheGamesDB is the scraper reference implementation. Always look here for comments when
# developing other scrapers.
#
# | Site     | https://thegamesdb.net      |
# | API info | https://api.thegamesdb.net/ |
# ------------------------------------------------------------------------------------------------
class TheGamesDB(Scraper):
    # --- Class variables ------------------------------------------------------------------------
    supported_metadata_list = [
        constants.META_TITLE_ID,
        constants.META_YEAR_ID,
        constants.META_GENRE_ID,
        constants.META_DEVELOPER_ID,
        constants.META_NPLAYERS_ID,
        constants.META_ESRB_ID,
        constants.META_PLOT_ID,
        constants.META_TAGS_ID
    ]
    supported_asset_list = [
        constants.ASSET_FANART_ID,
        constants.ASSET_BANNER_ID,
        constants.ASSET_CLEARLOGO_ID,
        constants.ASSET_SNAP_ID,
        constants.ASSET_BOXFRONT_ID,
        constants.ASSET_BOXBACK_ID,
        constants.ASSET_TRAILER_ID
    ]
    asset_name_mapping = {
        'screenshot': constants.ASSET_SNAP_ID,
        'boxart': constants.ASSET_BOXFRONT_ID,
        'boxartfront': constants.ASSET_BOXFRONT_ID,
        'boxartback': constants.ASSET_BOXBACK_ID,
        'fanart': constants.ASSET_FANART_ID,
        'clearlogo': constants.ASSET_CLEARLOGO_ID,
        'banner': constants.ASSET_BANNER_ID,
        'titlescreen': constants.ASSET_TITLE_ID
    }
    # This allows to change the API version easily.
    URL_ByGameName = 'https://api.thegamesdb.net/v1/Games/ByGameName'
    URL_ByGameID = 'https://api.thegamesdb.net/v1/Games/ByGameID'
    URL_Platforms = 'https://api.thegamesdb.net/v1/Platforms'
    URL_Genres = 'https://api.thegamesdb.net/v1/Genres'
    URL_Developers = 'https://api.thegamesdb.net/v1/Developers'
    URL_Publishers = 'https://api.thegamesdb.net/v1/Publishers'
    URL_Images = 'https://api.thegamesdb.net/v1/Games/Images'

    GLOBAL_CACHE_TGDB_GENRES = 'TGDB_genres'
    GLOBAL_CACHE_TGDB_DEVELOPERS = 'TGDB_developers'

    # --- Constructor ----------------------------------------------------------------------------
    def __init__(self):
        # --- This scraper settings ---
        # TheGamesDB requires an API key. Users should configure their own
        # public API key in the scraper add-on settings.
        self.api_key = settings.getSetting('thegamesdb_apikey')
        if self.api_key:
            logger.info('Applied API key from settings')
        else:
            logger.warning('TheGamesDB API key is not configured')

        # --- Cached TGDB metadata ---
        self.cache_candidates = {}
        self.cache_metadata = {}
        self.cache_assets = {}
        self.all_asset_cache = {}

        self.genres_cached = {}
        self.developers_cached = {}
        self.publishers_cached = {}

        cache_dir = settings.getSettingAsFilePath('scraper_cache_dir')
        self.GLOBAL_CACHE_LIST.append(self.GLOBAL_CACHE_TGDB_GENRES)
        self.GLOBAL_CACHE_LIST.append(self.GLOBAL_CACHE_TGDB_DEVELOPERS)
        super(TheGamesDB, self).__init__(cache_dir)
    
    # --- Base class abstract methods ------------------------------------------------------------
    def get_name(self):
        return 'TheGamesDB'

    def get_filename(self):
        return 'TGDB'

    def supports_disk_cache(self):
        return True

    def supports_search_string(self):
        return True

    def supports_metadata_ID(self, metadata_ID):
        return True if metadata_ID in TheGamesDB.supported_metadata_list else False

    def supports_metadata(self):
        return True

    def supports_asset_ID(self, asset_ID):
        return True if asset_ID in TheGamesDB.supported_asset_list else False

    def supports_assets(self):
        return True

    # TheGamesDB requires an API key.
    def check_before_scraping(self, status_dic):
        if not self.api_key:
            status_dic['status'] = False
            status_dic['dialog'] = kodi.KODI_MESSAGE_DIALOG
            status_dic['msg'] = (
                'TheGamesDB API key is not configured. '
                'Enter your public API key in the TheGamesDB scraper add-on settings.'
            )

        return status_dic

    def get_candidates(self, search_term, rom: ROMObj, platform, status_dic):
        # If the scraper is disabled return None and do not mark error in status_dic.
        # Candidate will not be introduced in the disk cache and will be scraped again.
        if self.scraper_disabled:
            logger.debug('Scraper disabled. Returning empty data for candidates.')
            return None

        # Prepare data for scraping.
        # --- Get candidates ---
        scraper_platform = convert_AKL_platform_to_TheGamesDB(platform)
        logger.debug('search_term         "{}"'.format(search_term))
        logger.debug('rom identifier      "{}"'.format(rom.get_identifier()))
        logger.debug('AKL platform        "{}"'.format(platform))
        logger.debug('TheGamesDB platform "{}"'.format(scraper_platform))
        candidate_list = self._search_candidates(search_term, platform, scraper_platform, status_dic)
        if not status_dic['status']:
            return None

        # --- Deactivate this for now ---
        # if len(candidate_list) == 0:
        #     altered_search_term = self._cleanup_searchterm(search_term, rombase_noext, platform)
        #     logger.debug('Cleaning search term. Before "{0}"'.format(search_term))
        #     logger.debug('After "{0}"'.format(altered_search_term))
        #     if altered_search_term != search_term:
        #         logger.debug('No matches, trying again with altered search terms: {0}'.format(
        #             altered_search_term))
        #         return self._get_candidates(altered_search_term, rombase_noext, platform)

        return candidate_list
    
    # This function may be called many times in the ROM Scanner. All calls to this function
    # must be cached. See comments for this function in the Scraper abstract class.
    def get_metadata(self, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            logger.debug('Scraper disabled. Returning empty data.')
            return self._new_gamedata_dic()

        # --- Check if search term is in the cache ---
        if self._check_disk_cache(Scraper.CACHE_METADATA, self.cache_key):
            logger.debug(f'Metadata cache hit "{self.cache_key}"')
            return self._retrieve_from_disk_cache(Scraper.CACHE_METADATA, self.cache_key)

        # --- Request is not cached. Get candidates and introduce in the cache ---
        logger.debug(f'Metadata cache miss "{self.cache_key}"')
        fields = ['players', 'genres', 'overview', 'rating', 'coop',
                  'youtube', 'hdd', 'video', 'sound']
        fields_concat = '%2C'.join(fields)
        id = self.candidate['id']
        url_tail = f'?apikey={self._get_API_key()}&id={id}&fields={fields_concat}'
        url = TheGamesDB.URL_ByGameID + url_tail
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_metadata.json', json_data)

        # --- Parse game page data ---
        logger.debug('Parsing game metadata...')
        online_data = json_data['data']['games'][0]
        gamedata = self._new_gamedata_dic()
        gamedata['title'] = self._parse_metadata_title(online_data)
        gamedata['year'] = self._parse_metadata_year(online_data)
        gamedata['genre'] = self._parse_metadata_genres(online_data, status_dic)
        if not status_dic['status']:
            return None
        gamedata['developer'] = self._parse_metadata_developer(online_data, status_dic)
        if not status_dic['status']:
            return None
        gamedata['nplayers'] = self._parse_metadata_nplayers(online_data)
        gamedata['esrb'] = self._parse_metadata_esrb(online_data)
        gamedata['plot'] = self._parse_metadata_plot(online_data)
        gamedata['tags'] = self._parse_metadata_tags(online_data)
        gamedata['trailer'] = self._parse_metadata_trailer(online_data)

        # --- Put metadata in the cache ---
        logger.debug(f'Adding to metadata cache "{self.cache_key}"')
        self._update_disk_cache(Scraper.CACHE_METADATA, self.cache_key, gamedata)

        logger.debug(f"Available metadata for the current scraped title: {json.dumps(gamedata)}")
        return gamedata
 
    # This function may be called many times in the ROM Scanner. All calls to this function
    # must be cached. See comments for this function in the Scraper abstract class.
    def get_assets(self, asset_info_id: str, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            logger.debug('Scraper disabled. Returning empty data.')
            return []

        candidate_id = self.candidate['id']
        logger.debug(f'Getting assets {asset_info_id} for candidate ID "{candidate_id}"')

        if asset_info_id == constants.ASSET_TRAILER_ID:
            gamedata = self.get_metadata(status_dic)
            if gamedata and 'trailer' in gamedata and gamedata['trailer']:
                logger.debug("Found trailer asset")
                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = "Youtube Trailer"
                asset_data['url_thumb'] = "Youtube.png"
                asset_data['url'] = gamedata['trailer']
                return [asset_data]

        # --- Request is not cached. Get candidates and introduce in the cache ---
        # Get all assets for candidate. _scraper_get_assets_all() caches all assets for a
        # candidate. Then select asset of a particular type.
        all_asset_list = self._retrieve_all_assets(self.candidate, status_dic)
        if not status_dic['status']:
            return None
        asset_list = [asset_dic for asset_dic in all_asset_list if asset_dic['asset_ID'] == asset_info_id]
        logger.debug('Total assets {} / Returned assets {}'.format(
            len(all_asset_list), len(asset_list)))

        return asset_list

    def resolve_asset_URL(self, selected_asset, status_dic):
        url = selected_asset['url']
        url_log = self._clean_URL_for_log(url)

        return url, url_log

    def resolve_asset_URL_extension(self, selected_asset, image_url, status_dic):
        if selected_asset['asset_ID'] == constants.ASSET_TRAILER_ID:
            return "url"
        return io.get_URL_extension(image_url)

    # --- This class own methods -----------------------------------------------------------------
    def debug_get_platforms(self, status_dic):
        logger.debug('Get Platforms: BEGIN...')
        url = TheGamesDB.URL_Platforms + '?apikey={}'.format(self._get_API_key())
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_platforms.json', json_data)

        return json_data

    def debug_get_genres(self, status_dic):
        logger.debug('Get Genres: BEGIN...')
        url = TheGamesDB.URL_Genres + '?apikey={}'.format(self._get_API_key())
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_genres.json', json_data)

        return json_data

    def download_image(self, image_url, image_local_path: io.FileName):
        if "plugin.video.youtube" in image_url:
            return image_url
        return super(TheGamesDB, self).download_image(image_url, image_local_path)

    # Always use the developer public key which is limited per IP address. This function
    # may return the private key during scraper development for debugging purposes.
    def _get_API_key(self):
        return self.api_key

    # --- Retrieve list of games ---
    def _search_candidates(self, search_term: str, platform: str, scraper_platform: int, status_dic):
        # quote_plus() will convert the spaces into '+'. Note that quote_plus() requires an
        # UTF-8 encoded string and does not work with Unicode strings.
        # https://stackoverflow.com/questions/22415345/using-pythons-urllib-quote-plus-on-utf-8-strings-with-safe-arguments
        search_string_encoded = quote_plus(search_term)
        url_tail = '?apikey={}&name={}&filter[platform]={}'.format(
            self._get_API_key(), search_string_encoded, scraper_platform)
        url = TheGamesDB.URL_ByGameName + url_tail
        # _retrieve_games_from_url() may load files recursively from several pages so this code
        # must be in a separate function.
        candidate_list = self._retrieve_games_from_url(
            url, search_term, platform, scraper_platform, status_dic)
        if not status_dic['status']:
            return None

        # --- Sort game list based on the score. High scored candidates go first ---
        candidate_list.sort(key=lambda result: result['order'], reverse=True)

        return candidate_list

    # Return a list of candiate games.
    # Return None if error/exception.
    # Return empty list if no candidates found.
    def _retrieve_games_from_url(self, url, search_term: str, platform: str, scraper_platform: int, status_dic):
        # --- Get URL data as JSON ---
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        # If status_dic mark an error there was an exception. Return None.
        if not status_dic['status']:
            return None
        # If no games were found status_dic['status'] is True and json_data is None.
        # Return empty list of candidates.
        self._dump_json_debug('TGDB_get_candidates.json', json_data)

        # --- Parse game list ---
        games_json = json_data['data']['games']
        candidate_list = []
        for item in games_json:
            title = item['game_title']
            scraped_akl_platform = convert_TheGamesDB_platform_to_AKL_platform(item['platform'])
            
            candidate = self._new_candidate_dic()
            candidate['id'] = item['id']
            candidate['display_name'] = '{} ({})'.format(title, scraped_akl_platform.long_name)
            candidate['platform'] = platform
            # Candidate platform may be different from scraper_platform if scraper_platform = 0
            # Always trust TGDB API about the platform of the returned candidates.
            candidate['scraper_platform'] = item['platform']
            candidate['order'] = 1
            # Increase search score based on our own search.
            if title.lower() == search_term.lower():
                candidate['order'] += 2
            if title.lower().find(search_term.lower()) != -1:
                candidate['order'] += 1
            if scraper_platform > 0 and platform == scraped_akl_platform.long_name:
                candidate['order'] += 1
            candidate_list.append(candidate)

        logger.debug(f'TheGamesDB:: Found {len(candidate_list)} titles with last request')
        # --- Recursively load more games ---
        next_url = json_data['pages']['next']
        if next_url is not None:
            logger.debug('Recursively loading game page')
            candidate_list = candidate_list + self._retrieve_games_from_url(
                next_url, search_term, platform, scraper_platform, status_dic)
            if not status_dic['status']:
                return None

        return candidate_list

    # Search for the game title.
    # "noms" : [
    #     { "text" : "Super Mario World", "region" : "ss" },
    #     { "text" : "Super Mario World", "region" : "us" },
    #     ...
    # ]
    def _parse_metadata_title(self, game_dic):
        if 'game_title' in game_dic and game_dic['game_title'] is not None:
            title_str = game_dic['game_title']
        else:
            title_str = constants.DEFAULT_META_TITLE

        return title_str

    def _parse_metadata_year(self, online_data):
        if 'release_date' in online_data and online_data['release_date'] is not None and \
           online_data['release_date'] != '':
            year_str = online_data['release_date'][:4]
        else:
            year_str = constants.DEFAULT_META_YEAR
        return year_str

    def _parse_metadata_genres(self, online_data, status_dic):
        if 'genres' not in online_data:
            return ''
        # "genres" : [ 1 , 15 ],
        genre_ids = online_data['genres']
        # log_variable('genre_ids', genre_ids)
        # For some games genre_ids is None. In that case return an empty string (default DB value).
        if not genre_ids:
            return constants.DEFAULT_META_GENRE
        # Convert integers to strings because the cached genres dictionary keys are strings.
        # This is because a JSON limitation.
        genre_ids = [str(id) for id in genre_ids]
        TGDB_genres = self._retrieve_genres(status_dic)
        if not status_dic['status']:
            return None
        genre_list = [TGDB_genres[genre_id] for genre_id in genre_ids]
        return ', '.join(genre_list)

    def _parse_metadata_developer(self, online_data, status_dic):
        if 'developers' not in online_data:
            return ''
        # "developers" : [ 7979 ],
        developers_ids = online_data['developers']
        # For some games developers_ids is None. In that case return an empty string (default DB value).
        if not developers_ids:
            return constants.DEFAULT_META_DEVELOPER
        # Convert integers to strings because the cached genres dictionary keys are strings.
        # This is because a JSON limitation.
        developers_ids = [str(id) for id in developers_ids]
        TGDB_developers = self._retrieve_developers(status_dic)
        if not status_dic['status']:
            return None
        developer_list = [TGDB_developers[dev_id] for dev_id in developers_ids]

        return ', '.join(developer_list)

    def _parse_metadata_nplayers(self, online_data):
        if 'players' in online_data and online_data['players'] is not None:
            nplayers_str = str(online_data['players'])
        else:
            nplayers_str = constants.DEFAULT_META_NPLAYERS

        return nplayers_str

    def _parse_metadata_esrb(self, online_data):
        if 'rating' not in online_data or not online_data['rating']:
            return constants.DEFAULT_META_ESRB
        
        esrb_str = online_data['rating']
        if esrb_str in constants.ESRB_LIST:
            return esrb_str
        if esrb_str.startswith('T'):
            return constants.ESRB_TEEN
        if esrb_str.startswith('EC'):
            return constants.ESRB_EARLY
        if esrb_str.startswith('E10'):
            return constants.ESRB_EVERYONE_10
        if esrb_str.startswith('M'):
            return constants.ESRB_MATURE
        if esrb_str.startswith('AO'):
            return constants.ESRB_ADULTS_ONLY
        if esrb_str.startswith('E'):
            return constants.ESRB_EVERYONE
        return constants.ESRB_PENDING

    def _parse_metadata_plot(self, online_data):
        if 'overview' in online_data and online_data['overview'] is not None:
            plot_str = online_data['overview']
        else:
            plot_str = constants.DEFAULT_META_PLOT

        return plot_str

    def _parse_metadata_tags(self, online_data: dict) -> list:
        tags = []
        if 'coop' in online_data and online_data['coop'] == 'Yes':
            tags.append('co-op')
        if 'hdd' in online_data and online_data['hdd'] != '' and online_data['hdd'] is not None:
            hdd = online_data['hdd']
            tags.append(f'hdd:{hdd}')
        if 'video' in online_data and online_data['video'] not in ('', None):
            tags.append(online_data['video'])
        if 'sound' in online_data and online_data['sound'] not in ('', None):
            tags.append(online_data['sound'])
        return tags

    def _parse_metadata_trailer(self, online_data: dict) -> str:
        if 'youtube' not in online_data:
            return None
        
        trailer_id = online_data['youtube']
        if not trailer_id:
            return None
        return f'plugin://plugin.video.youtube/play/?video_id={trailer_id}'

    # Get a dictionary of TGDB genres (integers) to AKL genres (strings).
    # TGDB genres are cached in an object variable.
    def _retrieve_genres(self, status_dic):
        # --- Cache hit ---
        if self._check_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_GENRES):
            logger.debug('Genres global cache hit.')
            return self._retrieve_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_GENRES)

        # --- Cache miss. Retrieve data ---
        logger.debug('Genres global cache miss. Retrieving genres...')
        url = TheGamesDB.URL_Genres + '?apikey={}'.format(self._get_API_key())
        page_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_genres.json', page_data)

        # --- Update cache ---
        genres = {}
        # Keep genres dictionary keys as strings and not integers. Otherwise, Python json
        # module will conver the integers to strings.
        # https://stackoverflow.com/questions/1450957/pythons-json-module-converts-int-dictionary-keys-to-strings/34346202
        for genre_id in page_data['data']['genres']:
            genres[genre_id] = page_data['data']['genres'][genre_id]['name']
        logger.debug('TheGamesDB._retrieve_genres() There are {} genres'.format(len(genres)))
        self._update_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_GENRES, genres)

        return genres

    def _retrieve_developers(self, status_dic):
        # --- Cache hit ---
        if self._check_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_DEVELOPERS):
            logger.debug('TheGamesDB._retrieve_developers() Genres global cache hit.')
            return self._retrieve_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_DEVELOPERS)

        # --- Cache miss. Retrieve data ---
        logger.debug('TheGamesDB._retrieve_developers() Developers global cache miss. Retrieving developers...')
        url = TheGamesDB.URL_Developers + '?apikey={}'.format(self._get_API_key())
        page_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_developers.json', page_data)

        # --- Update cache ---
        developers = {}
        for developer_id in page_data['data']['developers']:
            developers[developer_id] = page_data['data']['developers'][developer_id]['name']
        logger.debug('TheGamesDB._retrieve_developers() There are {} developers'.format(len(developers)))
        self._update_global_cache(TheGamesDB.GLOBAL_CACHE_TGDB_DEVELOPERS, developers)

        return developers

    # Publishers is not used in AKL at the moment.
    # THIS FUNCTION CODE MUST BE UPDATED.
    def _retrieve_publishers(self, publisher_ids):
        if publisher_ids is None:
            return ''
        if self.publishers is None:
            logger.debug('TheGamesDB. No cached publishers. Retrieving from online.')
            url = TheGamesDB.URL_Publishers + '?apikey={}'.format(self._get_API_key())
            publishers_json, http_code = net.get_URL(url, self._clean_URL_for_log(url), content_type=net.ContentType.JSON)
            if http_code != 200:
                logger.warning("Failure retrieving publishers data.")
                return ""

            self.publishers_cached = {}
            for publisher_id in publishers_json['data']['publishers']:
                self.publishers_cached[int(publisher_id)] = publishers_json['data']['publishers'][publisher_id]['name']
        publisher_names = [self.publishers_cached[publisher_id] for publisher_id in publisher_ids]

        return ' / '.join(publisher_names)

    # Get ALL available assets for game.
    # Cache all assets in the internal disk cache.
    def _retrieve_all_assets(self, candidate, status_dic):
        # --- Cache hit ---
        if self._check_disk_cache(Scraper.CACHE_INTERNAL, self.cache_key):
            logger.debug(f'Internal cache hit "{self.cache_key}"')
            return self._retrieve_from_disk_cache(Scraper.CACHE_INTERNAL, self.cache_key)

        # --- Cache miss. Retrieve data and update cache ---
        logger.debug(f'Internal cache miss "{self.cache_key}"')
        url_tail = '?apikey={}&games_id={}'.format(self._get_API_key(), candidate['id'])
        url = TheGamesDB.URL_Images + url_tail
        asset_list = self._retrieve_assets_from_url(url, candidate['id'], status_dic)
        if not status_dic['status']:
            return None
        logger.debug('A total of {0} assets found for candidate ID {1}'.format(
            len(asset_list), candidate['id']))

        # --- Put metadata in the cache ---
        logger.debug(f'Adding to internal cache "{self.cache_key}"')
        self._update_disk_cache(Scraper.CACHE_INTERNAL, self.cache_key, asset_list)

        return asset_list

    def _retrieve_assets_from_url(self, url, candidate_id, status_dic):
        # --- Read URL JSON data ---
        page_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not status_dic['status']:
            return None
        self._dump_json_debug('TGDB_get_assets.json', page_data)

        # --- Parse images page data ---
        base_url_thumb = page_data['data']['base_url']['thumb']
        base_url = page_data['data']['base_url']['original']
        assets_list = []
        for image_data in page_data['data']['images'][str(candidate_id)]:
            asset_name = '{0} ID {1}'.format(image_data['type'], image_data['id'])
            if image_data['type'] == 'boxart':
                if image_data['side'] == 'front':
                    asset_ID = constants.ASSET_BOXFRONT_ID
                elif image_data['side'] == 'back':
                    asset_ID = constants.ASSET_BOXBACK_ID
                else:
                    raise ValueError
            else:
                asset_ID = TheGamesDB.asset_name_mapping[image_data['type']]
            asset_fname = image_data['filename']

            # url_thumb is mandatory.
            # url is not mandatory here but MobyGames provides it anyway.
            asset_data = self._new_assetdata_dic()
            asset_data['asset_ID'] = asset_ID
            asset_data['display_name'] = asset_name
            asset_data['url_thumb'] = base_url_thumb + asset_fname
            asset_data['url'] = base_url + asset_fname
            if self.verbose_flag:
                logger.debug('TheGamesDB. Found Asset {}'.format(asset_data['name']))
            assets_list.append(asset_data)

        # --- Recursively load more assets ---
        next_url = page_data['pages']['next']
        if next_url is not None:
            logger.debug('TheGamesDB._retrieve_assets_from_url() Recursively loading assets page')
            assets_list = assets_list + self._retrieve_assets_from_url(next_url, candidate_id)

        return assets_list

    # TGDB URLs are safe for printing, however the API key is too long.
    # Clean URLs for safe logging.
    def _clean_URL_for_log(self, url):
        if not url:
            return url

        clean_url = url
        # apikey is followed by more arguments
        clean_url = re.sub('apikey=[^&]*&', 'apikey=***&', clean_url)
        # apikey is at the end of the string
        clean_url = re.sub('apikey=[^&]*$', 'apikey=***', clean_url)
        return clean_url

    # Retrieve URL and decode JSON object.
    # TGDB API info https://api.thegamesdb.net/
    #
    # * When the API number of calls is exhausted TGDB ...
    # * When a game search is not succesfull TGDB returns valid JSON with an empty list.
    def _retrieve_URL_as_JSON(self, url, status_dic):
        json_data, http_code = net.get_URL(url, self._clean_URL_for_log(url), content_type=net.ContentType.JSON)

        # --- Check HTTP error codes ---
        if http_code != 200:
            if http_code == 403:
                error_msg = (
                    'TheGamesDB rejected the API request. '
                    'Check that your API key is valid and that your API allowance '
                    'has not been exhausted.'
                )
            else:
                try:
                    error_msg = json_data['message']
                except Exception:
                    error_msg = 'Unknown/unspecified error.'

            logger.error('TGDB msg "{}"'.format(error_msg))
            self._handle_error(
                status_dic,
                'HTTP code {} message "{}"'.format(http_code, error_msg)
            )
            return None

        # If json_data is None at this point is because of an exception in net_get_URL()
        # which is not urllib2.HTTPError.
        if json_data is None:
            self._handle_error(status_dic, 'TGDB: Network error in net_get_URL()')
            return None

        # Check for scraper overloading. Scraper is disabled if overloaded.
        # Does the scraper return valid JSON when it is overloaded??? I have to confirm this point.
        self._check_overloading(json_data, status_dic)
        if not status_dic['status']:
            return None

        return json_data

    # Checks if TDGB scraper is overloaded (maximum number of API requests exceeded).
    # If the scraper is overloaded is immediately disabled.
    #
    # @param json_data: [dict] Dictionary with JSON data retrieved from TGDB.
    # @returns: [None]
    def _check_overloading(self, json_data, status_dic):
        # This is an integer.
        remaining_monthly_allowance = json_data['remaining_monthly_allowance']
        extra_allowance = json_data['extra_allowance']
        if not extra_allowance:
            extra_allowance = 0
            
        logger.debug('Threshold check: remaining_monthly_allowance = {}'.format(remaining_monthly_allowance))
        logger.debug('Threshold check: extra_allowance = {}'.format(extra_allowance))
        total_allowance = remaining_monthly_allowance + extra_allowance
        
        if total_allowance > 0:
            return
        logger.error('Threshold check: remaining total allowance <= 0')
        logger.error('Disabling TGDB scraper.')
        self.scraper_disabled = True
        status_dic['status'] = False
        status_dic['dialog'] = kodi.KODI_MESSAGE_DIALOG
        status_dic['msg'] = f'TGDB monthly/total allowance is {total_allowance}. Scraper disabled.'
        

# ------------------------------------------------------------------------------------------------
# TheGamesDB supported platforms mapped to AKL platforms.
# ------------------------------------------------------------------------------------------------
DEFAULT_PLAT_TGDB = 0


# NOTE must take into account platform aliases.
# '0' means any platform in TGDB and must be returned when there is no platform matching.
def convert_AKL_platform_to_TheGamesDB(platform_long_name) -> int:
    matching_platform = platforms.get_AKL_platform(platform_long_name)
    if matching_platform.compact_name in AKL_compact_platform_TGDB_mapping:
        return AKL_compact_platform_TGDB_mapping[matching_platform.compact_name]
    
    if matching_platform.aliasof is not None and matching_platform.aliasof in AKL_compact_platform_TGDB_mapping:
        return AKL_compact_platform_TGDB_mapping[matching_platform.aliasof]
        
    # Platform not found.
    return DEFAULT_PLAT_TGDB


def convert_TheGamesDB_platform_to_AKL_platform(tgdb_platform: int) -> platforms.Platform:
    if tgdb_platform in TGDB_AKL_compact_platform_mapping:
        platform_compact_name = TGDB_AKL_compact_platform_mapping[tgdb_platform]
        return platforms.get_AKL_platform_by_compact(platform_compact_name)
        
    return platforms.get_AKL_platform_by_compact(platforms.PLATFORM_UNKNOWN_COMPACT)


AKL_compact_platform_TGDB_mapping = {
    '3do': 25,
    'cpc': 4914,
    'a2600': 22,
    'a5200': 26,
    'a7800': 27,
    'atari-8bit': 30,
    'jaguar': 28,
    'jaguarcd': 29,
    'lynx': 4924,
    'atari-st': 4937,
    'wswan': 4925,
    'wswancolor': 4926,
    'pv1000': 4964,
    'cvision': 31,
    'c64': 40,
    'amiga': 4911,
    'cd32': 4947,
    'vic20': 4945,
    'arcadia2001': 4963,
    'avision': 4974,
    'scvision': 4966,
    'channelf': 4928,
    'fmtmarty': 4932,
    'vectrex': 4939,
    'odyssey2': 4927,
    platforms.PLATFORM_MAME_COMPACT: 23,
    'ivision': 32,
    'msdos': 1,
    'msx': 4929,
    'msx2': 4929,
    'windows': 1,
    'xbox': 14,
    'xbox360': 15,
    'xboxone': 4920,
    'pce': 34,
    'pcecd': 4955,
    'pcfx': 4930,
    'sgx': 34,
    'n3ds': 4912,
    'n64': 3,
    'n64dd': 3,
    'nds': 8,
    'ndsi': 8,
    'fds': 4936,
    'gb': 4,
    'gba': 5,
    'gbcolor': 41,
    'gamecube': 2,
    'nes': 7,
    'pokemini': 4957,
    'snes': 6,
    'switch': 4971,
    'vb': 4918,
    'wii': 9,
    'wiiu': 38,
    'ouya': 4921,
    'studio2': 4967,
    '32x': 33,
    'dreamcast': 16,
    'gamegear': 20,
    'sms': 35,
    'megadrive': 36,
    'megacd': 21,
    'pico': 4958,
    'saturn': 17,
    'sg1000': 4949,
    'x68k': 4931,
    'spectrum': 4913,
    'neocd': 4956,
    'ngp': 4922,
    'ngpcolor': 4923,
    'psx': 10,
    'ps2': 11,
    'ps3': 12,
    'ps4': 4919,
    'psp': 13,
    'psvita': 39,
    'tigergame': 4940,
    'supervision': 4959
}
TGDB_AKL_compact_platform_mapping = {}
for key, value in AKL_compact_platform_TGDB_mapping.items():
    TGDB_AKL_compact_platform_mapping[value] = key
