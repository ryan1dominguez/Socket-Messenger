import socket
import threading
from datetime import datetime
import os
from pathlib import Path

HOST = '127.0.0.1'  # local host
PORT = 18000

# ========== SET UP THE SERVER ==========
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # internet type socket, TCP socket
server.bind((HOST, PORT))  # bind to a tuple of the server and port

# set up downloads path (and make sure it exists
downloads_path = str(Path.home() / "downloads")
os.makedirs(downloads_path, exist_ok=True)

server.listen()

MAX_USERS = 3               # max users
clients = []                # holds clients
nicknames = []              # holds their nicknames
client_report_list = []     # holds both in a nice format
msgs = []                   # list of messages sent

# Broadcast: Sends a message to all the connected clients
def broadcast(message):
    for client in clients:
        client.send(message)

# HANDLE: once connected, this is how the connection is handled. take client as a parameter to run threads with
def handle(client):
    global client_report_list
    global downloads_path

    while True:
        # +++++ HANDLE NORMAL CONNECTIONS +++++
        try:
            # get a message from the client of 1024 bytes to broadcast to everyone
            message = client.recv(1024)
            timestamp = datetime.now().strftime("[%H:%M:%S]")

            # +++++ CHOSE 1: SEND REPORT +++++
            if message.decode('ascii') == "<request_report>":
                print("Sending a report to the client.")
                # make sure the client list isn't empty:
                if not client_report_list:
                    client.send("<NO_USERS>".encode('ascii'))
                else:
                    string_report_list = ",".join(client_report_list)
                    client.send(string_report_list.encode('ascii'))
            # +++++ CHOSE 2: HANDLE JOIN REQUEST +++++
            elif message.decode('ascii') == "<request_join>":
                # remove if server is full
                if len(client_report_list) >= MAX_USERS:
                    print("Rejected join request: Server is full.")  # MERGE
                    client.send("<MAX_USERS>".encode('ascii'))
                # grab name if server isn't full
                else:
                    client.send("<ACCEPTED>".encode('ascii'))
            # +++++ REQUEST NICKNAME +++++
            elif message.decode('ascii').startswith("<client_nickname>"):
                # parse nickname
                nickname = str(message.decode('ascii'))
                nickname = nickname.replace("<client_nickname>", "", 1)

                # check if the name exists
                name_exists = False
                for item in client_report_list:
                    if nickname in item:
                        name_exists = True

                if name_exists:
                    print(f"Rejecting join request: {nickname} is already in the server.")  # MERGE
                    client.send("<duplicate_name>".encode('ascii'))
                else:
                    client.send("<accepted>".encode('ascii'))
                    # append client and nickname to all lists
                    nicknames.append(nickname)
                    clients.append(client)
                    client_report_list.append(strip_info_from_client(nickname, str(client)))

                    print(f"{nickname} has joined the chat")  # print to the server 
                    client.send("The server welcomes you to the chatroom.\nType lowercase 'q' and press enter at any time to quit the chatroom.\nType lowercase 'a' and press enter at any time to upload an attachment to the chatroom.\nHere is a history of the chatroom:\n".encode('utf-8'))
                    for x in msgs:
                        if x.decode('ascii') != "": 
                            client.send(((x.decode('ascii')) + "\n").encode('ascii'))

                    broadcast(f"{timestamp} Server: {nickname} has connected to the server.".encode('utf-8'))  # broadcast to all users
                    msgs.append(f"{timestamp} Server: {nickname} has connected to the server.".encode('ascii'))
            elif message.decode('ascii') == "<client_sent_q>":
                disconnect(client)
                break
            elif message.decode('ascii') == "<dl_done>":
                print("Download is done for a client.")
            # +++++ REQUEST ATTACHMENT MESSAGES +++++
            elif message.decode('ascii').startswith("<attachment_flag>"):
                # parse message
                file_contents = str(message.decode('ascii'))
                file_contents = file_contents.replace("<attachment_flag>", "", 1)

                file_name, send_this_message = file_contents.split('|', 1)
                not_needed, text_contents = send_this_message.split(': ', 1)

                # send message
                broadcast(f"{send_this_message}".encode('utf-8'))  # broadcast to all users
                msgs.append(f"{send_this_message}".encode('ascii'))

                # set up download path
                downloads_path = str(Path.home() / "downloads")
                os.makedirs(downloads_path, exist_ok=True)
                file_path = os.path.join(downloads_path, file_name)

                try:
                    # Open the file in write mode and write the text
                    with open(file_path, 'w') as file:
                        file.write(text_contents)
                    path = file_path
                    print(f"Successfully downloaded file {file_name}.")
                    client.send(f"<FOR_DOWNLOAD>{file_name}|{text_contents}".encode('ascii'))
                except:
                    print(f"Could not download file {file_name}.")

                
            # +++++ NORMAL MESSAGES +++++
            else:
                # display message to all users only if people are in the chat
                if len(client_report_list) != 0:
                    broadcast(message)
                    msgs.append(message)
        # +++++ HANDLE DISCONNECTS OR CRASHES +++++
        except:
            # call disconnect
            disconnect(client)
            # break because then the full function is executed and the thread in receive stops
            break

# RECEIVE: listens and accepts new connections (main function run in main thread)
def receive():
    while True:
        # use the server's socket to accept the new connection
        client, address = server.accept()
        print(f"New connection with {str(address)}")

        thread = threading.Thread(target=handle, args=(client, ))
        thread.start()

# DISCONNECT: handles chat disconnects for any reason
def disconnect(client):
    # make sure the client is in the list (maybe they are connected but not in the chat)
    if client in clients:
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        global client_report_list 

        index = clients.index(client)

        # remove from client list and close connection
        clients.remove(client)
        client.close()

        # remove from all lists and display a disconnect message to all users
        nickname = nicknames[index]
        broadcast(f'{timestamp} {nickname} has left the chat.'.encode('utf-8')) 
        msgs.append(f'{timestamp} {nickname} has left the chat.'.encode('ascii')) 
        print(f"Disconnected {nickname} from the chat.") 
        nicknames.remove(nickname)
        client_report_list = remove_from_client_report_list(client_report_list, nickname)

# STRIP INFO FROM CLIENT REPORT LIST: for returning the port and address out of a given string of client info
def strip_info_from_client(client_name, client_info):
    # extract ip and port
    start_index = client_info.find("raddr=(") + len("raddr=(")
    end_index = client_info.find(")", start_index)
    ip_and_port = client_info[start_index:end_index]

    # split into separate variables
    client_ip = ip_and_port.split(", ")[0].strip("'")
    client_port = ip_and_port.split(", ")[1]

    # store into string before returning
    client_report_info = str(f"{client_name} at IP: {client_ip} and port: {client_port}")

    return client_report_info

# REMOVE FROM CLIENT REPORT LIST: for removing the client from the client_list upon disconnect
def remove_from_client_report_list(array, name):
    return [item for item in array if name not in item]


print("Server is running...")
receive()