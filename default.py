# -*- coding: utf-8 -*-
#
# TGDB Scraper for AKL
#
# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import sys
import logging
    
# --- Kodi stuff ---
import xbmcaddon

# AKL main imports
from akl import constants, settings, addons
from akl.utils import kodilogging, io, kodi
from akl.scrapers import ScraperSettings, ScrapeStrategy

# Local modules
from resources.lib.scraper import TheGamesDB

kodilogging.config()
logger = logging.getLogger(__name__)

# --- Addon object (used to access settings) ---
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')


# ---------------------------------------------------------------------------------------------
# This is the plugin entry point.
# ---------------------------------------------------------------------------------------------
def run_plugin():
    os_name = io.is_which_os()
    
    # --- Some debug stuff for development ---
    logger.info('------------ Called Advanced Kodi Launcher Plugin: TGDB Scraper ------------')
    logger.info(f'addon.id         "{addon_id}"')
    logger.info(f'addon.version    "{addon_version}"')
    logger.info(f'sys.platform     "{sys.platform}"')
    logger.info(f'OS               "{os_name}"')
    
    for i in range(len(sys.argv)):
        logger.info('sys.argv[{}] "{}"'.format(i, sys.argv[i]))
    
    parser = addons.AklAddonArguments('script.akl.tgdbscraper')
    try:
        parser.parse()
    except Exception as ex:
        logger.error('Exception in plugin', exc_info=ex)
        kodi.dialog_OK(text=parser.get_usage())
        return
        
    if parser.get_command() == addons.AklAddonArguments.SCRAPE:
        run_scraper(parser)
    elif parser.get_command() == addons.AklAddonArguments.SCRAPE_SYSTEM:
        run_system_scraper(parser)
    elif parser.args.cmd == "update-settings":
        update_plugin_settings()
    else:
        kodi.dialog_OK(text=parser.get_help())
        
    logger.debug('Advanced Kodi Launcher Plugin: TGDB Scraper -> exit')


# ---------------------------------------------------------------------------------------------
# Scraper methods.
# ---------------------------------------------------------------------------------------------
def run_scraper(args: addons.AklAddonArguments):
    logger.debug('========== run_scraper() BEGIN ==================================================')
    pdialog = kodi.ProgressDialog()
    
    settings = ScraperSettings.from_settings_dict(args.get_settings())
    scraper_strategy = ScrapeStrategy(
        args.get_webserver_host(),
        args.get_webserver_port(),
        settings,
        TheGamesDB(),
        pdialog)
    
    if args.get_entity_type() == constants.OBJ_ROM:
        logger.debug("Single ROM processing")
        scraped_rom = scraper_strategy.process_single_rom(args.get_entity_id())
        pdialog.endProgress()
        pdialog.startProgress('Saving ROM in database ...')
        scraper_strategy.store_scraped_rom(args.get_akl_addon_id(), args.get_entity_id(), scraped_rom)
        pdialog.endProgress()
    else:
        logger.debug("Multiple ROM processing")
        scraped_roms = scraper_strategy.process_roms(args.get_entity_type(), args.get_entity_id())
        pdialog.endProgress()
        pdialog.startProgress('Saving ROMs in database ...')
        scraper_strategy.store_scraped_roms(args.get_akl_addon_id(),
                                            args.get_entity_type(),
                                            args.get_entity_id(),
                                            scraped_roms)
        pdialog.endProgress()


def run_system_scraper(args: addons.AklAddonArguments):
    logger.debug(
        '========== run_system_scraper() BEGIN '
        '=========================================='
    )

    settings = ScraperSettings.from_settings_dict(
        args.get_settings()
    )

    pdialog = kodi.ProgressDialog()

    tgdb_scraper = TheGamesDB()

    scraper_strategy = ScrapeStrategy(
        args.get_webserver_host(),
        args.get_webserver_port(),
        settings,
        tgdb_scraper,
        pdialog
    )

    pdialog.startProgress(
        'Retrieving system information from TheGamesDB ...',
        100
    )

    asset_paths = {
        asset_id: io.FileName(
            asset_path,
            isdir=True
        )
        for asset_id, asset_path
        in args.get_asset_paths().items()
    }

    system_obj = tgdb_scraper.process_system(
        args.get_platform(),
        args.get_system_name(),
        asset_paths,
        scraper_settings=settings
    )

    if system_obj is None:
        pdialog.endProgress()
        kodi.notify_error(
            'Unable to retrieve system information from TheGamesDB.'
        )
        return

    pdialog.updateProgress(
        90,
        'Saving system information ...'
    )

    scraper_strategy.store_scraped_system(
        args.get_akl_addon_id(),
        args.get_entity_id(),
        system_obj
    )

    pdialog.endProgress()

    logger.debug(
        '========== run_system_scraper() END '
        '============================================'
    )


# ---------------------------------------------------------------------------------------------
# UPDATE PLUGIN
# ---------------------------------------------------------------------------------------------
def update_plugin_settings():
    supported_assets = '|'.join(TheGamesDB.supported_asset_list)
    supported_system_assets = '|'.join(
        TheGamesDB.supported_system_asset_list
    )
    supported_metadata = '|'.join(TheGamesDB.supported_metadata_list)

    settings.setSetting(
        "akl.scraper.supported_assets",
        supported_assets
    )
    settings.setSetting(
        "akl.scraper.supported_system_assets",
        supported_system_assets
    )
    settings.setSetting(
        "akl.scraper.supported_metadata",
        supported_metadata
    )
    kodi.notify("Updated AKL plugin settings for this addon")


# ---------------------------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------------------------
try:
    run_plugin()
except Exception as ex:
    logger.fatal('Exception in plugin', exc_info=ex)
    kodi.notify_error("General failure")
