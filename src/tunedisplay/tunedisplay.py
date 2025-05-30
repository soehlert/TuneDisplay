"""Gather the current playing song from last.fm and display it."""

import argparse
import importlib.metadata
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl
from pythonjsonlogger.json import JsonFormatter

from gui import TuneDisplayGUI

logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_handler = logging.StreamHandler()
formatter = JsonFormatter()
log_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(log_handler)


def open_file(filepath: str) -> None:
    """Open a file with the default application on macOS/Linux."""
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    opener_path = shutil.which(opener)

    if opener_path:
        try:
            # ruff: noqa: S603
            subprocess.run([opener_path, filepath], check=True)

        except FileNotFoundError:
            logger.exception("Command '%s' not found at execution time.", opener_path)
        except subprocess.CalledProcessError as e:
            logger.exception(
                "Command '%s %s' failed with exit code %s.",
                opener_path,
                filepath,
                e.returncode,
            )
    else:
        logger.warning(
            "Could not find the command '%s' in system PATH. Cannot open %s.",
            opener,
            filepath,
        )


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
        default=5,
        help="Seconds to wait between checking Last.fm (default: 5)",
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

    def __str__(self) -> str:
        """Represent a track in string format."""
        art_status = f"URL: {self.art_url}" if self.art_url else "Not available"
        return f"Artist: {self.artist}\nTrack: {self.name}\nAlbum: {self.album}\nAlbum Art: {art_status}"


