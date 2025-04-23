"""Gather the current playing song from last.fm and display it."""

import argparse
import importlib.metadata
import json
import logging
import os
import shutil
import subprocess
import sys
import time

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, ValidationError
from pythonjsonlogger.json import JsonFormatter

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = JsonFormatter()
logHandler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(logHandler)


def open_file(filepath):
    """Opens a file with the default application on macOS/Linux."""
    try:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        if shutil.which(opener):
            subprocess.run([opener, filepath], check=True)
        else:
            logger.error("Could not find %s command to open the image.", opener)
    except Exception as e:
        logger.error("Error opening image file: %s", e)


def setup_and_validate() -> tuple[argparse.Namespace, str, str, str]:
    """Load config, parse args, and validate required settings."""
    load_dotenv()

    api_key = os.environ.get("LASTFM_API_KEY")
    username = os.environ.get("LASTFM_USERNAME")
    image_filename = os.environ.get("TUNEDISPLAY_IMAGE_FILENAME") or "lastfm_nowplaying_art.png"

    parser = argparse.ArgumentParser(description="Fetch Now Playing from Last.fm and optionally display album art.")
    parser.add_argument(
        "--no-art",
        action="store_true",
        help="Disable downloading and displaying album art",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3,
        help="Seconds to wait between checking Last.fm (default: 3)",
    )
    args = parser.parse_args()

    if not api_key or api_key == "YOUR_API_KEY":
        logger.error("Configuration Error: Last.fm API key not found or is placeholder.")
        sys.exit("Please provide LASTFM_API_KEY via .env or environment variable.")
    if not username or username == "YOUR_USERNAME":
        logger.error("Configuration Error: Last.fm username not found or is placeholder.")
        sys.exit("Please provide LASTFM_USERNAME via .env or environment variable.")

    return args, api_key, username, image_filename


class Track(BaseModel):
    """Represent a music track."""

    artist: str
    name: str
    album: str
    # Use HttpUrl for validation, Optional if it might be missing
    art_url: HttpUrl | None = None

    def __str__(self):
        """String representation of the track."""
        art_status = f"URL: {self.art_url}" if self.art_url else "Not available"
        return f"Artist: {self.artist}\nTrack: {self.name}\nAlbum: {self.album}\nAlbum Art: {art_status}"


class LastFmClient:
    """Client to fetch Now Playing data from Last.fm."""

    BASE_URL = "http://ws.audioscrobbler.com/2.0/"
    APP_NAME = "TuneDisplay"
    CONTACT_INFO = "https://github.com/soehlert/tunedisplay"

    def __init__(self, api_key, username):
        if not api_key or not username:
            raise ValueError("API key and username are required.")
        self.api_key = api_key
        self.username = username

        try:
            app_version = importlib.metadata.version("tunedisplay")
        except importlib.metadata.PackageNotFoundError:
            app_version = "unknown"
            logger.error("Warning: Could not determine package version for %s.", self.APP_NAME)

        user_agent_string = f"{self.APP_NAME}-{app_version}: {self.CONTACT_INFO}"
        self.headers = {"User-Agent": user_agent_string}

    def _make_request(self, params):
        """Make the API requests."""
        params["api_key"] = self.api_key
        params["user"] = self.username
        params["format"] = "json"

        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                logger.error("Last.fm API Error %s: %s", data["error"], data["message"])
                return None
            return data
        except requests.exceptions.RequestException as e:
            logger.error("Error connecting to Last.fm API: %s", e)
            return None
        except json.JSONDecodeError:
            logger.error("Error decoding the response from Last.fm API.")
            return None

    def get_now_playing(self) -> Track | None:
        """Fetch the currently playing track."""
        params = {
            "method": "user.getrecenttracks",
            "limit": 1,
        }
        data = self._make_request(params)

        if not data:
            return None

        try:
            if "recenttracks" in data and "track" in data["recenttracks"] and data["recenttracks"]["track"]:
                latest_track_data = data["recenttracks"]["track"][0]

                if "@attr" in latest_track_data and latest_track_data["@attr"].get("nowplaying") == "true":
                    artist = latest_track_data["artist"]["#text"]
                    track_name = latest_track_data["name"]
                    album = latest_track_data["album"]["#text"]
                    art_url_str = None

                    if (
                        "image" in latest_track_data
                        and isinstance(latest_track_data["image"], list)
                        and len(latest_track_data["image"]) > 0
                    ):
                        for img in latest_track_data["image"]:
                            if img.get("size") == "extralarge":
                                art_url_str = img.get("#text")
                                break
                        if not art_url_str and latest_track_data["image"][-1]:
                            art_url_str = latest_track_data["image"][-1].get("#text")

                    track_data = {
                        "artist": artist,
                        "name": track_name,
                        "album": album,
                        "art_url": art_url_str if art_url_str else None,
                    }
                    validated_track = Track(**track_data)
                    return validated_track

                return None
            logger.warning("Could not parse track information from Last.fm response.")
            return None
        except (KeyError, IndexError) as e:
            logger.error("Error parsing the response data structure. Missing key or index: %s", e)
            return None
        except ValidationError as e:
            logger.error("Data validation error creating Track object: %s", e)
            return None

    def download_and_display_art(self, track: Track, filename="temp_album_art.png"):
        """Download and open the album art for a given track."""
        if not track or not track.art_url:
            logger.info("No album art URL available for this track.")
            return False

        try:
            img_response = requests.get(str(track.art_url), stream=True, headers=self.headers)
            img_response.raise_for_status()

            with open(filename, "wb") as f:
                for chunk in img_response.iter_content(1024):
                    f.write(chunk)

            open_file(filename)
            return True

        except requests.exceptions.RequestException as img_e:
            logging.exception("Error downloading image: %s", img_e)
            return False
        except OSError as io_e:
            logging.exception("Error saving image file: %s", io_e)
            return False


