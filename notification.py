import requests
import datetime
import os
import tkinter as tk

class NotificationManager:
    def __init__(self, root, asap=False):
        self.root = root
        self.api_url = "https://emc-san-mateo.com/api"  # Base URL for Flask API
        self.asap = asap

    def check_soon_to_expire(self):
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
                exp_date = med["expiration_date"]  # Assuming this is the expiration date string in 'YYYY-MM-DD' format

                # Check if expiration date is valid
                try:
                    days_left = (datetime.datetime.strptime(exp_date, "%Y-%m-%d").date() - datetime.datetime.now().date()).days
                except ValueError:
                    print(f"Invalid expiration date format for {med_name}: {exp_date}")
                    continue  # Skip this medicine if the date format is invalid

                # Log the notification via API
                self.log_notification({
                    "medicine_id": med_id,  # Replace with actual ID from the API if available
                    "medicine_name": med_name,
                    "med_type": med_type,
                    "dosage": dosage,
                    "expiration_date": exp_date,
                    "days_left": days_left,
                })

                if self.asap:
                    self.create_notification_popup(med_name, med_type, dosage, exp_date, days_left, notification_count)
        except requests.RequestException as e:
            print(f"Error fetching data from API: {e}")

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

    def log_notification(self, data):
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
            if e.response:
                print(f"Response content: {e.response.text}")  # Print the response content for more info

