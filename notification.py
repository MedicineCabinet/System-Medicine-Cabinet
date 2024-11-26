import requests
import datetime
import os
import tkinter as tk
import threading
import time  # For simulation purposes

motif_color = '#42a7f5'

class NotificationManager:
    def __init__(self, root, asap=False):
        self.root = root
        self.api_url = "https://emc-san-mateo.com/api"  # Base URL for Flask API
        self.asap = asap
        self.loading_window = None  # Initialize the attribute in the constructor
        self.show_loading()

    def show_loading(self, message="Loading, please wait..."):
        """Display a loading Toplevel."""
        # Ensure GUI updates are on the main thread
        self.root.after(0, self._create_loading_window, message)

    def _create_loading_window(self, message):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate position to center the window
        position_top = int(screen_height / 2 - 600 / 2)
        position_right = int(screen_width / 2 - 800 / 2)

        # Create the loading window
        self.loading_window = tk.Toplevel(self.root, bg=motif_color)
        self.loading_window.title("Loading")
        self.loading_window.geometry(f"{800}x{600}+{position_right}+{position_top}")  # Set size and position
        self.loading_window.resizable(False, False)  # Disable resizing
        self.loading_window.transient(self.root)  # Keep on top of the main window
        self.loading_window.grab_set()  # Block interaction with the main window
        self.loading_window.overrideredirect(True)  # Remove the title bar

        # Add the message label to the window
        tk.Label(self.loading_window, text=message, font=("Arial", 18, "bold"), fg='white', bg=motif_color, relief='sunken', bd=5, anchor='center').pack(pady=20, fill='both')

    def close_loading(self):
        """Close the loading Toplevel."""
        if self.loading_window:
            # Ensure this happens on the main thread
            self.root.after(0, self._destroy_loading_window)

    def _destroy_loading_window(self):
        """Internal method to safely destroy the loading window."""
        if self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

    def check_soon_to_expire(self):
        """Method to fetch medicines soon to expire and log notifications."""
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
            
            # Close the loading window after the entire process is complete
            self.close_loading()
            return medicines

        except requests.RequestException as e:
            print(f"Error fetching data from API: {e}")
            self.close_loading()  # Ensure loading window is closed on error

    def log_notification(self, data):
        """Log the notification data."""
        # Ensure required fields are present
        required_fields = ['medicine_id', 'medicine_name', 'med_type', 'dosage', 'expiration_date', 'days_left']
        for field in required_fields:
            if field not in data:
                print(f"Missing required field: {field}")
                return

        # Ensure proper data types
        if not isinstance(data['medicine_id'], int):
            print("Invalid data type for medicine_id. Expected integer.")
            return
        
        try:
            datetime.datetime.strptime(data['expiration_date'], "%Y-%m-%d")  # Check if date format is correct
        except ValueError:
            print(f"Invalid expiration_date format: {data['expiration_date']}. Expected 'YYYY-MM-DD'.")
            return
        
        try:
            response = requests.post(f"{self.api_url}/log_notification", json=data)
            response.raise_for_status()  # Raise an error for non-200 responses
            print(f"Notification logged successfully. {data}")
        except requests.RequestException as e:
            print(f"Error logging notification: {e}: {response.text}")

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
        """Start checking for soon-to-expire medicines in a separate thread."""
        # Run the check_soon_to_expire method in a background thread to avoid blocking the UI
        threading.Thread(target=self.check_soon_to_expire, daemon=True).start()
