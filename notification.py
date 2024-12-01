import requests
import datetime
import os
import tkinter as tk
import threading
import time  # For simulation purposes

motif_color = '#42a7f5'

class NotificationManager:
    def __init__(self, root, asap=False, log=False):
        self.root = root
        self.api_url = "https://emc-san-mateo.com/api"  # Base URL for Flask API
        self.asap = asap
        self.log = log
        self.loading_window = None  # Initialize the loading window attribute

    def show_loading_window(self, message="Loading, please wait..."):
        from System import root
        """Display a Toplevel window with a loading message centered on the root window."""
        if self.loading_window is not None:
            return  # Avoid creating multiple loading windows

        self.loading_window = tk.Toplevel(root, bg=motif_color)
        self.loading_window.title("Loading")
        self.loading_window.overrideredirect(True)
        self.loading_window.geometry("520x300")
        self.loading_window.resizable(False, False)
        self.loading_window.transient(self.root)
        self.loading_window.grab_set()  # Prevent interaction with other windows
        self.loading_window.protocol("WM_DELETE_WINDOW", lambda: None)  # Disable closing

        # Center the Toplevel window relative to the root window
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        # Calculate position to center the Toplevel on the root
        x_offset = root_x + (root_width // 2) - (200 // 2)
        y_offset = root_y + (root_height // 2) - (100 // 2)
        self.loading_window.geometry(f"+{x_offset}+{y_offset}")

        # Add a label for the loading message
        label = tk.Label(self.loading_window, text=message, font=("Arial", 18), bg=motif_color, fg='white')
        label.pack(expand=True, pady=20)

    def close_loading_window(self):
        """Close the loading window."""
        if self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

    def check_soon_to_expire(self):
        """Method to fetch medicines soon to expire and log notifications."""
        self.show_loading_window("Fetching soon-to-expire medicines...")
        try:
            response = requests.get(f"{self.api_url}/soon_to_expire")
            response.raise_for_status()  # Raise an error for non-200 responses
            medicines = response.json()

            for notification_count, med in enumerate(medicines):
                # Extract individual values correctly
                med_id = med["id"]
                med_name = med["name"]
                med_type = med["type"]
                dosage = med["dosage"]
                exp_date = med["expiration_date"]

                try:
                    med["days_left"] = (
                        datetime.datetime.strptime(exp_date, "%Y-%m-%d").date() -
                        datetime.datetime.now().date()
                    ).days
                    days_left = med["days_left"]
                except ValueError:
                    print(f"Invalid expiration date format for {med_name}: {exp_date}")
                    continue

                # Log the notification (this could involve some UI update or API call)
                if self.log:
                    self.show_loading_window("Logging notifications...")
                    self.log_notification({
                        "medicine_id": med_id,
                        "medicine_name": med_name,
                        "med_type": med_type,
                        "dosage": dosage,
                        "expiration_date": exp_date,
                        "days_left": days_left,
                    })
                if self.asap:
                    self.create_notification_popup(med_name, med_type, dosage, exp_date, days_left, notification_count)
            return medicines

        except requests.RequestException as e:
            print(f"Error fetching data from API: {e}")

        finally:
            # Close the loading window after the entire process is complete
            self.close_loading_window()

    def log_notification(self, data):
        """Log the notification data."""
        try:
            # Ensure proper fields and data types
            required_fields = ['medicine_id', 'medicine_name', 'med_type', 'dosage', 'expiration_date', 'days_left']
            for field in required_fields:
                if field not in data:
                    print(f"Missing required field: {field}")
                    return
            if not isinstance(data['medicine_id'], int):
                print("Invalid data type for medicine_id. Expected integer.")
                return
            datetime.datetime.strptime(data['expiration_date'], "%Y-%m-%d")  # Validate date format

            # Send the log request
            response = requests.post(f"{self.api_url}/log_notification", json=data)
            response.raise_for_status()  # Raise an error for non-200 responses
            print(f"Notification logged successfully: {data}")

        except requests.RequestException as e:
            print(f"Error logging notification: {e}")

        finally:
            # Close the loading window after logging is complete
            self.close_loading_window()

    def create_notification_popup(self, medicine_name, med_type, dosage, expiration_date, days_left, notification_count):
        try:
            from System import CustomMessageBox
            from System import root
            message_box = CustomMessageBox(
                root=root,
                title=f'Notification ({notification_count})',
                message=(
                    f'Expiring medicine:\n'
                    f'{medicine_name} - {med_type} - {dosage}\n'
                    f'Expiration Date: {expiration_date}\n'
                    f'Days left: {days_left}'
                ),
                color='red',
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png')
            )
        except Exception as e:
            print(f"Error displaying notification popup: {e}")

    def start_checking(self):
        """Start the check_soon_to_expire method in a separate thread."""
        threading.Thread(target=self.check_soon_to_expire, daemon=True).start()