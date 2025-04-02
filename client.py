import socket
import threading
import tkinter
from tkinter import scrolledtext
from datetime import datetime
import os
from pathlib import Path

HOST = '127.0.0.1'  # local host
PORT = 18000

# set up downloads path (and make sure it exists
downloads_path = str(Path.home() / "downloads")
os.makedirs(downloads_path, exist_ok=True)

class ChatClient:

    def __init__(self):
        # initially connect to the server but set nickname to none so we can still request reports
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        self.nickname = None

        # set up the chatroom and initial menu with options
        self.window = tkinter.Tk()
        self.window.title("Chatroom")

        self.chatbox = scrolledtext.ScrolledText(self.window,width=90, height=20)
        self.chatbox.config(font=("Courier New", 12))

        # display menu
        self.chatbox.insert(tkinter.END, "Welcome! You may use the below input box to type and press enter to send your message.\n\n")
        self.chatbox.insert(tkinter.END, "Please select one of the following options:\n\t1. Get a report of the chatroom from the server.\n\t2. Request to join the chatroom.\n\t3. Quit the program.\n")
        self.chatbox.pack(padx=20, pady=20)

        # when the user enters their choice and hits return, it'll run handle_choice
        self.textbox = tkinter.Entry(self.window,width=90,font=("Courier New", 12))
        self.textbox.pack(padx=0, pady=20)
        self.textbox.bind("<Return>", self.handle_choice)

        self.chat_area = self.chatbox  # Use the same text widget for chat
        self.message_entry = tkinter.Entry(self.window, width=60)

        self.window.protocol("WM_DELETE_WINDOW", self.stop)
        self.window.mainloop()

    def handle_choice(self, event):
        # if there is not an existing connection, make one
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))

        # store the choice into option
        option = self.textbox.get()

        # handle the choice
        if option == "1":
            # request report
            self.sock.send("<request_report>".encode('utf-8'))
            report_message = self.sock.recv(1024).decode('ascii')

            # display based on number of users
            if report_message == "<NO_USERS>":
                self.chatbox.insert(tkinter.END, "There are no active users in the chatroom.\n")
            else:
                number_of_users = self.count_report_length(report_message)

                if number_of_users == 1:
                    self.chatbox.insert(tkinter.END, "There is 1 active user in the chatroom.\n")
                else:
                    self.chatbox.insert(tkinter.END, f"There are {number_of_users} active users in the chatroom.\n")

                self.display_report(report_message)

            # send back to menu
            self.chatbox.insert(tkinter.END, "Please select one of the following options:\n\t1. Get a report of the chatroom from the server.\n\t2. Request to join the chatroom.\n\t3. Quit the program.\n")
            self.chatbox.yview(tkinter.END)  # scrolls down based on chat moving
            self.textbox.bind("<Return>", self.handle_choice)
        elif option == "2":
            self.sock.send("<request_join>".encode('utf-8'))
            server_message = self.sock.recv(1024).decode('ascii')

            # server is full, reject join request
            if server_message == "<MAX_USERS>":
                self.chatbox.insert(tkinter.END,f"The server rejects the join request. The chatroom has reached its maximum capacity.\n")

                # send back to menu
                self.chatbox.insert(tkinter.END,"Please select one of the following options:\n\t1. Get a report of the chatroom from the server.\n\t2. Request to join the chatroom.\n\t3. Quit the program.\n")
                self.chatbox.yview(tkinter.END)  # scrolls down based on chat moving
                self.textbox.bind("<Return>", self.handle_choice)
            # server is not full, ask for name
            else:
                self.chatbox.insert(tkinter.END, "Please enter a username.\n")
                self.textbox.bind("<Return>", self.request_chatroom)
        elif option == "3":
            self.stop()

        # clear out the input box
        self.textbox.delete(0, tkinter.END)

    def request_chatroom(self, event):
        self.nickname = self.textbox.get()

        if self.nickname != "" or self.nickname is not None:
            # if there is not an existing connection, make one
            if self.sock is None:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((HOST, PORT))

            nickname_flag = "<client_nickname>" + self.nickname
            self.sock.send(nickname_flag.encode('utf-8'))

            server_message = "empty"

            server_message = self.sock.recv(1024).decode('ascii')

            if server_message == "<accepted>":
                # display connection messages and send a message when they type and enter
                self.textbox.delete(0, tkinter.END)
                self.chatbox.delete(1.0, tkinter.END)
                self.textbox.bind("<Return>", self.write)

                # start receive thread
                self.receive_thread = threading.Thread(target=self.receive)
                self.receive_thread.start()
            else:
                self.chatbox.insert(tkinter.END,f"The server rejects the join request. Another user is using this username.\n")

                # send back to menu
                self.chatbox.insert(tkinter.END,"Please select one of the following options:\n\t1. Get a report of the chatroom from the server.\n\t2. Request to join the chatroom.\n\t3. Quit the program.\n")
                self.chatbox.yview(tkinter.END)  # scrolls down based on chat moving
                self.textbox.bind("<Return>", self.handle_choice)

    # receive server messages and handle them
    def receive(self):
        global downloads_path
        while True:
            try:
                message = self.sock.recv(1024).decode('utf-8')
    

                # +++++ DOWNLOAD ATTACHMENT +++++
                if message.startswith("<FOR_DOWNLOAD>"):
                    # parse message
                    file_message = message
                    file_contents = message.replace("<FOR_DOWNLOAD>", "", 1)
                    file_name, file_text = file_contents.split('|', 1)

                    # set up download path
                    downloads_path = str(Path.home() / "downloads")
                    os.makedirs(downloads_path, exist_ok=True)
                    file_path = os.path.join(downloads_path, file_name)

                    try:
                        # Open the file in write mode and write the text
                        with open(file_path, 'w') as file:
                            file.write(file_text)
                        path = file_path
                        self.sock.send("<dl_done>".encode('ascii'))
                    except:
                        self.sock.send("<dl_done>".encode('ascii'))

                    
                # +++++ REGULAR SERVER MESSAGES +++++
                else:
                    self.chatbox.insert(tkinter.END, message + '\n')
                    self.chatbox.yview(tkinter.END)  # scrolls down based on chat moving
            except ConnectionAbortedError:
                break
            except:
                self.sock.close()
                self.sock = None
                break

    # send messages to the server
    def write(self, event=None):
        message = self.textbox.get()
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        

        if message == 'q':
            #self.sock.send(f'{self.nickname} left the chat.'.encode('utf-8'))
            self.sock.send(f"<client_sent_q>".encode('ascii'))
            self.sock.close()
            self.sock = None
            self.chatbox.delete(1.0, tkinter.END)

            # enters the menu again
            self.chatbox.insert(tkinter.END, "Please select one of the following options:\n\t1. Get a report of the chatroom from the server.\n\t2. Request to join the chatroom.\n\t3. Quit the program.\n")
            self.chatbox.yview(tkinter.END)  # scrolls down based on chat moving
            self.textbox.bind("<Return>", self.handle_choice)

            self.textbox.delete(0, tkinter.END)
        # +++++ REQUEST ATTACHMENT MESSAGES +++++
        elif message == 'a':
            self.textbox.delete(0, tkinter.END)
            self.chatbox.insert(tkinter.END, f"Please enter the file path and name:\n")
            self.textbox.bind("<Return>", self.read_and_parse_file)
        else:
            self.sock.send(f'{timestamp} {self.nickname}: {message}'.encode('utf-8'))
            self.textbox.delete(0, tkinter.END)

    def stop(self):
        self.sock.close()
        self.sock = None
        self.window.quit()

    # check how many users are in the client list
    @staticmethod
    def count_report_length(info):
        number_of_users = len(info.split(","))
        return number_of_users

    # display the messages in report format
    def display_report(self, info):
        info_list = info.split(",")

        index = 1
        for item in info_list:
            self.chatbox.insert(tkinter.END, f"{index}: {str(item)}\n")
            index += 1

    # send txt info
    def read_and_parse_file(self, event):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        file_name = self.textbox.get()
        self.textbox.delete(0, tkinter.END)

        if os.path.isfile(file_name):
            try:
                with open(file_name, 'r') as file:
                    contents = file.read()
                    file_info = contents

                    self.sock.send(f"<attachment_flag>{file_name}|{timestamp} {self.nickname}: {file_info}\n".encode('ascii'))
            except:
                self.chatbox.insert(tkinter.END, f"There was an error reading the file.\n")
        else:
            file_info = f"The file {file_name} does not exist.\n"
        self.textbox.delete(0, tkinter.END)
        self.textbox.bind("<Return>", self.write)


if __name__ == "__main__":
    ChatClient()