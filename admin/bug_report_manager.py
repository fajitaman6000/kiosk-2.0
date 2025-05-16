import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext # Removed tkFont here
import json
import os
from datetime import datetime
import traceback # Import traceback for error logging
import sys # For sys.stderr

class BugReportManager:
    BUG_REPORTS_FILE = "bug_reports.json"
    DEBUG_LOG_FILE = "bug_manager_debug.log"

    # Define status order and colors as class attributes
    STATUS_ORDER = ["Open", "In Progress", "Resolved", "Closed", "Won't Fix"]
    STATUS_COLORS = {
        "Open": "#FF4136",          # Vivid Red
        "In Progress": "#FF851B",   # Orange
        "Resolved": "#2ECC40",      # Green
        "Closed": "#AAAAAA",        # Gray
        "Won't Fix": "#B10DC9",     # Purple
        "DEFAULT": "black",         # Fallback color for items
        "HEADER": "#0074D9"         # Blue for headers
    }


    def __init__(self, app):
        self.app = app
        self._log_debug("BugReportManager initialized.")
        self.reports = self.load_reports()
        self._log_debug(f"Loaded {len(self.reports)} bug reports.")
        # Removed: self.combobox_active = False # Status combobox flag
        self._debounce_id_details = None # For debouncing listbox selection -> details update
        self.currently_selected_report_id_for_update = None # To store the ID of the selected report (still used for delete)

    def _log_debug(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        try:
            with open(self.DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"ERROR: Could not write to debug log file {self.DEBUG_LOG_FILE}: {e}", file=sys.stderr)

    def load_reports(self):
        self._log_debug(f"Attempting to load reports from {self.BUG_REPORTS_FILE}")
        try:
            if os.path.exists(self.BUG_REPORTS_FILE):
                with open(self.BUG_REPORTS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        self._log_debug("Bug reports file is empty.")
                        return []
                    reports = json.loads(content)
                    # Optional: Clean status from loaded reports if needed, but not strictly necessary
                    # for functionality since we just won't display/use it.
                    self._log_debug("Successfully loaded reports.")
                    return reports
            self._log_debug("Bug reports file not found.")
            return []
        except json.JSONDecodeError as e:
            self._log_debug(f"JSON decode error loading reports: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Could not decode {self.BUG_REPORTS_FILE}. It might be corrupted. A new one will be created on next save.", parent=self.app.root)
            return []
        except Exception as e:
            self._log_debug(f"Failed to load bug reports: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to load bug reports: {e}", parent=self.app.root)
            return []

    def save_reports(self):
        self._log_debug(f"Attempting to save reports to {self.BUG_REPORTS_FILE}")
        try:
            # Ensure reports being saved don't have the status key, though add_report already handles this for new reports
            # This map handles old reports that might still have status if loaded from an old file version
            reports_to_save = []
            for report in self.reports:
                report_copy = report.copy() # Don't modify the original list items while iterating
                if 'status' in report_copy:
                    del report_copy['status']
                reports_to_save.append(report_copy)

            with open(self.BUG_REPORTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(reports_to_save, f, indent=4)
            self._log_debug("Successfully saved reports.")
        except Exception as e:
            self._log_debug(f"Failed to save bug reports: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to save bug reports: {e}", parent=self.app.root)

    def add_report(self, name, content, date_str=None, reporter_name="GM"):
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        next_id = 1
        if self.reports:
            # Find the maximum ID, handling cases where 'id' might be missing or non-numeric
            max_id = 0
            for report in self.reports:
                report_id = report.get('id', 0)
                if isinstance(report_id, (int, float)): # Ensure it's a number before comparing
                    max_id = max(max_id, int(report_id)) # Convert to int for comparison
            next_id = max_id + 1
            
        new_report = {
            "id": next_id,
            "name": name,
            "date": date_str,
            "content": content,
            # Removed: "status": "Open",
            "reporter": reporter_name
        }
        self.reports.append(new_report)
        self._log_debug(f"Added new report with ID {next_id}.")
        self.save_reports()
        return new_report

    def show_report_submission_popup(self):
        self._log_debug("Opening report submission popup.")
        popup = tk.Toplevel(self.app.root)
        popup.title("Submit Bug Report")
        popup.update_idletasks()
        req_width = popup.winfo_reqwidth() + 20
        req_height = popup.winfo_reqheight() + 20
        min_width = 450
        min_height = 500
        popup.geometry(f"{max(req_width, min_width)}x{max(req_height, min_height)}")
        popup.minsize(min_width, min_height)

        popup.transient(self.app.root)
        popup.grab_set()

        main_frame = ttk.Frame(popup, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Your Name:").grid(row=0, column=0, sticky="w", pady=(0, 2))
        reporter_entry = ttk.Entry(main_frame, width=60)
        reporter_entry.grid(row=0, column=1, sticky="ew", pady=(0, 10))

        ttk.Label(main_frame, text="Bug Title/Summary:").grid(row=1, column=0, sticky="w", pady=(0, 2))
        name_entry = ttk.Entry(main_frame, width=60)
        name_entry.grid(row=1, column=1, sticky="ew", pady=(0, 10))

        ttk.Label(main_frame, text="Date:").grid(row=2, column=0, sticky="w", pady=(0, 2))
        date_str_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ttk.Label(main_frame, text=date_str_val).grid(row=2, column=1, sticky="w", pady=(0, 10))

        ttk.Label(main_frame, text="Description:").grid(row=3, column=0, sticky="nw", pady=(0, 2))
        content_text = scrolledtext.ScrolledText(main_frame, width=60, height=15, wrap=tk.WORD)
        content_text.grid(row=3, column=1, sticky="nsew", pady=(0, 10))

        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(3, weight=1)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky="e")

        def _submit():
            self._log_debug("Submit button clicked in submission popup.")
            reporter_name_val = reporter_entry.get().strip()
            name_val = name_entry.get().strip()
            content_val = content_text.get("1.0", tk.END).strip()

            if not reporter_name_val:
                self._log_debug("Validation failed: Reporter name is empty.")
                messagebox.showwarning("Input Error", "Your Name is required.", parent=popup)
                return
            if not name_val:
                self._log_debug("Validation failed: Title is empty.")
                messagebox.showwarning("Input Error", "Bug Title/Summary is required.", parent=popup)
                return
            if not content_val:
                self._log_debug("Validation failed: Description is empty.")
                messagebox.showwarning("Input Error", "Description is required.", parent=popup)
                return

            self._log_debug("Validation successful. Adding report.")
            self.add_report(name_val, content_val, date_str_val, reporter_name_val)
            messagebox.showinfo("Success", "Bug report submitted!", parent=popup)
            self._log_debug("Submission successful. Closing popup.")
            popup.destroy()

        submit_button = ttk.Button(buttons_frame, text="Submit", command=_submit)
        submit_button.pack(side=tk.LEFT, padx=5)

        browse_button = ttk.Button(buttons_frame, text="Browse Reports", command=self.show_browse_reports_popup)
        browse_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(buttons_frame, text="Cancel", command=popup.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        popup.protocol("WM_DELETE_WINDOW", popup.destroy)

    def populate_reports_listbox(self):
        self._log_debug("Populating reports listbox.")
        if not hasattr(self, 'reports_listbox') or not self.reports_listbox.winfo_exists():
            self._log_debug("Listbox widget not found during populate. Aborting.")
            return

        self.reports_listbox.delete(0, tk.END)
        # self.reports_listbox.selection_clear(0, tk.END) # Not strictly needed here as delete clears selection

        # Sort reports by ID in descending order for display
        sorted_reports = sorted(self.reports, key=lambda r: r.get('id', 0), reverse=True)
        self._log_debug(f"Inserting {len(sorted_reports)} items into listbox.")
        for report in sorted_reports:
            # Removed status from display text
            display_text = f"{report.get('id', 'N/A')} | {report.get('date', 'N/A')} | {report.get('name', 'Untitled')} | By: {report.get('reporter', 'GM')}"
            self.reports_listbox.insert(tk.END, display_text)
        self._log_debug("Finished populating listbox.")

    # Removed status combobox event handlers:
    # _on_combobox_focus_in
    # _on_combobox_selected
    # _on_combobox_focus_out
    # _reset_combobox_active_flag


    def show_browse_reports_popup(self):
        self._log_debug("Opening browse reports popup.")
        self.currently_selected_report_id_for_update = None # Reset when opening
        # Removed: self.combobox_active = False # Reset flag

        browse_popup = tk.Toplevel(self.app.root)
        browse_popup.title("Browse Bug Reports")
        browse_popup.update_idletasks()
        req_width = 900
        req_height = 700
        min_width = 700
        min_height = 500
        browse_popup.geometry(f"{max(req_width, min_width)}x{max(req_height, min_height)}")
        browse_popup.minsize(min_width, min_height)
        browse_popup.transient(self.app.root)
        browse_popup.grab_set()

        main_paned_window = ttk.PanedWindow(browse_popup, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        list_frame = ttk.Frame(main_paned_window, width=400)
        main_paned_window.add(list_frame, weight=2)

        # Updated label text to remove status reference
        listbox_label = ttk.Label(list_frame, text="Reports (ID | Date | Title | Reporter)")
        listbox_label.pack(pady=(0,5), anchor="w")

        self.reports_listbox = tk.Listbox(list_frame, width=70, height=20)
        self.reports_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.reports_listbox.yview)
        self.reports_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.populate_reports_listbox() # Call after self.reports_listbox is created

        details_frame = ttk.Frame(main_paned_window)
        main_paned_window.add(details_frame, weight=3)

        ttk.Label(details_frame, text="Report Details:").pack(anchor="w", pady=(0,5))

        self.details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, state=tk.DISABLED, height=15)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=(0,10))

        # Removed status change UI elements:
        # status_frame
        # status_label
        # self.status_var
        # status_options
        # status_dropdown
        # status_dropdown.bind calls
        # update_status_button

        action_buttons_frame = ttk.Frame(details_frame)
        action_buttons_frame.pack(fill=tk.X, pady=(5,0)) # Adjust pady as status frame is removed

        # Keep delete button
        delete_button = ttk.Button(action_buttons_frame, text="Delete Report", command=self._delete_selected_report, style="Danger.TButton")
        delete_button.pack(side=tk.LEFT, padx=5)

        # Keep style configuration as delete button uses it
        try:
            s = ttk.Style()
            if "Danger.TButton" not in s.theme_names():
                s.configure("Danger.TButton", foreground="white", background="#dc3545")
                s.map("Danger.TButton", background=[('active', '#bb2d3b')])
        except tk.TclError:
            pass

        close_button = ttk.Button(action_buttons_frame, text="Close Browser", command=browse_popup.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)

        self.reports_listbox.bind('<<ListboxSelect>>', self._on_listbox_select_debounced)
        browse_popup.protocol("WM_DELETE_WINDOW", browse_popup.destroy)

        # Initial call to display placeholder if no selection
        self._perform_detail_update()


    def _on_listbox_select_debounced(self, event=None):
        self._log_debug("_on_listbox_select_debounced called.")

        current_selection = []
        if hasattr(self, 'reports_listbox') and self.reports_listbox.winfo_exists():
            current_selection = self.reports_listbox.curselection()
        else:
            self._log_debug("_on_listbox_select_debounced: reports_listbox not available. Cannot get current selection.")
            return # Cannot proceed without listbox

        # Removed check for combobox_active

        if hasattr(self, '_debounce_id_details') and self._debounce_id_details:
            # Check if self.reports_listbox exists before calling after_cancel
            if hasattr(self, 'reports_listbox') and self.reports_listbox.winfo_exists():
                self.reports_listbox.after_cancel(self._debounce_id_details)
                self._log_debug(f"Cancelled previous _perform_detail_update timer: {self._debounce_id_details}")
            else:
                self._log_debug("_on_listbox_select_debounced: reports_listbox not available for after_cancel.")
                return


        if hasattr(self, '_perform_detail_update') and hasattr(self, 'reports_listbox') and self.reports_listbox.winfo_exists():
            self._debounce_id_details = self.reports_listbox.after(50, self._perform_detail_update)
            self._log_debug(f"Scheduled _perform_detail_update in 50ms. ID: {self._debounce_id_details}")
        else:
            self._log_debug("ERROR: _perform_detail_update method or reports_listbox not found for scheduling!")

    def _perform_detail_update(self):
        self._log_debug("_perform_detail_update called (actual execution).")

        if not hasattr(self, 'reports_listbox') or not self.reports_listbox.winfo_exists():
            self._log_debug("_perform_detail_update: Listbox widget missing or destroyed. Aborting.")
            self.currently_selected_report_id_for_update = None # Clear stored ID
            return

        selection_after_delay = self.reports_listbox.curselection()
        self._log_debug(f"_perform_detail_update: Current selection tuple (after delay): {selection_after_delay}")

        # Update detail text area
        if hasattr(self, 'details_text') and self.details_text.winfo_exists():
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete('1.0', tk.END)
        else:
            self._log_debug("_perform_detail_update: Details text widget missing. Cannot update panel.")
            self.currently_selected_report_id_for_update = None # Clear stored ID
            return

        if not selection_after_delay:
            self._log_debug("_perform_detail_update: No item selected. Clearing details panel.")
            self.details_text.insert(tk.END, "Select a report from the list.")
            # Removed: if hasattr(self, 'status_var'): self.status_var.set("")
            self.currently_selected_report_id_for_update = None # Clear stored ID
        else:
            selected_index_in_listbox = selection_after_delay[0]
            self._log_debug(f"_perform_detail_update: Item selected at listbox index {selected_index_in_listbox}.")
            try:
                sorted_reports_view = sorted(self.reports, key=lambda r: r.get('id', 0), reverse=True)
                if 0 <= selected_index_in_listbox < len(sorted_reports_view):
                    report_obj = sorted_reports_view[selected_index_in_listbox]
                    self.currently_selected_report_id_for_update = report_obj.get('id') # STORE THE ID
                    self._log_debug(f"_perform_detail_update: Stored currently_selected_report_id_for_update: {self.currently_selected_report_id_for_update}")

                    details_content = (
                        f"ID: {report_obj.get('id', 'N/A')}\n"
                        f"Title: {report_obj.get('name', 'N/A')}\n"
                        f"Date: {report_obj.get('date', 'N/A')}\n"
                        f"Reporter: {report_obj.get('reporter', 'N/A')}\n\n"
                        # Removed: f"Status: {report_obj.get('status', 'N/A')}\n\n"
                        f"Description:\n{'-'*30}\n{report_obj.get('content', '')}"
                    )
                    self.details_text.insert(tk.END, details_content)
                    # Removed status_var setting logic
                    self._log_debug("_perform_detail_update: Details panel updated successfully.")
                else:
                    self._log_debug(f"_perform_detail_update: Selected index {selected_index_in_listbox} is out of bounds.")
                    self.details_text.insert(tk.END, "Error: Could not find selected report details.")
                    # Removed: if hasattr(self, 'status_var'): self.status_var.set("")
                    self.currently_selected_report_id_for_update = None # Clear stored ID
            except Exception as e:
                self._log_debug(f"_perform_detail_update: Exception: {e}\n{traceback.format_exc()}")
                self.details_text.insert(tk.END, f"Error displaying details:\n{e}")
                # Removed: if hasattr(self, 'status_var'): self.status_var.set("")
                self.currently_selected_report_id_for_update = None # Clear stored ID

        if hasattr(self, 'details_text') and self.details_text.winfo_exists():
            self.details_text.config(state=tk.DISABLED)
        self._log_debug("_perform_detail_update finished.")

    # Removed the entire _update_selected_report_status method

    def _delete_selected_report(self):
        parent_popup = self.reports_listbox.winfo_toplevel()
        self._log_debug("_delete_selected_report called.")

        report_id_to_delete = self.currently_selected_report_id_for_update
        if report_id_to_delete is None:
            # Fallback to curselection if no ID was stored (e.g. user clicked delete without prior valid selection)
            # This is less robust but provides a safety net.
            if hasattr(self, 'reports_listbox') and self.reports_listbox.winfo_exists():
                selection = self.reports_listbox.curselection()
                if selection:
                    try:
                        sorted_reports_view = sorted(self.reports, key=lambda r: r.get('id', 0), reverse=True)
                        if 0 <= selection[0] < len(sorted_reports_view):
                            report_id_to_delete = sorted_reports_view[selection[0]].get('id')
                            self._log_debug(f"Fallback: Got report ID {report_id_to_delete} from listbox selection index {selection[0]}.")
                        else:
                            self._log_debug(f"Fallback: Listbox index {selection[0]} out of bounds.")
                    except Exception as e:
                        self._log_debug(f"Fallback: Error getting report ID from selection: {e}")


            if report_id_to_delete is None:
                self._log_debug("No report ID stored or selectable for deletion.")
                messagebox.showwarning("No Selection", "Please select a report to delete.", parent=parent_popup)
                return

        self._log_debug(f"Attempting to delete report ID: {report_id_to_delete}.")

        #confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this report? This action cannot be undone.", parent=parent_popup)
        #if not confirm:
            #self._log_debug("Delete cancelled by user.")
            #return

        try:
            report_to_remove = None
            for report in self.reports:
                if report.get('id') == report_id_to_delete:
                    report_to_remove = report
                    break

            if report_to_remove:
                self.reports.remove(report_to_remove)
                self._log_debug(f"Removed report object with ID {report_id_to_delete} from list.")
                self.save_reports()
                self._log_debug("Reports saved after deletion.")

                self.populate_reports_listbox()
                self._log_debug("Listbox repopulated after deletion.")

                self.currently_selected_report_id_for_update = None # Clear stored ID after deletion
                if hasattr(self, '_perform_detail_update'):
                    self._perform_detail_update() # Refresh details (should show empty state)

                #messagebox.showinfo("Success", "Report deleted.", parent=parent_popup)
                self._log_debug("Report deletion successful.")
            else:
                self._log_debug(f"Could not find report object with ID {report_id_to_delete} for deletion.")
                messagebox.showerror("Error", "Could not find the report to delete.", parent=parent_popup)
        except Exception as e:
            self._log_debug(f"_delete_selected_report: Exception occurred: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to delete report: {e}", parent=parent_popup)