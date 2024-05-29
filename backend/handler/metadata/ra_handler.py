import yarl
import requests
import time
import re
from typing import Final, Optional
from typing_extensions import NotRequired, TypedDict
from requests.exceptions import HTTPError, Timeout
from fastapi import HTTPException, status
from redis.commands.search import Search
from redis.commands.search.field import TextField, NumericField

from config import RETROACHIEVEMENTS_USERNAME, RETROACHIEVEMENTS_API_KEY
from handler.redis_handler import cache
from logger.logger import log
from .base_hander import MetadataHandler, PS2_OPL_REGEX, SONY_SERIAL_REGEX

GAMES_INDEX_KEY: Final = "romm:retroachievements_games"

# Create the redis search client
existing_indexes = cache.execute_command('FT._LIST')
redis_search_client = Search(
    client=cache,
    index_key=GAMES_INDEX_KEY,
)
if GAMES_INDEX_KEY not in existing_indexes:
    redis_search_client.create_index([
        TextField("title"),
        NumericField("id"),
        NumericField("console_id"),
    ])

def add_games_to_index(games: list[dict]) -> None:
    for game in games:
        redis_search_client.add_document(
            doc_id=game["game_id"],
            fields={
                "title": game["title"],
                "id": game["id"],
                "console_id": game["console_id"],
            }
        )

RETROACHIEVEMENTS_API_ENABLED: Final = bool(RETROACHIEVEMENTS_USERNAME and RETROACHIEVEMENTS_API_KEY)

PS1_RA_ID: Final = 12
PS2_RA_ID: Final = 21
PSP_RA_ID: Final = 41
ARCADE_RA_IDS: Final = [27]

class RetroAchievementsPlatform(TypedDict):
    ra_id: int
    slug: str
    name: str
    icon: str


class RetroAchievementsMetadata(TypedDict):
    pass


class RetroAchievementsRom(TypedDict):
    ra_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    ra_metadata: Optional[RetroAchievementsMetadata]

