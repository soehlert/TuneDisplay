# TuneDisplay

A simple Python script to monitor and display your currently playing track from Last.fm. It shows the artist, track, album, and album art.

## Requirements

*   Python 3.9+
*   [uv](https://github.com/astral-sh/uv) (Python package installer and virtual environment manager)
*   A Last.fm account and API Key ([Get one here](https://www.last.fm/api/account/create))
*   For album art display locally during development (optional): `xdg-open` (Linux) or `open` (macOS)

## Installation

```bash
git clone https://github.com/soehlert/tunedisplay.git
cd tunedisplay
uv venv
source .venv/bin/activate
uv pip install .
```
    
### Configuration
Create a .env file in the tunedisplay directory.
Add your Last.fm credentials to the .env file:

```Text Only
# Required:
LASTFM_API_KEY=YOUR_ACTUAL_API_KEY
LASTFM_USERNAME=YOUR_LASTFM_USERNAME

# Optional: Customize the temporary image filename
TUNEDISPLAY_IMAGE_FILENAME=album_art.png
```

### Usage
Run the script from the terminal within the project directory:

``` bash
python tunedisplay.py
```
The script will start checking Last.fm periodically. When a track is playing it will display album art. 

### Command-line Options

```Text Only
--no-art: Prevents the script from downloading or displaying album art.
$ python tunedisplay.py --no-art

--interval <seconds>: Sets how often (in seconds) the script checks Last.fm. Default is 3 seconds.
$ python tunedisplay.py --interval 10
```

### License
This project is licensed under the MIT License. See the LICENSE file for details.