import argparse
import json
import os
import shutil
import subprocess
import sys

import requests
from pydantic import BaseModel, HttpUrl, ValidationError
from dotenv import load_dotenv


def open_file(filepath):
    """Opens a file with the default application on macOS/Linux."""
    try:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        if shutil.which(opener):
             subprocess.run([opener, filepath], check=True)
        else:
            print(f"Could not find '{opener}' command to open the image.")
            print(f"Image saved as: {filepath}")

    except Exception as e:
        print(f"Error opening image file: {e}")
        print(f"Image saved as: {filepath}")


class Track(BaseModel):
    """Represents a music track with its details using Pydantic."""

    artist: str
    name: str
    album: str
    # Use HttpUrl for validation, Optional if it might be missing
    art_url: HttpUrl | None = None

    def __str__(self):
        """String representation of the track."""
        art_status = f"URL: {self.art_url}" if self.art_url else "Not available"
        return (f"**Artist:** {self.artist}\n"
                f"**Track:** {self.name}\n"
                f"**Album:** {self.album}\n"
                f"**Album Art:** {art_status}")

class LastFmClient:
    """Client to fetch Now Playing data from Last.fm."""

    BASE_URL = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self, api_key, username):
        if not api_key or not username:
            raise ValueError("API key and username are required.")
        self.api_key = api_key
        self.username = username

    def _make_request(self, params):
        """Internal helper to make API requests."""
        params["api_key"] = self.api_key
        params["user"] = self.username
        params["format"] = "json"

        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                 print(f"Last.fm API Error {data['error']}: {data['message']}")
                 return None
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Last.fm API: {e}")
            return None
        except json.JSONDecodeError:
            print("Error decoding the response from Last.fm API.")
            return None

    def get_now_playing(self) -> Track | None:
        """Fetches the currently playing track."""
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

                    if "image" in latest_track_data and isinstance(latest_track_data["image"], list) and len(
                            latest_track_data["image"]) > 0:
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

                    # Validate and create the Pydantic model
                    validated_track = Track(**track_data)
                    return validated_track
                return None
            print("Could not parse track information from Last.fm response.")
            return None
        except (KeyError, IndexError) as e:
            print(f"Error parsing the response data structure. Missing key or index: {e}")
            return None
        except ValidationError as e:
            print(f"Data validation error creating Track object: {e}")
            return None

    @staticmethod
    def download_and_display_art(track: Track, filename="temp_album_art.png"):
        """Downloads and opens the album art for a given track."""
        if not track or not track.art_url:
            print("No album art URL available for this track.")
            return False

        print(f"Downloading album art from: {track.art_url}")
        try:
            # Convert HttpUrl back to string for requests
            img_response = requests.get(str(track.art_url), stream=True)
            img_response.raise_for_status()

            with open(filename, "wb") as f:
                for chunk in img_response.iter_content(1024):
                    f.write(chunk)

            print(f"Opening {filename}...")
            open_file(filename)
            return True

        except requests.exceptions.RequestException as img_e:
            print(f"Error downloading image: {img_e}")
            return False
        except OSError as io_e:
             print(f"Error saving image file: {io_e}")
             return False


if __name__ == "__main__":
    load_dotenv()
    API_KEY = os.environ.get('LASTFM_API_KEY')
    USERNAME = os.environ.get('LASTFM_USERNAME')
    IMAGE_FILENAME = os.environ.get('TUNEDISPLAY_IMAGE_FILENAME')

    parser = argparse.ArgumentParser(description="Fetch Now Playing from Last.fm and optionally display album art.")
    parser.add_argument(
        "--no-art",
        action="store_true",
        help="Disable downloading and displaying album art.",
    )
    args = parser.parse_args()

    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("Error: Please replace 'YOUR_API_KEY' with your actual Last.fm API key.")
        sys.exit(1)
    if not USERNAME or USERNAME == "YOUR_USERNAME":
        print("Error: Please replace 'YOUR_USERNAME' with your actual Last.fm username.")
        sys.exit(1)

    try:
        client = LastFmClient(api_key=API_KEY, username=USERNAME)
        now_playing_track = client.get_now_playing()

        if now_playing_track:
            print("**Now Playing:**")
            print(now_playing_track)

            if args.no_art:
                print("Album art display disabled via --no-art flag.")
            elif now_playing_track.art_url:
                print("Attempting to download and display album art...")
                # Renamed the function slightly for clarity
                client.download_and_display_art(now_playing_track, IMAGE_FILENAME)
            else:
                # This case is handled inside download_and_display_art_dev,
                # but we can add a note here too.
                print("No album art URL found for this track.")

        else:
            print("No track currently playing on Last.fm or failed to retrieve data.")

    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