class RetroAchievementsHandler(MetadataHandler):
    def __init__(self) -> None:
        self.games_list_url = "https://retroachievements.org/API/API_GetGameList.php"
        self.game_progress_url = (
            "https://retroachievements.org/API/API_GetGameInfoAndUserProgress.php"
        )

    def _request(self, url: yarl.URL, timeout: int = 120) -> dict:
        authorized_url = url.update_query(
            z=RETROACHIEVEMENTS_USERNAME, y=RETROACHIEVEMENTS_API_KEY
        )
        try:
            res = requests.get(authorized_url, timeout=timeout)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.ConnectionError:
            log.critical("Connection error: can't connect to Retroachievements", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Mobygames, check your internet connection",
            )
        except HTTPError as err:
            if err.response.status_code == 429:
                # Retry after 2 seconds if rate limit hit
                time.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
                return {}
        except Timeout:
            # Retry the request once if it times out
            pass

        try:
            res = requests.get(url, timeout=timeout)
            res.raise_for_status()
        except (HTTPError, Timeout) as err:
            # Log the error and return an empty dict if the request fails with a different code
            log.error(err)
            return {}

        return res.json()
    
    def get_platform(self, slug: str) -> RetroAchievementsPlatform:
        platform = SLUG_TO_RETROACHIEVE_ID.get(slug, None)

        if not platform:
            return RetroAchievementsPlatform(ra_id=None, slug=slug)

        return RetroAchievementsPlatform(
            ra_id=platform["id"],
            slug=slug,
            name=platform["name"],
            icon=platform["icon"],
        )
    
    async def get_rom(self, file_name: str, platform_ra_id: int) -> RetroAchievementsRom:
        from handler.filesystem import fs_rom_handler

        if not RETROACHIEVEMENTS_API_ENABLED:
            return RetroAchievementsRom(ra_id=None)

        if not platform_ra_id:
            return RetroAchievementsRom(ra_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = RetroAchievementsRom(ra_id=None)

        # Support for PS2 OPL filename format
        match = re.match(PS2_OPL_REGEX, file_name)
        if platform_ra_id == PS2_RA_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = RetroAchievementsRom(ra_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = re.search(SONY_SERIAL_REGEX, file_name, re.IGNORECASE)
        if platform_ra_id == PS1_RA_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = RetroAchievementsRom(ra_id=None, name=search_term)

        if platform_ra_id == PS2_RA_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = RetroAchievementsRom(ra_id=None, name=search_term)

        if platform_ra_id == PSP_RA_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = RetroAchievementsRom(ra_id=None, name=search_term)

        # Support for MAME arcade filename format
        if platform_ra_id in ARCADE_RA_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = RetroAchievementsRom(ra_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)
        res = self._search_rom(search_term, platform_ra_id)

        # Some MAME games have two titles split by a slash
        if not res and "/" in search_term:
            for term in search_term.split("/"):
                res = self._search_rom(term.strip(), platform_ra_id)
                if res:
                    break

        if not res:
            return fallback_rom

        # rom = {
        #     "ra_id": res["game_id"],
        #     "name": res["title"],
        #     "slug": res["moby_url"].split("/")[-1],
        #     "summary": res.get("description", ""),
        #     "url_cover": pydash.get(res, "sample_cover.image", ""),
        #     "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
        #     "moby_metadata": extract_metadata_from_moby_rom(res),
        # }

    #     return RetroAchievementsRom({k: v for k, v in rom.items() if v})

    # def get_rom_by_id(self, ra_id: int) -> RetroAchievementsRom
    #     if not RETROACHIEVEMENTS_API_ENABLED:
    #         return RetroAchievementsRom(ra_id=None)

    #     url = yarl.URL(self.games_url).with_query(id=ra_id)
    #     roms = self._request(str(url)).get("games", [])
    #     res = pydash.get(roms, "[0]", None)

    #     if not res:
    #         return RetroAchievementsRom(ra_id=None)

    #     rom = {
    #         "ra_id": res["game_id"],
    #         "name": res["title"],
    #         "slug": res["moby_url"].split("/")[-1],
    #         "summary": res.get("description", None),
    #         "url_cover": pydash.get(res, "sample_cover.image", None),
    #         "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
    #         "moby_metadata": extract_metadata_from_moby_rom(res),
    #     }

    #     return RetroAchievementsRom({k: v for k, v in rom.items() if v})

    # def get_matched_roms_by_id(self, ra_id: int) -> list[RetroAchievementsRom]:
    #     if not RETROACHIEVEMENTS_API_ENABLED:
    #         return []

    #     rom = self.get_rom_by_id(ra_id)
    #     return [rom] if rom["ra_id"] else []

    # def get_matched_roms_by_name(
    #     self, search_term: str, platform_ra_id: int
    # ) -> list[RetroAchievementsRom]:
    #     if not RETROACHIEVEMENTS_API_ENABLED:
    #         return []

    #     if not platform_ra_id:
    #         return []

    #     search_term = uc(search_term)
    #     url = yarl.URL(self.games_url).with_query(
    #         platform=[platform_ra_id], title=quote(search_term, safe="/ ")
    #     )
    #     matched_roms = self._request(str(url)).get("games", [])

    #     return [
    #         RetroAchievementsRom(
    #             {
    #                 k: v
    #                 for k, v in {
    #                     "ra_id": rom["game_id"],
    #                     "name": rom["title"],
    #                     "slug": rom["moby_url"].split("/")[-1],
    #                     "summary": rom.get("description", ""),
    #                     "url_cover": pydash.get(rom, "sample_cover.image", ""),
    #                     "url_screenshots": [
    #                         s["image"] for s in rom.get("sample_screenshots", [])
    #                     ],
    #                     "moby_metadata": extract_metadata_from_moby_rom(rom),
    #                 }.items()
    #                 if v
    #             }
    #         )
    #         for rom in matched_roms
    #     ]


# Icons are located at https://static.retroachievements.org/assets/images/system/<icon>
SLUG_TO_RETROACHIEVE_ID: Final = {
    "genesis-slash-megadrive": {
        "id": 1,
        "name": "Genesis/Mega Drive",
        "icon": "md.png",
    },
    "n64": {
        "id": 2,
        "name": "Nintendo 64",
        "icon": "n64.png",
    },
    "snes": {
        "id": 3,
        "name": "SNES/Super Famicom",
        "icon": "snes.png",
    },
    "gb": {
        "id": 4,
        "name": "Game Boy",
        "icon": "gb.png",
    },
    "gba": {
        "id": 5,
        "name": "Game Boy Advance",
        "icon": "gba.png",
    },
    "gbc": {
        "id": 6,
        "name": "Game Boy Color",
        "icon": "gbc.png",
    },
    "nes": {
        "id": 7,
        "name": "NES/Famicom",
        "icon": "nes.png",
    },
    "turbografx16--1": {
        "id": 8,
        "name": "PC Engine/TurboGrafx-16",
        "icon": "pce.png",
    },
    "segacd": {
        "id": 9,
        "name": "Sega CD",
        "icon": "scd.png",
    },
    "sega32": {
        "id": 10,
        "name": "32X",
        "icon": "32x.png",
    },
    "sega-master-system": {
        "id": 11,
        "name": "Master System",
        "icon": "sms.png",
    },
    "ps": {
        "id": 12,
        "name": "PlayStation",
        "icon": "ps1.png",
    },
    "lynx": {
        "id": 13,
        "name": "Atari Lynx",
        "icon": "lynx.png",
    },
    "neo-geo-pocket": {
        "id": 14,
        "name": "Neo Geo Pocket",
        "icon": "ngp.png",
    },
    "gamegear": {
        "id": 15,
        "name": "Game Gear",
        "icon": "gg.png",
    },
    "ngc": {
        "id": 16,
        "name": "GameCube",
        "icon": "gc.png",
    },
    "jaguar": {
        "id": 17,
        "name": "Atari Jaguar",
        "icon": "jag.png",
    },
    "nds": {
        "id": 18,
        "name": "Nintendo DS",
        "icon": "ds.png",
    },
    "wii": {
        "id": 19,
        "name": "Wii",
        "icon": "wii.png",
    },
    "wiiu": {
        "id": 20,
        "name": "Wii U",
        "icon": "wiiu.png",
    },
    "ps2": {
        "id": 21,
        "name": "PlayStation 2",
        "icon": "ps2.png",
    },
    "xbox": {
        "id": 22,
        "name": "Xbox",
        "icon": "xbox.png",
    },
    "odyssey-2": {
        "id": 23,
        "name": "Magnavox Odyssey 2",
        "icon": "mo2.png",
    },
    "pokemon-mini": {
        "id": 24,
        "name": "Pokemon Mini",
        "icon": "mini.png",
    },
    "atari2600": {
        "id": 25,
        "name": "Atari 2600",
        "icon": "2600.png",
    },
    "dos": {
        "id": 26,
        "name": "DOS",
        "icon": "dos.png",
    },
    "arcade": {
        "id": 27,
        "name": "Arcade",
        "icon": "arc.png",
    },
    "virtualboy": {
        "id": 28,
        "name": "Virtual Boy",
        "icon": "vb.png",
    },
    "msx": {
        "id": 29,
        "name": "MSX",
        "icon": "msx.png",
    },
    "c64": {
        "id": 30,
        "name": "Commodore 64",
        "icon": "c64.png",
    },
    "sinclair-zx81": {
        "id": 31,
        "name": "ZX81",
        "icon": "zx81.png",
    },
    "oric": {
        "id": 32,
        "name": "Oric",
        "icon": "oric.png",
    },
    "sg1000": {
        "id": 33,
        "name": "SG-1000",
        "icon": "sg1k.png",
    },
    "vic-20": {
        "id": 34,
        "name": "VIC-20",
        "icon": "vic-20.png",
    },
    "amiga": {
        "id": 35,
        "name": "Amiga",
        "icon": "amiga.png",
    },
    "atari-st": {
        "id": 36,
        "name": "Atari ST",
        "icon": "ast.png",
    },
    "acpc": {
        "id": 37,
        "name": "Amstrad CPC",
        "icon": "cpc.png",
    },
    "appleii": {
        "id": 38,
        "name": "Apple II",
        "icon": "a2.png",
    },
    "saturn": {
        "id": 39,
        "name": "Saturn",
        "icon": "sat.png",
    },
    "dc": {
        "id": 40,
        "name": "Dreamcast",
        "icon": "dc.png",
    },
    "psp": {
        "id": 41,
        "name": "PlayStation Portable",
        "icon": "psp.png",
    },
    "philips-cd-i": {
        "id": 42,
        "name": "Philips CD-i",
        "icon": "cd-i.png",
    },
    "3do": {
        "id": 43,
        "name": "3DO Interactive Multiplayer",
        "icon": "3do.png",
    },
    "colecovision": {
        "id": 44,
        "name": "ColecoVision",
        "icon": "cv.png",
    },
    "intellivision": {
        "id": 45,
        "name": "Intellivision",
        "icon": "intv.png",
    },
    "vectrex": {
        "id": 46,
        "name": "Vectrex",
        "icon": "vect.png",
    },
    "pc-8800-series": {
        "id": 47,
        "name": "PC-8000/8800",
        "icon": "8088.png",
    },
    "pc-9800-series": {
        "id": 48,
        "name": "PC-9800",
        "icon": "9800.png",
    },
    "pc-fx": {
        "id": 49,
        "name": "PC-FX",
        "icon": "pc-fx.png",
    },
    "atari5200": {
        "id": 50,
        "name": "Atari 5200",
        "icon": "5200.png",
    },
    "atari7800": {
        "id": 51,
        "name": "Atari 7800",
        "icon": "7800.png",
    },
    "sharp-x68000": {
        "id": 52,
        "name": "Sharp X68000",
        "icon": "x68k.png",
    },
    "wonderswan": {
        "id": 53,
        "name": "WonderSwan",
        "icon": "ws.png",
    },
    "epoch-cassette-vision": {
        "id": 54,
        "name": "Cassette Vision",
        "icon": "ecv.png",
    },
    "epoch-super-cassette-vision": {
        "id": 55,
        "name": "Super Cassette Vision",
        "icon": "escv.png",
    },
    "neo-geo-cd": {
        "id": 56,
        "name": "Neo Geo CD",
        "icon": "ngcd.png",
    },
    "fairchild-channel-f": {
        "id": 57,
        "name": "Fairchild Channel F",
        "icon": "chf.png",
    },
    "fm-towns": {
        "id": 58,
        "name": "FM Towns",
        "icon": "fm-towns.png",
    },
    "zxs": {
        "id": 59,
        "name": "ZX Spectrum",
        "icon": "zxs.png",
    },
    "g-and-w": {
        "id": 60,
        "name": "Game & Watch",
        "icon": "g&w.png",
    },
    "ngage": {
        "id": 61,
        "name": "Nokia N-Gage",
        "icon": "n-gage.png",
    },
    "3ds": {
        "id": 62,
        "name": "Nintendo 3DS",
        "icon": "3ds.png",
    },
    "supervision": {
        "id": 63,
        "name": "Watara Supervision",
        "icon": "wsv.png",
    },
    "x1": {
        "id": 64,
        "name": "Sharp X1",
        "icon": "x1.png",
    },
    "tic-80": {
        "id": 65,
        "name": "TIC-80",
        "icon": "tic-80.png",
    },
    "thomson-to": {
        "id": 66,
        "name": "Thomson TO8",
        "icon": "to8.png",
    },
    "nec-pc-6000-series": {
        "id": 67,
        "name": "PC-6000",
        "icon": "pc-6000.png",
    },
    "pico": {
        "id": 68,
        "name": "Sega Pico",
        "icon": "pico.png",
    },
    "mega-duck-slash-cougar-boy": {
        "id": 69,
        "name": "Mega Duck",
        "icon": "duck.png",
    },
    "zeebo": {
        "id": 70,
        "name": "Zeebo",
        "icon": "zeebo.png",
    },
    "arduboy": {
        "id": 71,
        "name": "Arduboy",
        "icon": "ard.png",
    },
    "wasm-4": {
        "id": 72,
        "name": "WASM-4",
        "icon": "wasm4.png",
    },
    "arcadia-2001": {
        "id": 73,
        "name": "Arcadia 2001",
        "icon": "a2001.png",
    },
    "vc-4000": {
        "id": 74,
        "name": "Interton VC 4000",
        "icon": "vc4000.png",
    },
    "elektor": {
        "id": 75,
        "name": "Elektor TV Games Computer",
        "icon": "elek.png",
    },
    "turbografx-16-slash-pc-engine-cd": {
        "id": 76,
        "name": "PC Engine CD/TurboGrafx-CD",
        "icon": "pccd.png",
    },
    "atari-jaguar-cd": {
        "id": 77,
        "name": "Atari Jaguar CD",
        "icon": "jcd.png",
    },
    "nintendo-dsi": {
        "id": 78,
        "name": "Nintendo DSi",
        "icon": "dsi.png",
    },
    "ti-programmable-calculator": {
        "id": 79,
        "name": "TI-83",
        "icon": "ti-83.png",
    },
    "uzebox": {
        "id": 80,
        "name": "Uzebox",
        "icon": "uze.png",
    },
    "standalone": {
        "id": 102,
        "name": "Standalone",
        "icon": "exe.png",
    },
}


# Reverse lookup
RETROACHIEVE_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_RETROACHIEVE_ID.items()}