class LastFmClient:
    """Client to fetch Now Playing data from Last.fm."""

    BASE_URL = "http://ws.audioscrobbler.com/2.0/"
    APP_NAME = "TuneDisplay"
    CONTACT_INFO = "https://github.com/soehlert/tunedisplay"

    def __init__(self, api_key: str, username: str) -> None:
        """Initialize a Last.fm client."""
        if not api_key or not username:
            msg = "API key and username are required."
            raise ValueError(msg)
        self.api_key = api_key
        self.username = username

        try:
            app_version = importlib.metadata.version(self.APP_NAME)
        except importlib.metadata.PackageNotFoundError:
            app_version = "unknown"
            logger.exception("Warning: Could not determine package version for %s.", self.APP_NAME)

        user_agent_string = f"{self.APP_NAME}-{app_version}: {self.CONTACT_INFO}"
        self.headers = {"User-Agent": user_agent_string}

    def _make_request(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Make the API requests."""
        params["api_key"] = self.api_key
        params["user"] = self.username
        params["format"] = "json"

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                logger.error(
                    "Last.fm API Error %s: %s",
                    data.get("error", "N/A"),
                    data.get("message", "No message provided"),
                )
                return None
        except requests.exceptions.RequestException:
            logger.exception("Error connecting to Last.fm API")
            return None
        except json.JSONDecodeError:
            logger.exception("Error decoding the response from Last.fm API.")
            return None
        else:
            return data

    @staticmethod
    def _extract_image_url(track_data: dict[str, Any]) -> str | None:
        """Extract the 'extralarge' image URL or the last available one."""
        art_url: str | None = None
        image_list: list = track_data.get("image")

        if isinstance(image_list, list) and image_list:
            for img in image_list:
                if isinstance(img, dict) and img.get("size") == "extralarge":
                    art_url = img.get("#text")
                    if art_url:
                        break

            if not art_url:
                last_image = image_list[-1]
                if isinstance(last_image, dict):
                    art_url = last_image.get("#text")

        return art_url if art_url else None

    def _create_track(self, track_data: dict[str, Any]) -> Track | None:
        """Create a track object."""
        try:
            artist = track_data.get("artist", {}).get("#text")
            track_name = track_data.get("name")
            album = track_data.get("album", {}).get("#text")

            if not all([artist, track_name, album]):
                logger.warning(
                    "Missing essential track data (artist, name, or album) in: %s",
                    track_data,
                )
                return None

            art_url = self._extract_image_url(track_data)

            track_info = {
                "artist": artist,
                "name": track_name,
                "album": album,
                "art_url": art_url,
            }

            return Track(**track_info)

        except (AttributeError, TypeError, KeyError):
            logger.exception("Error accessing expected keys in track data. Data: %s", track_data)
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
            recent_tracks = data.get("recenttracks", {})
            track_list = recent_tracks.get("track", [])

            if not track_list:
                logger.debug("No recent tracks found in Last.fm response.")
                return None

            latest_track_data = track_list[0]

            attributes = latest_track_data.get("@attr", {})
            if not isinstance(attributes, dict) or attributes.get("nowplaying") != "true":
                logger.debug("Latest track is not marked as 'nowplaying'.")
                return None

            return self._create_track(latest_track_data)

        except (KeyError, IndexError, TypeError):
            logger.exception("Error parsing the main Last.fm response structure. Data: %s", data)
            return None

    def download_album_art(self, track: Track, filename: str = "temp_album_art.png") -> str | None:
        """Download album art for a given track and return the filename."""
        if not track or not track.art_url:
            logger.info("No album art URL available for this track.")
            return None

        try:
            img_response = requests.get(str(track.art_url), stream=True, headers=self.headers, timeout=5)
            img_response.raise_for_status()

            with Path(filename).open("wb") as f:
                for chunk in img_response.iter_content(1024):
                    f.write(chunk)

            return filename

        except requests.exceptions.RequestException:
            logger.exception("Error downloading image")
            return None
        except OSError:
            logger.exception("Error saving image file")
            return None


def run_monitoring_loop(client: LastFmClient, args: argparse.Namespace, image_filename: str, display: TuneDisplayGUI) -> None:
    """Run the main loop to monitor Last.fm Now Playing status."""
    previous_track: Track | None = None
    logger.info(
        "Starting continuous monitoring for user %s",
        client.username,
    )

    while display.running:
        try:
            now_playing_track = client.get_now_playing()

            if now_playing_track != previous_track:
                if now_playing_track:
                    track_dict = now_playing_track.model_dump(mode="json")
                    log_message = "New track playing" if previous_track else "Playback started"
                    event_type = "now_playing_started" if not previous_track else "now_playing_changed"
                    logger.info(log_message, extra={"event_type": event_type, "track_details": track_dict})

                    # Update GUI with track info
                    display.update_song_info(
                        title=now_playing_track.name,
                        artist=now_playing_track.artist,
                        album=now_playing_track.album
                    )

                    if not args.no_art and now_playing_track.art_url:
                        logger.info(
                            "Attempting to download album art",
                            extra={"art_url": str(now_playing_track.art_url)},
                        )
                        # Download art and update GUI
                        art_path = client.download_album_art(now_playing_track, image_filename)
                        if art_path:
                            display.update_album_art(art_path)

                elif previous_track:
                    logger.info(
                        "Playback stopped",
                        extra={
                            "event_type": "now_playing_stopped",
                            "previous_track_details": previous_track.model_dump(mode="json"),
                        },
                    )
                    # Update GUI to show not playing
                    display.update_song_info()
                    display.clear_album_art()

                previous_track = now_playing_track

        except Exception:
            logger.exception("Error during check cycle")
            time.sleep(args.interval * 2)

        time.sleep(args.interval)


def cleanup(image_filename: str) -> None:
    """Perform cleanup tasks on shutdown."""
    logger.info("Performing cleanup")
    if Path(image_filename).exists():
        try:
            Path(image_filename).unlink()
            logger.info("Removed temporary image file: %s", image_filename)
        except OSError:
            logger.exception("Error removing temporary image file %s", image_filename)

def run_monitoring_thread(client, args, image_filename, gui_display):
    """Run the monitoring loop in a separate thread"""
    threading.Thread(
        target=run_monitoring_loop,
        args=(client, args, image_filename, gui_display),
        daemon=True  # This makes the thread exit when the main program exits
    ).start()


if __name__ == "__main__":
    cli_args, lastfm_api_key, lastfm_username, album_art = setup_and_validate()

    try:
        lastfm_client = LastFmClient(api_key=lastfm_api_key, username=lastfm_username)
    except ValueError:
        logger.exception("Client Initialization Error")
        sys.exit(1)

    logger.info("Creating display")
    display = TuneDisplayGUI()

    try:
        # Start monitoring in a separate thread
        run_monitoring_thread(lastfm_client, cli_args, album_art, display)

        # Start the GUI main loop in the main thread
        display.start()

    except KeyboardInterrupt:
        logger.info("Stopping monitoring script due to user request.")
    finally:
        cleanup(album_art)
        sys.exit(0)
