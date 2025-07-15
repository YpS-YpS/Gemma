"""
GUI Application for Game UI Navigation Automation Tool
This provides a user-friendly interface for controlling the automation tool.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import logging
import queue
import yaml
from pathlib import Path

# Add logging handler for GUI
class QueueHandler(logging.Handler):
    """Send logging records to a queue"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)

class HybridConfigParser:
    """Handles loading and parsing both state machine and step-based YAML configurations."""
    
    def __init__(self, config_path: str):
        """Initialize the hybrid config parser."""
        self.config_path = config_path
        self.config = self._load_config()
        self.config_type = self._detect_config_type()
        self._validate_config()
        
        # Extract game metadata
        self.game_name = self.config.get("metadata", {}).get("game_name", "Unknown Game")
        logging.getLogger(__name__).info(f"HybridConfigParser initialized for {self.game_name} using {config_path} (type: {self.config_type})")
    
    def _load_config(self):
        """Load the YAML configuration file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML config: {str(e)}")
    
    def _detect_config_type(self):
        """Detect whether this is a step-based or state machine configuration."""
        if "steps" in self.config:
            return "steps"
        elif "states" in self.config and "transitions" in self.config:
            return "state_machine"
        else:
            logging.getLogger(__name__).warning("Could not determine config type, defaulting to state_machine")
            return "state_machine"
    
    def _validate_config(self):
        """Validate the configuration structure based on detected type."""
        if self.config_type == "steps":
            return self._validate_steps_config()
        else:
            return self._validate_state_machine_config()
    
    def _validate_steps_config(self):
        """Validate step-based configuration."""
        if "steps" not in self.config:
            raise ValueError("Invalid config: missing 'steps' section")
        
        steps = self.config.get("steps", {})
        if not isinstance(steps, dict) or not steps:
            raise ValueError("Invalid config: steps section must be a non-empty dictionary")
        
        return True
    
    def _validate_state_machine_config(self):
        """Validate state machine configuration."""
        required_sections = ["states", "transitions", "initial_state", "target_state"]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Invalid config: missing '{section}' section")
        
        return True
    
    def get_config(self):
        """Get the parsed configuration."""
        return self.config
    
    def get_config_type(self):
        """Get the detected configuration type."""
        return self.config_type
    
    def is_step_based(self):
        """Check if this is a step-based configuration."""
        return self.config_type == "steps"
    
    def get_state_definition(self, state_name: str):
        """Get the definition for a specific state (state machine configs only)."""
        if self.config_type != "state_machine":
            return None
        states = self.config.get("states", {})
        return states.get(state_name)
    
    def get_game_metadata(self):
        """Get game metadata from the configuration."""
        return self.config.get("metadata", {})

class AutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Katana - Game Automator | Ver 1.0.0 | Alpha Release")
        self.root.geometry("1800x900")  # Set initial size
        self.root.minsize(800, 600)
        
        # Variables
        self.sut_ip = tk.StringVar(value="192.168.50.231")
        self.sut_port = tk.StringVar(value="8080")
        self.game_path = tk.StringVar()  # No default value - will be populated from config
        self.lm_studio_url = tk.StringVar(value="http://127.0.0.1:1234")
        self.config_path = tk.StringVar(value="config/games/cs2_simple_rev2.yaml")
        self.max_iterations = tk.StringVar(value="50")
        self.vision_model = tk.StringVar(value="omniparser")  # Default to Omniparser
        self.omniparser_url = tk.StringVar(value="http://localhost:8000")  # Default Omniparser URL
        self.running = False
        self.process_thread = None
        self.game_name = "Unknown Game"  # Added for game-specific paths
        self.path_auto_loaded = False  # Track if path was loaded from config
        
        # Queue for logging
        self.log_queue = queue.Queue()
        self.setup_logger()
        
        # Create GUI elements
        self.create_widgets()
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6)
        self.style.configure("Green.TButton", background="green")
        self.style.configure("Red.TButton", background="red")
        
        # Start queue processing
        self.root.after(100, self.setup_auto_test_if_omniparser)
        
        # Save references to running objects
        self.automation_thread = None
        self.stop_event = threading.Event()

    def setup_auto_test_if_omniparser(self):
        """Setup auto-test if omniparser is selected"""
        if self.vision_model.get() == "omniparser":
            self.root.after(2000, self.auto_test_omniparser)
        else:
            # If not omniparser, show "Not Connected"
            self.omniparser_status_label.config(text="Not Connected", foreground="red")

    def auto_test_omniparser(self):
        """Auto-test omniparser connection"""
        self.omniparser_status_label.config(text="**Testing...**", foreground="blue")
        self.root.after(100, self.perform_auto_test)

    def perform_auto_test(self):
        """Perform the actual auto-test"""
        try:
            import requests
            response = requests.get(f"{self.omniparser_url.get()}/probe", timeout=5)
            if response.status_code == 200:
                self.omniparser_status_label.config(text="Connected", foreground="green")
                self.logger.info("Auto-connected to Omniparser server on startup!")
            else:
                self.omniparser_status_label.config(text="Connection Failed", foreground="red")
                self.logger.info(f"Auto-test failed: HTTP {response.status_code}")
        except Exception as e:
            self.omniparser_status_label.config(text="Connection Failed", foreground="red")
            self.logger.info(f"Auto-test failed (server may not be running): {str(e)}")

    def setup_logger(self):
        """Configure logging to both file and GUI"""
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(f"logs/gui_run_{time.strftime('%Y_%m_%d__%H_%M_%S')}.log", encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Queue handler for GUI
        queue_handler = QueueHandler(self.log_queue)
        # NEW - includes module names like command line
        queue_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                   datefmt='%H:%M:%S')
        queue_handler.setFormatter(queue_formatter)
        self.logger.addHandler(queue_handler)

    def create_widgets(self):
        """Create all the GUI elements with improved layout and organization"""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left and right panes for split layout
        left_pane = ttk.Frame(main_frame)
        right_pane = ttk.Frame(main_frame)
        
        # Place the panes side by side
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # ===== SETTINGS SECTION (LEFT PANE) =====
        settings_frame = ttk.LabelFrame(left_pane, text="Configure settings, connections, and YAML files", padding="10")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ===== GROUP 1: SUT CONNECTION SETTINGS =====
        sut_group = ttk.LabelFrame(settings_frame, text="SUT Connection | SUT IP:Port", padding="10")
        sut_group.pack(fill=tk.X, pady=(0, 10))
        
        # Create a frame for horizontal layout
        sut_row = ttk.Frame(sut_group)
        sut_row.pack(fill=tk.X)
        
        # SUT IP
        ttk.Label(sut_row, text="IP Address:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(sut_row, textvariable=self.sut_ip, width=15).pack(side=tk.LEFT, padx=(0, 15))
        
        # SUT Port
        ttk.Label(sut_row, text="Port:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(sut_row, textvariable=self.sut_port, width=8).pack(side=tk.LEFT)

        # ===== GROUP 2: VISION SYSTEM (LLM & VL Models) =====
        vision_group = ttk.LabelFrame(settings_frame, text="Vision System - LLM & VL Models", padding="10")
        vision_group.pack(fill=tk.X, pady=(0, 10))
        
        # LM Studio URL
        url_row = ttk.Frame(vision_group)
        url_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(url_row, text="LM Studio URL:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(url_row, textvariable=self.lm_studio_url, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Model Selection (Gemma and Qwen VL)
        model_row = ttk.Frame(vision_group)
        model_row.pack(fill=tk.X)
        ttk.Label(model_row, text="Select Model:").pack(side=tk.LEFT, padx=(0, 10))
        
        # Radio buttons for Gemma and Qwen VL
        ttk.Radiobutton(model_row, text="Gemma", variable=self.vision_model, 
                       value="gemma", command=self.update_vision_model_ui).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(model_row, text="Qwen VL", variable=self.vision_model, 
                       value="qwen", command=self.update_vision_model_ui).pack(side=tk.LEFT)
        
        # ===== GROUP 3: OMNIPARSER =====
        omniparser_group = ttk.LabelFrame(settings_frame, text="Omniparser + Flowrunner", padding="10")
        omniparser_group.pack(fill=tk.X, pady=(0, 10))
        
        # Radio button for Omniparser
        omniparser_select_row = ttk.Frame(omniparser_group)
        omniparser_select_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(omniparser_select_row, text="Use Omniparser", variable=self.vision_model, 
                       value="omniparser", command=self.update_vision_model_ui).pack(side=tk.LEFT)
        
        # ADDED: Auto-test omniparser connection on startup
        self.root.after(100, self.setup_auto_test_if_omniparser)

        # Omniparser URL and Test Connection (always visible within this group)
        omniparser_url_row = ttk.Frame(omniparser_group)
        omniparser_url_row.pack(fill=tk.X)
        
        ttk.Label(omniparser_url_row, text="Omniparser URL:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(omniparser_url_row, textvariable=self.omniparser_url, width=25).pack(side=tk.LEFT, padx=(0, 10))
        
        # Connection status and test button
        # self.omniparser_status_label = ttk.Label(omniparser_url_row, text="Not Connected", foreground="red") -- legacy code
        self.omniparser_status_label = ttk.Label(omniparser_url_row, text="**Auto testing in 2 seconds...**", foreground="red")
        self.omniparser_status_label.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(omniparser_url_row, text="Test Connection", 
                  command=self.test_omniparser_connection).pack(side=tk.LEFT)
        
        # ===== GAME AND CONFIG SETTINGS =====
        # These remain outside the groups since they're common to all modes
        game_config_frame = ttk.Frame(settings_frame)
        game_config_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Game Path (modified to show it's a remote path)
        game_path_row = ttk.Frame(game_config_frame)
        game_path_row.pack(fill=tk.X, pady=(0, 10))
        
        # Updated label to indicate this is a remote path
        game_path_label = ttk.Label(game_path_row, text="Game Path (on SUT):")
        game_path_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Add tooltip to explain this is a remote path
        self.create_tooltip(game_path_label, "This is the path to the game executable on the remote SUT system.\nIt will be auto-populated from the config file if available.")
        
        path_entry_frame = ttk.Frame(game_path_row)
        path_entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # The entry field remains the same but we'll add a visual indicator
        self.game_path_entry = ttk.Entry(path_entry_frame, textvariable=self.game_path)
        self.game_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add a label to show if the path was auto-loaded
        self.path_source_label = ttk.Label(path_entry_frame, text="", foreground="green", font=("TkDefaultFont", 8))
        self.path_source_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Replace Browse button with Clear button
        ttk.Button(game_path_row, text="Clear", command=self.clear_game_path).pack(side=tk.LEFT, padx=(0, 5))
        
        # Add a Verify button to check if path exists on SUT
        self.verify_path_button = ttk.Button(game_path_row, text="Verify", command=self.verify_game_path)
        self.verify_path_button.pack(side=tk.LEFT)
        
        # Config File
        config_row = ttk.Frame(game_config_frame)
        config_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(config_row, text="Config File:").pack(side=tk.LEFT, padx=(0, 5))
        config_entry_frame = ttk.Frame(config_row)
        config_entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Entry(config_entry_frame, textvariable=self.config_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(config_row, text="Browse...", command=self.browse_config_path).pack(side=tk.LEFT)
        
        # Max Iterations
        iter_row = ttk.Frame(game_config_frame)
        iter_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(iter_row, text="Max Iterations:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(iter_row, textvariable=self.max_iterations, width=10).pack(side=tk.LEFT)
        
        # Game Info and Config Type
        info_row = ttk.Frame(game_config_frame)
        info_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(info_row, text="Game Info:").pack(side=tk.LEFT, padx=(0, 5))
        self.game_info_label = ttk.Label(info_row, text="No valid config file selected", foreground="blue")
        self.game_info_label.pack(side=tk.LEFT)
        
        config_type_row = ttk.Frame(game_config_frame)
        config_type_row.pack(fill=tk.X)
        ttk.Label(config_type_row, text="Config Type:").pack(side=tk.LEFT, padx=(0, 5))
        self.config_type_label = ttk.Label(config_type_row, text="No config loaded", foreground="gray")
        self.config_type_label.pack(side=tk.LEFT)

        # ===== ACTION BUTTONS =====
        button_frame = ttk.Frame(left_pane)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start Automation", command=self.start_automation)
        self.start_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_automation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Open Logs Folder", command=self.open_logs_folder).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Status indicators
        status_frame = ttk.Frame(left_pane)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, text="Ready", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # ===== SCREENSHOT SECTION =====
        self.image_frame = ttk.LabelFrame(left_pane, text="Latest Screenshot", padding="10")
        self.image_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(self.image_frame, text="Screenshots and annotated images will be saved to the logs folder").pack(padx=5, pady=10)
        ttk.Button(self.image_frame, text="Open Latest Screenshot", command=self.open_latest_screenshot).pack(padx=5, pady=5)
        
        # ===== FOOTER WITH VERSION AND FEEDBACK INFO =====
        # Create some vertical space before the footer
        ttk.Frame(left_pane, height=20).pack()
        
        # Footer frame that will stick to the bottom
        footer_frame = ttk.Frame(left_pane)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Add a horizontal separator line
        ttk.Separator(footer_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 10))
        
        # Version label
        version_label = ttk.Label(footer_frame, 
                                 text="Version 1.0", 
                                 font=("TkDefaultFont", 9, "italic"),
                                 foreground="gray")
        version_label.pack()
        
        # Feedback text
        feedback_label = ttk.Label(footer_frame, 
                                  text="For feedbacks/suggestions and issues please email to",
                                  font=("TkDefaultFont", 8),
                                  foreground="gray")
        feedback_label.pack(pady=(5, 0))
        
        # Email address
        email_label = ttk.Label(footer_frame, 
                               text="satyajit.bhuyan@intel.com",
                               font=("TkDefaultFont", 8, "underline"),
                               foreground="blue",
                               cursor="hand2")
        email_label.pack()
        
        # Make email clickable
        email_label.bind("<Button-1>", lambda e: self.open_email_client())

        # ===== LOG DISPLAY (RIGHT PANE) =====
        log_frame = ttk.LabelFrame(right_pane, text="Logs", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=50, height=40)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.config(state=tk.DISABLED)
        
        # Tag configuration for log levels
        self.log_area.tag_config("INFO", foreground="black")
        self.log_area.tag_config("DEBUG", foreground="gray")
        self.log_area.tag_config("WARNING", foreground="orange")
        self.log_area.tag_config("ERROR", foreground="red")
        self.log_area.tag_config("CRITICAL", foreground="red", background="yellow")
        
        # Load game info if a config file is already selected
        self.load_game_info()

    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = ttk.Label(tooltip, text=text, background="lightyellow", 
                            relief="solid", borderwidth=1, font=("TkDefaultFont", 8))
            label.pack()
            widget.tooltip = tooltip
            
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
                
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def clear_game_path(self):
        """Clear the game path and reset the auto-loaded indicator"""
        self.game_path.set("")
        self.path_auto_loaded = False
        self.path_source_label.config(text="")
        self.game_path_entry.config(background="white")
        self.logger.info("Game path cleared by user")

    def verify_game_path(self):
        """Verify if the game path exists on the SUT"""
        if not self.game_path.get():
            messagebox.showwarning("No Path", "Please enter or load a game path first")
            return
            
        if not self.sut_ip.get() or not self.sut_port.get():
            messagebox.showwarning("No SUT Connection", "Please enter SUT IP and port first")
            return
            
        # This is a placeholder for the verification logic
        # In a real implementation, you would send a request to the SUT to check the path
        self.logger.info(f"Verification requested for path: {self.game_path.get()}")
        messagebox.showinfo("Path Verification", 
                          "Path verification requires the SUT service to be running.\n"
                          "This feature would check if the path exists on the remote system.")

    def open_email_client(self):
        """Open default email client with the feedback email"""
        import webbrowser
        webbrowser.open("mailto:satyajit.bhuyan@intel.com")

    def process_log_queue(self):
        """Process logs from the queue and display them in the GUI"""
        try:
            while True:
                record = self.log_queue.get_nowait()
                self.display_log(record)
        except queue.Empty:
            self.root.after(100, self.process_log_queue)

    def display_log(self, record):
        """Display a log record in the log area"""
        msg = self.format_log_record(record)
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n", record.levelname)
        self.log_area.see(tk.END)  # Scroll to the end
        self.log_area.config(state=tk.DISABLED)

    def format_log_record(self, record):
        """Format a log record for display"""
        formatter = self.logger.handlers[1].formatter
        return formatter.format(record)

    def update_vision_model_ui(self):
        """Update UI based on selected vision model"""
        # Currently, all settings are visible at all times within their groups
        # This method can be extended if you want to hide/show certain elements
        pass
    
    def test_omniparser_connection(self, auto_test=False):
        """Test connection to Omniparser server"""
        try:
            import requests
            response = requests.get(f"{self.omniparser_url.get()}/probe", timeout=5)
            if response.status_code == 200:
                self.omniparser_status_label.config(text="Connected", foreground="green")
                messagebox.showinfo("Success", "Successfully connected to Omniparser server!")
            else:
                self.omniparser_status_label.config(text="Connection Failed", foreground="red")
                messagebox.showerror("Error", f"Failed to connect to Omniparser server: HTTP {response.status_code}")
        except Exception as e:
            self.omniparser_status_label.config(text="Connection Failed", foreground="red")
            messagebox.showerror("Error", f"Failed to connect to Omniparser server: {str(e)}")

    def browse_config_path(self):
        """Open file dialog to browse for config file"""
        filepath = filedialog.askopenfilename(
            title="Select Config File",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if filepath:
            self.config_path.set(filepath)
            # Load game info when a new config is selected
            self.load_game_info()

    def load_game_info(self):
        """Load and display game information from the selected config file"""
        config_file = self.config_path.get()
        if not config_file or not os.path.exists(config_file):
            self.game_info_label.config(text="No valid config file selected")
            self.config_type_label.config(text="No config loaded", foreground="gray")
            # Clear the auto-loaded path if config is invalid
            if self.path_auto_loaded:
                self.clear_game_path()
            return
            
        try:
            # Use HybridConfigParser to detect config type
            config_parser = HybridConfigParser(config_file)
            config = config_parser.get_config()
            metadata = config_parser.get_game_metadata()
            
            # Extract game information
            self.game_name = metadata.get("game_name", os.path.basename(config_file).replace('.yaml', ''))
            benchmark_duration = metadata.get("benchmark_duration", "Unknown")
            resolution = metadata.get("resolution", "Any")
            preset = metadata.get("preset", "Any")
            
            # Update game info display
            self.game_info_label.config(
                text=f"{self.game_name} - Resolution: {resolution}, Preset: {preset}, Benchmark: ~{benchmark_duration}s"
            )
            
            # Update config type display
            config_type = config_parser.get_config_type()
            if config_type == "steps":
                self.config_type_label.config(text="Step-based (SimpleAutomation)", foreground="green")
            else:
                self.config_type_label.config(text="State machine (DecisionEngine)", foreground="blue")
            
            # AUTO-POPULATE GAME PATH FROM METADATA
            # This is the key new functionality
            game_path_in_config = metadata.get("path", "")
            if game_path_in_config:
                # Found a path in the config file
                self.game_path.set(game_path_in_config)
                self.path_auto_loaded = True
                self.path_source_label.config(text="(auto-loaded from config)", foreground="green")
                self.logger.info(f"Auto-populated game path from config: {game_path_in_config}")
                
                # Make the entry field background slightly different to indicate auto-load
                self.game_path_entry.config(background="#f0fff0")  # Very light green
            else:
                # No path in config, but don't clear existing manual entry unless it was auto-loaded
                if self.path_auto_loaded:
                    self.game_path.set("")
                    self.path_source_label.config(text="")
                    self.game_path_entry.config(background="white")
                    self.path_auto_loaded = False
                    self.logger.info("No game path found in config metadata")
                else:
                    # Keep any manually entered path
                    self.logger.info("No game path in config, keeping manually entered path")
            
            self.logger.info(f"Loaded config for game: {self.game_name} (type: {config_type})")
            
        except Exception as e:
            self.game_info_label.config(text=f"Error loading config: {str(e)}")
            self.config_type_label.config(text="Invalid config", foreground="red")
            self.logger.error(f"Failed to load game config: {str(e)}")
            # Clear auto-loaded path on error
            if self.path_auto_loaded:
                self.clear_game_path()

    def clear_logs(self):
        """Clear the log display area"""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)

    def open_logs_folder(self):
        """Open the logs folder for the current or most recent run"""
        if hasattr(self, 'current_run_dir') and self.current_run_dir:
            folder_path = os.path.abspath(self.current_run_dir)
        else:
            # Find most recent run folder
            game_dir = f"logs/{self.game_name}" if self.game_name else "logs"
            os.makedirs(game_dir, exist_ok=True)
            
            run_folders = [f for f in os.listdir(game_dir) if f.startswith("run_")]
            if run_folders:
                latest_run = max(run_folders)  # This works because timestamps are YYYYMMDD_HHMMSS format
                folder_path = os.path.abspath(f"{game_dir}/{latest_run}")
            else:
                folder_path = os.path.abspath(game_dir)
        
        # Platform-specific way to open folder
        if sys.platform == 'win32':
            os.startfile(folder_path)
        elif sys.platform == 'darwin':  # macOS
            import subprocess
            subprocess.Popen(['open', folder_path])
        else:  # Linux
            import subprocess
            subprocess.Popen(['xdg-open', folder_path])

    def open_latest_screenshot(self):
        """Open the latest annotated screenshot from the current or most recent run"""
        if hasattr(self, 'current_run_dir') and self.current_run_dir:
            screenshots_dir = os.path.abspath(f"{self.current_run_dir}/annotated")
        else:
            # Find most recent run folder
            game_dir = f"logs/{self.game_name}" if self.game_name else "logs"
            run_folders = [f for f in os.listdir(game_dir) if f.startswith("run_")]
            if run_folders:
                latest_run = max(run_folders)
                screenshots_dir = os.path.abspath(f"{game_dir}/{latest_run}/annotated")
            else:
                screenshots_dir = os.path.abspath(f"{game_dir}/annotated")
        
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Find the latest screenshot
        try:
            files = [os.path.join(screenshots_dir, f) for f in os.listdir(screenshots_dir) 
                    if f.startswith("annotated_") and f.endswith(".png")]
            if files:
                latest_file = max(files, key=os.path.getmtime)
                
                # Platform-specific way to open image
                if sys.platform == 'win32':
                    os.startfile(latest_file)
                elif sys.platform == 'darwin':  # macOS
                    import subprocess
                    subprocess.Popen(['open', latest_file])
                else:  # Linux
                    import subprocess
                    subprocess.Popen(['xdg-open', latest_file])
            else:
                messagebox.showinfo("No Screenshots", "No annotated screenshots found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open screenshot: {str(e)}")

    def start_automation(self):
        """Start the automation process in a separate thread"""
        # Validate inputs
        try:
            port = int(self.sut_port.get())
            iterations = int(self.max_iterations.get())
            if port <= 0 or iterations <= 0:
                raise ValueError("Port and max iterations must be positive integers")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return
        
        if not self.sut_ip.get():
            messagebox.showerror("Invalid Input", "SUT IP address is required")
            return
            
        # Modified game path validation - now it's a warning instead of an error
        if not self.game_path.get():
            response = messagebox.askyesno("No Game Path", 
                                         "No game path specified. The config file should contain the path.\n\n"
                                         "Do you want to continue anyway?")
            if not response:
                return
            
        if not self.config_path.get() or not os.path.exists(self.config_path.get()):
            messagebox.showerror("Invalid Input", "Config file does not exist")
            return
            
        # Load game info to ensure we have the game name
        self.load_game_info()
            
        # Clear stop event and update GUI state
        self.stop_event.clear()
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Running", foreground="green")
        
        # Start automation in a separate thread
        self.automation_thread = threading.Thread(
            target=self.run_automation,
            daemon=True
        )
        self.automation_thread.start()
        
        # Log start
        self.logger.info(f"Starting automation process for {self.game_name}...")

    def stop_automation(self):
        """Stop the automation process"""
        if self.running and self.automation_thread:
            self.logger.info("Stopping automation process...")
            self.stop_event.set()
            self.running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_label.config(text="Stopped", foreground="red")

    def run_automation(self):
        """Run the main automation process with automatic config type detection"""
        try:
            # Parse configuration with hybrid parser
            config_parser = HybridConfigParser(self.config_path.get())
            config = config_parser.get_config()
            
            if config_parser.is_step_based():
                # Use SimpleAutomation for step-based configs
                self.logger.info("Using SimpleAutomation for step-based configuration")
                self._run_simple_automation(config_parser, config)
            else:
                # Use state machine automation
                self.logger.info("Using state machine automation")
                self._run_state_machine_automation(config_parser, config)
                
        except Exception as e:
            self.logger.error(f"Error in automation process: {str(e)}", exc_info=True)
            self.status_label.config(text="Error", foreground="red")
        finally:
            self.logger.info("Cleaning up resources")
            # Reset GUI state
            self.running = False
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            self.logger.info("Automation process completed")

    def _run_simple_automation(self, config_parser, config):
        """Run automation using SimpleAutomation system."""
        try:
            # Import required modules
            from modules.network import NetworkManager
            from modules.screenshot import ScreenshotManager
            from modules.gemma_client import GemmaClient
            from modules.qwen_client import QwenClient
            from modules.omniparser_client import OmniparserClient
            from modules.annotator import Annotator
            from modules.simple_automation import SimpleAutomation
            from modules.game_launcher import GameLauncher
            import datetime
            
            # Create timestamp for this run
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create game-specific directory structure
            os.makedirs("logs", exist_ok=True)
            game_dir = f"logs/{self.game_name}" if self.game_name else "logs"
            os.makedirs(game_dir, exist_ok=True)

            # Create run-specific directory
            run_dir = f"{game_dir}/run_{timestamp}"
            os.makedirs(run_dir, exist_ok=True)
            os.makedirs(f"{run_dir}/screenshots", exist_ok=True)
            os.makedirs(f"{run_dir}/annotated", exist_ok=True)
            
            # Store the current run directory for later use
            self.current_run_dir = run_dir
            
            # Set up run-specific logging
            run_log_file = f"{run_dir}/automation.log"
            run_file_handler = logging.FileHandler(run_log_file)
            run_file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            run_file_handler.setFormatter(run_file_formatter)
            logging.getLogger().addHandler(run_file_handler)
            
            self.logger.info(f"Created run directory: {run_dir}")
            self.logger.info(f"Logs will be saved to: {run_log_file}")
            
            # Initialize components
            self.logger.info(f"Connecting to SUT at {self.sut_ip.get()}:{self.sut_port.get()}")
            network = NetworkManager(self.sut_ip.get(), int(self.sut_port.get()))
            
            self.logger.info("Initializing components...")
            screenshot_mgr = ScreenshotManager(network)
            
            # Initialize the vision model based on user selection
            if self.vision_model.get() == 'gemma':
                self.logger.info("Using Gemma for UI detection")
                vision_model = GemmaClient(self.lm_studio_url.get())
            elif self.vision_model.get() == 'qwen':
                self.logger.info("Using Qwen VL for UI detection")
                vision_model = QwenClient(self.lm_studio_url.get())
            elif self.vision_model.get() == 'omniparser':
                self.logger.info("Using Omniparser for UI detection")
                vision_model = OmniparserClient(self.omniparser_url.get())
                
            annotator = Annotator()
            game_launcher = GameLauncher(network)
            
            # Get game metadata
            game_metadata = config_parser.get_game_metadata()
            self.logger.info(f"Game metadata loaded: {game_metadata}")
            startup_wait = game_metadata.get("startup_wait", 30)
            
            try:
                # Launch the game only if a path is provided
                if self.game_path.get():
                    self.logger.info(f"Launching game from: {self.game_path.get()}")
                    game_launcher.launch(self.game_path.get())
                    
                    # Wait for game to initialize
                    self.logger.info(f"Waiting {startup_wait} seconds for game to fully initialize...")
                    wait_time = startup_wait
                    for i in range(wait_time):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                        self.status_label.config(text=f"Initializing ({wait_time-i}s)")
                else:
                    self.logger.info("No game path provided, assuming game is already running")
                    self.status_label.config(text="Running (no launch)")
                
                if self.stop_event.is_set():
                    self.logger.info("Automation stopped during initialization")
                    return
                    
                self.status_label.config(text="Running", foreground="green")
                
                # Use SimpleAutomation
                self.logger.info("Starting SimpleAutomation...")
                
                # Configure simple automation with run-specific directory
                simple_auto = SimpleAutomation(
                    config_path=self.config_path.get(),
                    network=network,
                    screenshot_mgr=screenshot_mgr,
                    vision_model=vision_model,
                    stop_event=self.stop_event,
                    run_dir=run_dir,
                    annotator=annotator
                )
                
                # Run the simple automation
                success = simple_auto.run()
                
                # Update UI based on result
                if success:
                    self.status_label.config(text="Completed", foreground="green")
                elif self.stop_event.is_set():
                    self.status_label.config(text="Stopped", foreground="red")
                else:
                    self.status_label.config(text="Failed", foreground="red")
                    
            except Exception as e:
                self.logger.error(f"Error in simple automation execution: {str(e)}", exc_info=True)
                self.status_label.config(text="Error", foreground="red")
                
            finally:
                # Cleanup
                if 'network' in locals():
                    network.close()
                if 'vision_model' in locals() and hasattr(vision_model, 'close'):
                    vision_model.close()
                # Remove the run-specific log handler
                if 'run_file_handler' in locals():
                    logging.getLogger().removeHandler(run_file_handler)
                    
        except Exception as e:
            self.logger.error(f"SimpleAutomation failed: {str(e)}", exc_info=True)

    def _run_state_machine_automation(self, config_parser, config):
        """Run automation using original state machine approach."""
        try:
            # Import required modules
            from modules.network import NetworkManager
            from modules.screenshot import ScreenshotManager
            from modules.gemma_client import GemmaClient
            from modules.qwen_client import QwenClient
            from modules.omniparser_client import OmniparserClient
            from modules.annotator import Annotator
            from modules.decision_engine import DecisionEngine
            from modules.game_launcher import GameLauncher
            import datetime
            
            # Create timestamp for this run
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create game-specific directory structure
            os.makedirs("logs", exist_ok=True)
            game_dir = f"logs/{self.game_name}" if self.game_name else "logs"
            os.makedirs(game_dir, exist_ok=True)

            # Create run-specific directory
            run_dir = f"{game_dir}/run_{timestamp}"
            os.makedirs(run_dir, exist_ok=True)
            os.makedirs(f"{run_dir}/screenshots", exist_ok=True)
            os.makedirs(f"{run_dir}/annotated", exist_ok=True)
            
            # Store the current run directory for later use
            self.current_run_dir = run_dir
            
            # Set up run-specific logging
            run_log_file = f"{run_dir}/automation.log"
            run_file_handler = logging.FileHandler(run_log_file)
            run_file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            run_file_handler.setFormatter(run_file_formatter)
            logging.getLogger().addHandler(run_file_handler)
            
            self.logger.info(f"Created run directory: {run_dir}")
            self.logger.info(f"Logs will be saved to: {run_log_file}")
            
            # Initialize components
            self.logger.info(f"Connecting to SUT at {self.sut_ip.get()}:{self.sut_port.get()}")
            network = NetworkManager(self.sut_ip.get(), int(self.sut_port.get()))
            
            self.logger.info("Initializing components...")
            screenshot_mgr = ScreenshotManager(network)
            
            # Initialize the vision model based on user selection
            if self.vision_model.get() == 'gemma':
                self.logger.info("Using Gemma for UI detection")
                vision_model = GemmaClient(self.lm_studio_url.get())
            elif self.vision_model.get() == 'qwen':
                self.logger.info("Using Qwen VL for UI detection")
                vision_model = QwenClient(self.lm_studio_url.get())
            elif self.vision_model.get() == 'omniparser':
                self.logger.info("Using Omniparser for UI detection")
                vision_model = OmniparserClient(self.omniparser_url.get())
                
            annotator = Annotator()
            decision_engine = DecisionEngine(config)
            game_launcher = GameLauncher(network)
            
            # Get game metadata
            game_metadata = config_parser.get_game_metadata()
            self.logger.info(f"Game metadata loaded: {game_metadata}")
            startup_wait = game_metadata.get("startup_wait", 30)
            
            try:
                # Launch the game only if a path is provided
                if self.game_path.get():
                    self.logger.info(f"Launching game from: {self.game_path.get()}")
                    game_launcher.launch(self.game_path.get())
                    
                    # Wait for game to initialize
                    self.logger.info(f"Waiting {startup_wait} seconds for game to fully initialize...")
                    wait_time = startup_wait
                    for i in range(wait_time):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                        self.status_label.config(text=f"Initializing ({wait_time-i}s)")
                else:
                    self.logger.info("No game path provided, assuming game is already running")
                    self.status_label.config(text="Running (no launch)")
                
                if self.stop_event.is_set():
                    self.logger.info("Automation stopped during initialization")
                    return
                    
                self.status_label.config(text="Running", foreground="green")
                
                # Main execution loop - state machine approach
                iteration = 0
                current_state = "initial"
                target_state = decision_engine.get_target_state()
                
                # Track time spent in each state to detect timeouts
                state_start_time = time.time()
                max_time_in_state = 60  # Default maximum seconds to remain in the same state
                
                while current_state != target_state and iteration < int(self.max_iterations.get()) and not self.stop_event.is_set():
                    iteration += 1
                    self.logger.info(f"Iteration {iteration}: Current state: {current_state}")
                    
                    # Get state-specific timeout
                    state_def = config_parser.get_state_definition(current_state)
                    state_timeout = state_def.get("timeout", max_time_in_state) if state_def else max_time_in_state
                    
                    # Check for timeout in current state
                    time_in_state = time.time() - state_start_time
                    if time_in_state > state_timeout:
                        self.logger.warning(f"Timeout in state {current_state} after {time_in_state:.1f} seconds (limit: {state_timeout}s)")
                        
                        # Get fallback action
                        fallback_action = decision_engine.get_fallback_action(current_state)
                        self.logger.info(f"Using fallback action for timeout: {fallback_action}")
                        
                        # Execute fallback action
                        network.send_action(fallback_action)
                        self.logger.info("Executed timeout recovery action")
                        time.sleep(2)
                        
                        # Reset timeout timer
                        state_start_time = time.time()
                        continue
                    
                    # Capture screenshot - USE RUN-SPECIFIC DIRECTORY
                    screenshot_path = f"{run_dir}/screenshots/screenshot_{iteration}.png"
                    screenshot_mgr.capture(screenshot_path)
                    self.logger.info(f"Screenshot captured: {screenshot_path}")
                    
                    # Process with vision model
                    bounding_boxes = vision_model.detect_ui_elements(screenshot_path)
                    self.logger.info(f"Detected {len(bounding_boxes)} UI elements")
                    
                    # Annotate screenshot - USE RUN-SPECIFIC DIRECTORY
                    annotated_path = f"{run_dir}/annotated/annotated_{iteration}.png"
                    annotator.draw_bounding_boxes(screenshot_path, bounding_boxes, annotated_path)
                    self.logger.info(f"Annotated screenshot saved: {annotated_path}")
                    
                    # Determine next action
                    previous_state = current_state
                    next_action, new_state = decision_engine.determine_next_action(
                        current_state, bounding_boxes
                    )
                    
                    # Format the action for better logging
                    action_str = ""
                    if next_action:
                        if next_action.get("type") == "click":
                            action_str = f"Click at ({next_action.get('x')}, {next_action.get('y')})"
                        elif next_action.get("type") == "key":
                            action_str = f"Press key {next_action.get('key')}"
                        elif next_action.get("type") == "wait":
                            action_str = f"Wait for {next_action.get('duration')} seconds"
                        else:
                            action_str = str(next_action)
                            
                    self.logger.info(f"Next action: {action_str}, transitioning to state: {new_state}")
                    
                    # Execute action
                    if next_action and not self.stop_event.is_set():
                        self.logger.info(f"Executing action: {action_str}")
                        
                        # Handle "wait" actions locally instead of sending to SUT
                        if next_action.get("type") == "wait":
                            duration = next_action.get("duration", 1)
                            self.logger.info(f"Waiting for {duration} seconds...")
                            
                            # Wait in small increments so we can check for stop events
                            for i in range(duration):
                                if self.stop_event.is_set():
                                    self.logger.info("Wait interrupted by stop event")
                                    break
                                time.sleep(1)
                                if i % 10 == 0 and i > 0:  # Log every 10 seconds for long waits
                                    self.logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
                                    
                            self.logger.info(f"Wait completed")
                        else:
                            # Send other action types to SUT
                            network.send_action(next_action)
                            
                        self.logger.info(f"Action completed: {action_str}")
                    
                    # Update state
                    current_state = new_state
                    if previous_state != current_state:
                        # Reset timeout timer when state changes
                        state_start_time = time.time()
                        self.logger.info(f"State changed from {previous_state} to {current_state}")
                    
                    # Get delay from transition if specified
                    transition_key = f"{previous_state}->{current_state}"
                    transition = config.get("transitions", {}).get(transition_key, {})
                    delay = transition.get("expected_delay", 1)
                    
                    time.sleep(delay)  # Wait before next iteration
                
                # Check if we reached the target state
                if current_state == target_state:
                    self.logger.info(f"Successfully reached target state: {target_state}")
                    
                    # Report benchmark results if available
                    if hasattr(decision_engine, "state_context") and "benchmark_duration" in decision_engine.state_context:
                        benchmark_duration = decision_engine.state_context["benchmark_duration"]
                        self.logger.info(f"Benchmark completed in {benchmark_duration:.2f} seconds")
                        
                    self.status_label.config(text="Completed", foreground="green")
                elif self.stop_event.is_set():
                    self.logger.info("Automation process was manually stopped")
                    self.status_label.config(text="Stopped", foreground="red")
                else:
                    self.logger.warning(f"Failed to reach target state. Stopped at: {current_state}")
                    self.status_label.config(text="Failed", foreground="red")
                    
            except Exception as e:
                self.logger.error(f"Error in state machine execution: {str(e)}", exc_info=True)
                self.status_label.config(text="Error", foreground="red")
            
            finally:
                # Cleanup
                if 'network' in locals():
                    network.close()
                if 'vision_model' in locals() and hasattr(vision_model, 'close'):
                    vision_model.close()
                # Remove the run-specific log handler
                if 'run_file_handler' in locals():
                    logging.getLogger().removeHandler(run_file_handler)
                    
        except Exception as e:
            self.logger.error(f"State machine automation failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    # Ensure the modules can be imported
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Create and run the GUI
    root = tk.Tk()
    app = AutomationGUI(root)
    root.mainloop()