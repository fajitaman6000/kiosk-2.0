import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from pathlib import Path
import datetime
import zipfile
import threading

# Import archive functionality from log_archive.py
from log_archive import archive_old_logs

class LogViewer(tk.Tk):
    """Simple utility to view kiosk log files."""
    def __init__(self):
        super().__init__()
        self.title("Kiosk Log Viewer")
        self.geometry("1000x700")
        
        # Create menu bar
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        
        # File menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open Log...", command=self.browse_log_file)
        self.file_menu.add_command(label="Refresh Log List", command=self.refresh_log_list)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Archive Old Logs...", command=self.show_archive_dialog)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit)
        
        # Help menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="Filter Instructions", command=self.show_filter_help)
        
        # Set up the main frame
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # File selection area
        self.file_frame = ttk.Frame(self.main_frame)
        self.file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.file_frame, text="Log File:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.file_var = tk.StringVar()
        self.file_combo = ttk.Combobox(self.file_frame, textvariable=self.file_var, width=50)
        self.file_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.file_combo.bind("<<ComboboxSelected>>", self.load_selected_log)
        
        ttk.Button(self.file_frame, text="Refresh", command=self.refresh_log_list).pack(side=tk.LEFT)
        ttk.Button(self.file_frame, text="Load", command=self.load_selected_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.file_frame, text="Browse...", command=self.browse_log_file).pack(side=tk.LEFT)
        ttk.Button(self.file_frame, text="Archive...", command=self.show_archive_dialog).pack(side=tk.LEFT, padx=5)
        
        # Filter frame
        self.filter_frame = ttk.Frame(self.main_frame)
        self.filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(self.filter_frame, textvariable=self.filter_var, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_entry.bind("<Return>", lambda e: self.apply_filter())
        
        ttk.Button(self.filter_frame, text="Apply Filter", command=self.apply_filter).pack(side=tk.LEFT)
        ttk.Button(self.filter_frame, text="Clear Filter", command=self.clear_filter).pack(side=tk.LEFT, padx=5)
        
        self.error_only_var = tk.BooleanVar()
        ttk.Checkbutton(self.filter_frame, text="Show Errors Only", variable=self.error_only_var, 
                        command=self.apply_filter).pack(side=tk.LEFT, padx=10)
        
        # Help button for filter instructions
        ttk.Button(self.filter_frame, text="?", width=2, 
                  command=self.show_filter_help).pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh
        self.auto_refresh_var = tk.BooleanVar()
        self.auto_refresh_cb = ttk.Checkbutton(self.filter_frame, text="Auto-refresh", 
                                      variable=self.auto_refresh_var)
        self.auto_refresh_cb.pack(side=tk.RIGHT, padx=5)
        
        # Log content area
        self.log_text = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, 
                                                 width=120, height=30, 
                                                 font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, 
                                   relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        
        # Initialize
        self.log_dir = Path("logs")
        self.current_file = None
        self.full_content = []
        self.refresh_log_list()
        
        # Auto-refresh timer
        self.after(1000, self.check_auto_refresh)
    
    def refresh_log_list(self):
        """Refresh the list of available log files."""
        if not self.log_dir.exists():
            self.status_var.set(f"Log directory not found: {self.log_dir}")
            return
            
        log_files = sorted(list(self.log_dir.glob("*.txt")), reverse=True)
        self.file_combo['values'] = [f.name for f in log_files]
        
        if log_files and not self.file_var.get():
            self.file_var.set(log_files[0].name)
            self.load_selected_log()
            
        self.status_var.set(f"Found {len(log_files)} log files in {self.log_dir}")
    
    def load_selected_log(self, event=None):
        """Load the currently selected log file."""
        filename = self.file_var.get()
        if not filename:
            self.status_var.set("No log file selected")
            return
            
        log_path = self.log_dir / filename
        self.load_log_file(log_path)
    
    def browse_log_file(self):
        """Open a file browser to select a log file."""
        initial_dir = self.log_dir if self.log_dir.exists() else os.getcwd()
        filepath = filedialog.askopenfilename(
            title="Select Log File",
            initialdir=initial_dir,
            filetypes=[("Log Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if filepath:
            path = Path(filepath)
            self.file_var.set(path.name)
            self.load_log_file(path)
    
    def load_log_file(self, filepath):
        """Load a log file and display its contents."""
        try:
            self.current_file = filepath
            with open(filepath, 'r', encoding='utf-8') as f:
                self.full_content = f.readlines()
                
            self.apply_filter()  # Apply any active filters
            self.status_var.set(f"Loaded {filepath} ({len(self.full_content)} lines)")
        except Exception as e:
            self.status_var.set(f"Error loading log file: {str(e)}")
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, f"Error loading log file: {str(e)}")
    
    def apply_filter(self):
        """Apply filter to the log content."""
        if not self.full_content:
            return
            
        filter_text = self.filter_var.get().lower()
        error_only = self.error_only_var.get()
        
        # Clear current display
        self.log_text.delete(1.0, tk.END)
        
        # Apply filters
        filtered_lines = []
        for line in self.full_content:
            if error_only and "[ERROR]" not in line and "EXCEPTION" not in line:
                continue
                
            if filter_text and filter_text not in line.lower():
                continue
                
            filtered_lines.append(line)
        
        # Display filtered content
        for line in filtered_lines:
            # Color coding for errors
            if "[ERROR]" in line or "EXCEPTION" in line:
                self.log_text.insert(tk.END, line, "error")
            elif "WARNING" in line:
                self.log_text.insert(tk.END, line, "warning")
            else:
                self.log_text.insert(tk.END, line)
        
        # Configure tags for coloring
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")
        
        # Scroll to end
        self.log_text.see(tk.END)
        
        self.status_var.set(f"Showing {len(filtered_lines)} of {len(self.full_content)} lines")
    
    def clear_filter(self):
        """Clear all filters and show all content."""
        self.filter_var.set("")
        self.error_only_var.set(False)
        self.apply_filter()
    
    def check_auto_refresh(self):
        """Check if auto-refresh is enabled and reload the current file if it is."""
        if self.auto_refresh_var.get() and self.current_file:
            self.load_log_file(self.current_file)
        
        # Schedule next check
        self.after(5000, self.check_auto_refresh)  # Check every 5 seconds
    
    def show_filter_help(self):
        """Show instructions for using the filter features."""
        help_text = """
Filter Instructions:

1. Text Filter:
   - Enter text in the filter box to show only lines containing that text
   - Filter is case-insensitive
   - Press Enter or click "Apply Filter" to apply
   - Click "Clear Filter" to remove all filters

2. Error Filter:
   - Check "Show Errors Only" to display only error and exception messages
   - This highlights errors in red and warnings in orange

3. Auto-refresh:
   - Enable "Auto-refresh" to automatically reload the current log file every 5 seconds
   - Useful for monitoring active logs during application runtime

Tips:
   - Use specific keywords to narrow down results (e.g., "network", "video")
   - Combine text filter with error filter to find specific errors
   - Filters apply only to the display, not the actual log file
        """
        messagebox.showinfo("Filter Instructions", help_text)
    
    def show_archive_dialog(self):
        """Show dialog for archiving old log files."""
        archive_window = tk.Toplevel(self)
        archive_window.title("Archive Old Log Files")
        archive_window.geometry("400x300")
        archive_window.resizable(False, False)
        archive_window.transient(self)  # Make it a child of the main window
        archive_window.grab_set()  # Make it modal
        
        # Frame for options
        options_frame = ttk.Frame(archive_window, padding=15)
        options_frame.pack(fill=tk.BOTH, expand=True)
        
        # Options
        ttk.Label(options_frame, text="Archive logs older than:").grid(row=0, column=0, sticky=tk.W, pady=5)
        days_var = tk.IntVar(value=7)
        days_spinner = ttk.Spinbox(options_frame, from_=1, to=365, textvariable=days_var, width=5)
        days_spinner.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Label(options_frame, text="days").grid(row=0, column=2, sticky=tk.W, pady=5)
        
        # Delete after archiving
        delete_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Delete original files after archiving", 
                       variable=delete_var).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Archive path
        ttk.Label(options_frame, text="Archive directory:").grid(row=2, column=0, sticky=tk.W, pady=5)
        archive_path_var = tk.StringVar(value=str(self.log_dir / "archive"))
        ttk.Entry(options_frame, textvariable=archive_path_var, width=30).grid(
            row=2, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Status messages
        status_var = tk.StringVar()
        status_label = ttk.Label(options_frame, textvariable=status_var, wraplength=380)
        status_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=10)
        
        # Progress indicator
        progress_var = tk.DoubleVar()
        progress = ttk.Progressbar(options_frame, variable=progress_var, maximum=100)
        progress.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(options_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        def start_archive():
            """Start the archive process in a separate thread."""
            days = days_var.get()
            delete = delete_var.get()
            archive_dir = archive_path_var.get()
            
            # Disable buttons during processing
            archive_button.config(state=tk.DISABLED)
            cancel_button.config(state=tk.DISABLED)
            
            status_var.set(f"Archiving logs older than {days} days...")
            progress_var.set(10)  # Show some initial progress
            
            # Function to run in thread
            def run_archive():
                try:
                    # Call archive function
                    archive_old_logs(
                        log_dir=str(self.log_dir),
                        archive_dir=archive_dir,
                        days_to_keep=days,
                        delete_after_archive=delete
                    )
                    
                    # Update UI from main thread
                    self.after(0, lambda: progress_var.set(100))
                    self.after(0, lambda: status_var.set("Archive complete!"))
                    self.after(0, lambda: archive_button.config(state=tk.NORMAL))
                    self.after(0, lambda: cancel_button.config(state=tk.NORMAL))
                    
                    # Refresh log list after a short delay
                    self.after(1000, self.refresh_log_list)
                    
                except Exception as e:
                    # Handle errors
                    self.after(0, lambda: status_var.set(f"Error: {str(e)}"))
                    self.after(0, lambda: archive_button.config(state=tk.NORMAL))
                    self.after(0, lambda: cancel_button.config(state=tk.NORMAL))
            
            # Start thread
            threading.Thread(target=run_archive, daemon=True).start()
        
        archive_button = ttk.Button(button_frame, text="Archive", command=start_archive)
        archive_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=archive_window.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Center the window
        archive_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - archive_window.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - archive_window.winfo_height()) // 2
        archive_window.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    viewer = LogViewer()
    viewer.mainloop() 