def run_monitoring_loop(client: LastFmClient, args: argparse.Namespace, image_filename: str):
    """Run the main loop to monitor Last.fm Now Playing status."""
    previous_track: Track | None = None
    logger.info(
        "Starting continuous monitoring for user '%s'.",
        client.username,
    )

    while True:
        try:
            now_playing_track = client.get_now_playing()

            if now_playing_track != previous_track:
                if now_playing_track:
                    track_dict = now_playing_track.model_dump(mode="json")
                    log_message = "New track playing" if previous_track else "Playback started"
                    event_type = "now_playing_started" if not previous_track else "now_playing_changed"
                    logger.info(log_message, extra={"event_type": event_type, "track_details": track_dict})

                    if not args.no_art and now_playing_track.art_url:
                        logger.info(
                            "Attempting to download and display album art",
                            extra={"art_url": str(now_playing_track.art_url)},
                        )
                        client.download_and_display_art(now_playing_track, image_filename)

                elif previous_track:
                    logger.info(
                        "Playback stopped",
                        extra={
                            "event_type": "now_playing_stopped",
                            "previous_track_details": previous_track.model_dump(mode="json"),
                        },
                    )

                previous_track = now_playing_track

        except Exception as loop_error:
            logger.error("Error during check cycle: %s", loop_error, exc_info=True)
            time.sleep(args.interval * 2)

        time.sleep(args.interval)


def cleanup(image_filename: str):
    """Perform cleanup tasks on shutdown."""
    logger.info("Performing cleanup...")
    if os.path.exists(image_filename):
        try:
            os.remove(image_filename)
            logger.info("Removed temporary image file: %s", image_filename)
        except OSError as e:
            logger.error("Error removing temporary image file '%s': %s", image_filename, e, exc_info=True)


if __name__ == "__main__":
    cli_args, lastfm_api_key, lastfm_username, album_art = setup_and_validate()

    try:
        lastfm_client = LastFmClient(api_key=lastfm_api_key, username=lastfm_username)
    except ValueError as ve:
        logger.error("Client Initialization Error: %s", ve, exc_info=True)
        sys.exit(1)

    try:
        run_monitoring_loop(lastfm_client, cli_args, album_art)
    except KeyboardInterrupt:
        logger.info("Stopping monitoring script due to user request.")
        cleanup(album_art)
        sys.exit(0)
    except Exception as main_error:
        logger.error("An unexpected critical error occurred in the main loop: %s", main_error, exc_info=True)
        cleanup(album_art)
        sys.exit(1)
