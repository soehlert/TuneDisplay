import logging
import tkinter as tk

from PIL import Image, ImageTk
from pathlib import Path
from pythonjsonlogger.json import JsonFormatter

logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_handler = logging.StreamHandler()
formatter = JsonFormatter()
log_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(log_handler)

class TuneDisplayGUI:
    def __init__(self):
        # Create the main window
        logger.info("Initializing TuneDisplayGUI")
        self.root = tk.Tk()
        self.root.title("TuneDisplay")

        # Don't show the mouse cursor
        self.root.config(cursor="none")

        # Make window stay on top
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)

        # Add escape key binding to exit fullscreen
        self.root.bind("<Escape>", lambda event: self.toggle_fullscreen())

        # Set window size (width x height)
        self.root.geometry("600x600")

        # Set background color to black
        bg_color = "#2a2a2a"  # Black
        fg_color = "#f6f2f2"  # White
        # Add transparency (0.0 is fully transparent, 1.0 is opaque)
        self.root.attributes('-alpha', 0.55)

        self.root.configure(bg=bg_color)

        # Create a frame for song information
        info_frame = tk.Frame(self.root, bg=bg_color, padx=20, pady=20)
        info_frame.pack(fill=tk.X, anchor="nw")

        # Create separate labels for title, artist, and album
        self.title_label = tk.Label(
            info_frame,
            text="",
            font=("Helvetica", 48, "bold"),
            fg=fg_color,
            bg=bg_color,
            anchor="w",
            justify="left"
        )
        self.title_label.pack(fill=tk.X, anchor="w")

        self.artist_label = tk.Label(
            info_frame,
            text="",
            font=("Helvetica", 32),
            fg=fg_color,
            bg=bg_color,
            anchor="w",
            justify="left"
        )
        self.artist_label.pack(fill=tk.X, anchor="w")

        self.album_label = tk.Label(
            info_frame,
            text="",
            font=("Helvetica", 24),
            fg=fg_color,
            bg=bg_color,
            anchor="w",
            justify="left"
        )
        self.album_label.pack(fill=tk.X, anchor="w")

        # Create a frame for the album art
        art_frame = tk.Frame(self.root, bg=bg_color)
        art_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add a label for album art
        self.art_label = tk.Label(art_frame, bg=bg_color)
        self.art_label.pack(fill=tk.BOTH, expand=True)

        # Keep a reference to the PhotoImage to prevent garbage collection
        self.current_image = None

        # Flag to track if we're running
        self.running = True

        # Bind resize event to update album art when window size changes
        self.root.bind("<Configure>", self.on_resize)

        # Store the current image path for resize events
        self.current_image_path = None

    def on_resize(self, event):
        """Handle window resize events"""
        # Only process resize events for the root window
        if event.widget == self.root and self.current_image_path:
            # Add a small delay to avoid too many updates
            self.root.after(100, lambda: self.update_album_art(self.current_image_path))

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)

    def update_album_art(self, image_path):
        """Update the displayed album art"""
        if not self.running or not Path(image_path).exists():
            return

        # Store the current image path for resize events
        self.current_image_path = image_path

        try:
            logger.info(f"Updating album art with: {image_path}")

            # Open the image
            img = Image.open(image_path)

            # Calculate available space
            available_height = self.art_label.winfo_height() or 800
            available_width = self.art_label.winfo_width() or 800

            # Ensure we have positive values
            available_height = max(400, available_height)
            available_width = max(400, available_width)

            # Calculate new size while maintaining aspect ratio
            width, height = img.size
            width_ratio = available_width / width
            height_ratio = available_height / height

            # Use the smaller ratio to ensure the image fits completely
            ratio = min(width_ratio, height_ratio)

            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # Reduce animation effects
            self.root.after(0, lambda: self.art_label.config(image=self.current_image))

            # Use simpler image resizing
            img = img.resize((new_width, new_height), Image.Resampling.NEAREST)

            # Convert to PhotoImage and keep a reference
            photo = ImageTk.PhotoImage(img)
            self.current_image = photo  # Keep reference to prevent garbage collection

            # Update the label on the main thread
            self.root.after(0, lambda: self.art_label.config(image=self.current_image))

        except Exception as e:
            logger.exception(f"Error updating album art: {e}")

    def update_song_info(self, title="", artist="", album=""):
        """Update the displayed song information with separate fields"""
        if not self.running:
            return

        logger.info(f"Updating GUI with: {title} - {artist} - {album}")

        # Use after to schedule the updates on the main thread
        if not title and not artist and not album:
            # Not playing anything
            self.root.after(0, lambda: self.title_label.config(text="Currently not playing anything"))
            self.root.after(0, lambda: self.artist_label.config(text=""))
            self.root.after(0, lambda: self.album_label.config(text=""))
        else:
            self.root.after(0, lambda: self.title_label.config(text=title))
            self.root.after(0, lambda: self.artist_label.config(text=artist))
            self.root.after(0, lambda: self.album_label.config(text=f"{album}" if album else ""))

    def clear_album_art(self):
        """Clear the album art"""
        if self.running:
            self.current_image = None
            self.root.after(0, lambda: self.art_label.config(image=''))

    def start(self):
        """Start the GUI main loop"""
        self.root.mainloop()
        self.running = False  # Set flag when mainloop exits

    def close(self):
        """Close the window"""
        self.running = False
        self.root.quit()
        self.root.destroy()
