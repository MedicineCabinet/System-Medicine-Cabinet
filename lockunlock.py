import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mysql.connector
import os
from PIL import Image, ImageTk, ImageSequence
from keyboard import OnScreenKeyboard
from custom_messagebox import CustomMessageBox
import serial
from withdrawal import QRCodeScanner
import mysql.connector
from datetime import datetime
import time


motif_color = '#42a7f5'
tab1 = None
tab2 = None

class LockUnlock:
    def __init__(self, root, keyboardframe, userName, passWord, arduino, action, parentHeader, exit_callback=None, container=None):


        self.user_Username = userName
        self.user_Password = passWord

        self.arduino = arduino
        self.action = action

        self.exit_callback = exit_callback

        self.window = root

        self.parentHeader = parentHeader

        self.container = container
        
        for widget in self.window.winfo_children():
            widget.destroy()

        self.keyboardFrame = keyboardframe
        # Instantiate OnScreenKeyboard
        self.keyboard = OnScreenKeyboard(self.keyboardFrame)
        self.keyboard.create_keyboard()
        self.keyboard.hide_keyboard()  # Initially hide the keyboard


        # Add the close button icon at the top-right corner
        self.close_icon_path = os.path.join(os.path.dirname(__file__), 'images', 'cancel_icon.png')
        if self.close_icon_path:
            self.close_img = ImageTk.PhotoImage(Image.open(self.close_icon_path).resize((14, 14), Image.LANCZOS))
        else:
            self.close_img = None

        self._disable_container_buttons()
        self._enable_all()

        # Create the UI components
        self._create_ui()




    def _create_ui(self):
        
        # Title frame
        title_frame = tk.Frame(self.window, bg=motif_color)
        title_frame.pack(fill=tk.X)

        
        title_label = tk.Label(title_frame, text=f'{self.parentHeader.capitalize()} > {self.action.capitalize()}', font=('Arial', 15, 'bold'), bg=motif_color, fg='white', pady=12)
        title_label.pack(side=tk.LEFT, padx=(10, 0))


        close_button = tk.Button(title_frame, image=self.close_img, command=self._exit_action, bg=motif_color, relief=tk.FLAT, bd=0)
        close_button.image = self.close_img  # Keep a reference to avoid garbage collection
        close_button.pack(side=tk.RIGHT, padx=(0, 10), pady=(0, 5))


        # Create a Notebook widget
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True)
        
         # Create a custom style for the Notebook tabs
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Arial", 18, 'bold'), padding=[20, 17])  # Adjust font size and padding

        global tab1, tab2

        # Create frames for each tab
        tab1 = ttk.Frame(notebook)
        tab2 = ttk.Frame(notebook)

        # Add frames to the notebook with titles
        notebook.add(tab1, text="Manual")
        notebook.add(tab2, text="QR Code")

        if self.action == "withdraw":
            manual_instruction = tk.Label(tab1, text=f'Enter your username and password manually\nto unlock the door before proceeding to {self.action} medicine.', font=('Arial', 18))
        elif self.action == "deposit":
            manual_instruction = tk.Label(tab1, text=f'Enter your username and password manually\nto unlock the door before proceeding to {self.action} medicine.', font=('Arial', 18))
        else:
            manual_instruction = tk.Label(tab1, text=f'Enter your username and password manually\nto lock the door.', font=('Arial', 18))
        manual_instruction.pack(pady=10, anchor='center')

        username_label = tk.Label(tab1, text="Username", font=("Arial", 18))
        username_label.pack(pady=10)

        self.username_entry = tk.Entry(tab1, font=("Arial", 16), relief='sunken', bd=3, width=50)
        self.username_entry.pack(pady=5, padx=20)

        password_label = tk.Label(tab1, text="Password", font=("Arial", 18))
        password_label.pack(pady=10)

        self.password_entry = tk.Entry(tab1, show="*", font=("Arial", 16), relief='sunken', bd=3, width=50)
        self.password_entry.pack(pady=5, padx=20)

        # Function to show/hide password based on Checkbutton state
        def toggle_password_visibility():
            if show_password_var.get():
                self.password_entry.config(show='')
            else:
                self.password_entry.config(show='*')

        # Variable to track the state of the Checkbutton
        show_password_var = tk.BooleanVar()
        show_password_checkbutton = tk.Checkbutton(tab1, text="Show Password", variable=show_password_var,
                                                    command=toggle_password_visibility, font=("Arial", 14))
        show_password_checkbutton.pack(anchor='center', pady=(5, 10))  # Align to the left with padding

        enter_button = tk.Button(tab1, text="Enter", font=("Arial", 18, 'bold'), bg=motif_color, fg='white', relief="raised", bd=3, pady=7, padx=40, command=self._validate_credentials)
        enter_button.pack(anchor='center', pady=(0, 10))

        # Bind the FocusIn event to show the keyboard when focused
        self.username_entry.bind("<FocusIn>", lambda event : self._show_keyboard())
        self.password_entry.bind("<FocusIn>", lambda event : self._show_keyboard())


        #TAB 2 - QR SCANNING TO LOCK OUR UNLOCK THE DOOR

        # QR Code Scanner Icon
        original_logo_img = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'scanning_icon.png')).resize((170, 170), Image.LANCZOS)
        logo_img = ImageTk.PhotoImage(original_logo_img)
        logo_label = tk.Label(tab2, image=logo_img)
        logo_label.image = logo_img  # Keep reference to avoid garbage collection
        logo_label.pack(side=tk.TOP, pady=(10, 10))

        # Instruction Message
        instruction_label = tk.Label(tab2, text=f"Please scan your qrcode\nto lock or unlock the door", font=("Arial", 18), fg='black')
        instruction_label.pack(pady=10)

        # QR Code Entry Frame
        entry_frame = tk.Frame(tab2)
        entry_frame.pack(pady=(5, 3))

        # Entry widget to capture QR code input
        self.qr_entry = tk.Entry(tab2, font=("Arial", 14), justify='center', width=35, relief='flat', bd=3)
        self.qr_entry.pack(pady=(10, 5))
        self.qr_entry.focus_set()

        # Label to display the contents corresponding to qrcode
        self.result_label = tk.Label(tab2, text="", font=("Arial", 15), fg='green', pady=2, height=5)
        self.result_label.pack()

        # Bind the Enter key to process the QR code when scanned
        self.qr_entry.bind("<Return>", self._process_qrcode)

        # Bind the tab change event
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    #Function that validates user login credentials manually
    def _validate_credentials(self):
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="db_medicine_cabinet"
            )
        cursor = conn.cursor()

        username = self.username_entry.get()
        password = self.password_entry.get()

        if username == self.user_Username and password == self.user_Password:

            search_query = "SELECT username, accountType, position FROM users WHERE username = %s AND password = %s"
            cursor.execute(search_query, (username, password))
            result = cursor.fetchone()
            userName, accountType, position = result

            insert_query = """
                INSERT INTO door_logs (username, accountType, position, date, time, action_taken)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (userName, accountType, position, datetime.now().date(), datetime.now().time(), self.action))
            conn.commit()
            self._exit_action()
            if self.action == "unlock":
                self._unlock_door()

                message_box = CustomMessageBox(
                    root=self.keyboardFrame,
                    title="Success",
                    message="Door lock is now unlocked.",
                    icon_path=os.path.join(os.path.dirname(__file__), 'images', 'unlock_icon.png'),
                    ok_callback=lambda: message_box.destroy()
                )
            elif self.action == "withdraw":
                self._unlock_door()
                message_box = CustomMessageBox(
                    root=self.keyboardFrame,
                    title="Success",
                    message="Door lock is now unlocked\nYou may now proceed to withdraw medicine.",
                    icon_path=os.path.join(os.path.dirname(__file__), 'images', 'unlock_icon.png'),
                    ok_callback= lambda: (message_box.destroy(), QRCodeScanner(self.keyboardFrame), self._enable_all)
                )
            elif self.action == "lock":
                self._lock_door()
        else:
            message_box = CustomMessageBox(
            root=self.keyboardFrame,
            title="Error",
            message="Invalid username or password.",
            color="red",  # Background color for warning
            icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),  # Path to your icon
            sound_file="sounds/invalidLogin.mp3"
        )


    def _on_tab_change(self, event):
        # Check if the selected tab is tab2 and hide the keyboard
        notebook = event.widget
        if notebook.index(notebook.select()) == 1:  # Index 1 for tab2
            self._hide_keyboard()


    def _show_keyboard(self):
        """Show the keyboard and move the window up."""
        self.keyboard.show_keyboard()

    def _hide_keyboard(self):
        """Hide the keyboard and restore the window position."""
        self.keyboard.hide_keyboard()

    #Function that validates user login credentials via QR code
    def _process_qrcode(self, event):
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="db_medicine_cabinet"
            )
        cursor = conn.cursor()

        if self.qr_entry.winfo_exists():
            scanned_qr_code = self.qr_entry.get().strip()
            print(f"Final scanned QR code: {scanned_qr_code}")  # Debugging statement

            if scanned_qr_code:
                # Clear the Entry widget for the next scan
                self.qr_entry.delete(0, tk.END)

                # Connect to the MySQL database
                try:
                    conn = mysql.connector.connect(
                        host="localhost",
                        user="root",
                        password="",  # Adjust according to your MySQL setup
                        database="db_medicine_cabinet"
                    )
                    cursor = conn.cursor()

                    # Check if the scanned QR code matches any user in the database
                    query = "SELECT username, password FROM users WHERE username = %s AND password = %s"
                    cursor.execute(query, (self.user_Username, self.user_Password))
                    result = cursor.fetchone()

                    if result:
                        search_query = "SELECT username, accountType, position FROM users WHERE qrcode_data = %s"
                        cursor.execute(search_query, (scanned_qr_code,))
                        user_result = cursor.fetchone()
                        userName, accountType, position = user_result
                        self._exit_action()
                        insert_query = """
                            INSERT INTO door_logs (username, accountType, position, date, time, action_taken)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (userName, accountType, position, datetime.now().date(), datetime.now().time(), self.action))
                        conn.commit()
                        if self.action == "unlock":
                            self._unlock_door()
                            message_box = CustomMessageBox(
                                root=self.keyboardFrame,
                                title="Success",
                                message="Door lock is now unlock.",
                                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'unlock_icon.png'),
                                ok_callback=message_box.destroy
                            )
                        elif self.action == "withdraw":
                            self._unlock_door()
                            
                            message_box = CustomMessageBox(
                                root=self.keyboardFrame,
                                title="Success",
                                message="Door lock is now unlock\nYou may now proceed to withdraw medicine.",
                                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'unlock_icon.png'),
                                ok_callback= lambda: (message_box.destroy(), QRCodeScanner(self.keyboardFrame), self._enable_all())
                            )
                        elif self.action == "lock":
                            self._lock_door()
                            message_box = CustomMessageBox(
                                root=self.keyboardFrame,
                                title="Success",
                                message="Door lock is now locked.",
                                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'lock_icon.png')
                            )
                    else:
                        # If no match found, show an error
                        self.result_label.config(text="Invalid QR code or credentials.", fg="red")

                except mysql.connector.Error as err:
                    print(f"Error: {err}")
                    messagebox.showerror("Database Error", "Could not connect to the database.")

                finally:
                    # Close the cursor and connection
                    cursor.close()
                    conn.close()
            else:
                self.result_label.config(text="No QR code data scanned.", fg="red")

    # Function to send the lock command
    def _lock_door(self):
        # Step 1: Check the sensors before sending the lock command
        self.arduino.write(b'check_sensors\n')  # Send "check_sensors" command to Arduino
        time.sleep(0.1)  # Brief delay to allow Arduino to process and respond

        # Step 2: Read Arduino's response
        if self.arduino.in_waiting > 0:
            response = self.arduino.readline().decode().strip()
            
            # Step 3: Proceed based on the sensor check response
            if response == "Object detected":
                self.arduino.write(b'lock\n')  # Send the "lock" command to the Arduino
                message_box = CustomMessageBox(
                    root=self.keyboardFrame,
                    title="Success",
                    message="Door lock is now locked.",
                    icon_path=os.path.join(os.path.dirname(__file__), 'images', 'lock_icon.png')
                )
                print("Lock command sent")
            else:
                # Recursive function to keep checking the sensors
                def recheck_sensors(warning_box):
                    self.arduino.write(b'check_sensors\n')
                    time.sleep(0.1)
                    if self.arduino.in_waiting > 0:
                        response = self.arduino.readline().decode().strip()
                        if response == "Object detected":
                            # Destroy the warning box since doors are properly closed now
                            warning_box.destroy()
                            # Send lock command and show success message
                            self.arduino.write(b'lock\n')
                            CustomMessageBox(
                                root=self.keyboardFrame,
                                title="Success",
                                message="Door lock is now locked.",
                                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'lock_icon.png')
                            )
                            print("Lock command sent after recheck")
                        else:
                            # Display warning again if doors are still not closed properly
                            warning_box = CustomMessageBox(
                                root=self.keyboardFrame,
                                title="Warning",
                                color='red',
                                message="Doors are not properly closed\nPlease close both the doors properly.",
                                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                                ok_callback=lambda: recheck_sensors(warning_box)  # Reattach recheck_sensors with warning_box as callback
                            )
                            print("Rechecking sensors: No object detected.")
                
                # Show warning message with the recheck callback
                warning_box = CustomMessageBox(
                    root=self.keyboardFrame,
                    title="Warning",
                    color='red',
                    message="Doors are not properly closed\nPlease close both the doors properly.",
                    icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                    ok_callback=lambda: recheck_sensors(warning_box)  # Attach recheck_sensors with warning_box as callback
                )
                print("Lock command aborted: No object detected.")


    # Function to send the unlock command
    def _unlock_door(self):
        print("Unlock command sent")
        self.arduino.write(b'unlock\n')  # Send the "unlock" command to the Arduino

    def _exit_action(self):
        """Trigger the no callback and close the window."""
        if self.exit_callback:
            self.exit_callback()

    def _disable_container_buttons(self):
        """Disable all buttons within the container frame."""
        if self.container:
            for widget in self.container.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.DISABLED)

    def _enable_all(self):
        """Re-enable all buttons within the container frame."""
        if self.container:
            for widget in self.container.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.NORMAL)
        
