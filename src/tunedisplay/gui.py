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
        logger.info("Initializing TuneDisplayGUI")
        self.root = tk.Tk()
        self.root.title("TuneDisplay")
        self.root.config(cursor="none")
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.bind("<Escape>", lambda event: self.toggle_fullscreen())

        bg_color = "#2a2a2a"
        fg_color = "#f6f2f2"
        self.root.configure(bg=bg_color)

        # Main container with grid layout
        main_frame = tk.Frame(self.root, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_rowconfigure(0, weight=9)  # 90% for art
        main_frame.grid_rowconfigure(1, weight=1)  # 10% for info
        main_frame.grid_columnconfigure(0, weight=1)

        # Art frame (top, 90%)
        art_frame = tk.Frame(main_frame, bg=bg_color)
        art_frame.grid(row=0, column=0, sticky="nsew")

        self.art_label = tk.Label(art_frame, bg=bg_color)
        self.art_label.pack(fill=tk.BOTH, expand=True)

        # Info frame (bottom, 10%)
        info_frame = tk.Frame(main_frame, bg=bg_color)
        info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))

        # Labels WITHOUT any padding/font yet
        self.title_label = tk.Label(info_frame, text="", fg=fg_color, bg=bg_color, anchor="w")
        self.artist_label = tk.Label(info_frame, text="", fg=fg_color, bg=bg_color, anchor="w")
        self.album_label = tk.Label(info_frame, text="", fg=fg_color, bg=bg_color, anchor="w")

        self.current_image = None
        self.running = True
        self.current_image_path = None

        # ONLY ONE bind
        self.root.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        """Calculate ALL sizing based on actual window dimensions"""
        if event.widget != self.root:
            return

        window_height = self.root.winfo_height()
        window_width = self.root.winfo_width()

        title_size = max(16, int(window_height * 0.06))
        artist_size = max(12, int(window_height * 0.04))
        album_size = max(10, int(window_height * 0.03))
        padding_x = max(5, int(window_width * 0.02))

        # Center the labels vertically within the info_frame
        info_frame = self.title_label.master
        info_frame.grid_rowconfigure(0, weight=1)
        info_frame.grid_rowconfigure(1, weight=1)
        info_frame.grid_rowconfigure(2, weight=1)
        info_frame.grid_columnconfigure(0, weight=1)

        self.title_label.config(font=("Helvetica", title_size, "bold"), padx=padding_x, anchor="center")
        self.title_label.grid(row=0, column=0, sticky="ew")

        self.artist_label.config(font=("Helvetica", artist_size), padx=padding_x, anchor="center")
        self.artist_label.grid(row=1, column=0, sticky="ew")

        self.album_label.config(font=("Helvetica", album_size), padx=padding_x, anchor="center")
        self.album_label.grid(row=2, column=0, sticky="ew")


        if self.current_image_path:
            self.update_album_art(self.current_image_path)

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
            logger.debug(f"Updating album art with: {image_path}")

            # Open the image
            img = Image.open(image_path)

            # Get the current height of the window
            window_height = self.root.winfo_height()

            # Use the full height of the window for the art
            art_size = window_height

            # Calculate new size while maintaining aspect ratio
            width, height = img.size
            if width > height:
                new_width = art_size
                new_height = int(height * (art_size / width))
            else:
                new_height = art_size
                new_width = int(width * (art_size / height))

            # Use simpler image resizing for better performance on Raspberry Pi
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
