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

        # Make window stay on top
        self.root.attributes('-topmost', True)

        # Set window size (width x height) and make it resizable
        self.root.geometry("600x600")
        self.root.minsize(400, 400)  # Set minimum size

        # Create a main frame with padding
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Add a simple label for song information
        self.song_label = tk.Label(main_frame, text="Currently not playing anything", font=("Helvetica", 14))
        self.song_label.pack(pady=10)

        # Create a frame for the album art
        art_frame = tk.Frame(main_frame)
        art_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add a label for album art
        self.art_label = tk.Label(art_frame)
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
            available_height = self.art_label.winfo_height() or 400
            available_width = self.art_label.winfo_width() or 400

            # Ensure we have positive values
            available_height = max(200, available_height)
            available_width = max(200, available_width)

            # Calculate new size while maintaining aspect ratio
            width, height = img.size
            width_ratio = available_width / width
            height_ratio = available_height / height

            # Use the smaller ratio to ensure the image fits completely
            ratio = min(width_ratio, height_ratio)

            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # Resize the image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to PhotoImage and keep a reference
            photo = ImageTk.PhotoImage(img)
            self.current_image = photo  # Keep reference to prevent garbage collection

            # Update the label on the main thread
            self.root.after(0, lambda: self.art_label.config(image=self.current_image))

        except Exception as e:
            logger.exception(f"Error updating album art: {e}")

    def update_song_info(self, song_info):
        """Update the displayed song information"""
        if song_info and self.running:
            logger.info(f"Updating GUI with: {song_info}")
            # Use after to schedule the update on the main thread
            self.root.after(0, lambda: self.song_label.config(text=song_info))

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
