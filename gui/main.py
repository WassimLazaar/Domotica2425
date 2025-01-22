import tkinter as tk
import serial
import threading
import time
from serial.tools import list_ports

ser = serial.Serial('COM16', 115200, timeout=1)

next_address = 0x0010  # Eerste beschikbare address
next_group = 0xc000 # Eerste beschikbare group address
node_count = 1
group_count = 1
selected_address = None  # Variabele om geselecteerd adres op te slaan
selected_group = None  # Variabele om geselecteerd adres op te slaan

# def send_command():
#     command = command_entry.get()
#     if command:
#         # Start een nieuwe thread voor het verzenden van het command
#         threading.Thread(target=send_serial_command, args=(command,)).start()

def send_serial_command(command):
    """Functie om een command via de seriële poort te verzenden."""
    ser.write((command + "\r\n").encode('utf-8'))
    ser.flush()  # Zorgt ervoor dat de buffer wordt geleegd en de data meteen wordt verzonden
    print(f"Verzonden: {command}")
    time.sleep(0.1)  # Simuleer enige verwerkingstijd

    response = ser.read(ser.in_waiting or 1).decode('utf-8')
    if response:
        output_text.insert(tk.END, f"Response: {response}\n")
    else:
        output_text.insert(tk.END, "No response from device\n")
                           
                           
def close_serial():
    ser.close()
    print("Seriele poort gesloten.")

def add_node(node_name, address):
    """Voegt een node toe aan de lijstbox en slaat het adres op."""
    if node_name:
        node_listbox.insert(tk.END, f"{node_name} ({address})")  # Voeg adres toe aan lijst

def reset_serial_buffers():
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        print(f"Failed to reset serial buffers: {e}")

def add_model():
    model_str = f"0x1000"
    model_listbox.insert(tk.END, f"Gen_OnOff_svr: ({model_str})")
    model_str = f"0x1001"
    model_listbox.insert(tk.END, f"Gen_OnOff_cli: ({model_str})")

def create_group():    
    global next_group
    global group_count
    group_str = f"0x{next_group:04X}"
    group_listbox.insert(tk.END, f"group{group_count}: ({group_str})")  # Voeg adres toe aan lijst
    group_count += 1
    next_group += 1

def sub_group():
    global selected_address
    global selected_group
    global selected_model
    sending = f"mesh models cfg model sub-add {selected_address} {selected_group} {selected_model}"
    send_serial_command(sending)

def remove_node():
    selected_node = node_listbox.curselection()  # Haal de geselecteerde node op
    if selected_node:
        node_listbox.delete(selected_node)  # Verwijder de geselecteerde node
    send_serial_command("mesh models cfg reset") #unprovision de node

def on_node_select(event):
    """Functie die wordt aangeroepen wanneer een node wordt geselecteerd."""
    global selected_address

    selected_index = node_listbox.curselection()
    if selected_index:
        selected_node = node_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_node.split("(")[-1].strip(")")
        selected_address = str(address)  # Opslaan voor gebruik
        sending = f"mesh target dst {selected_address}"
        send_serial_command(sending)

def on_group_select(event):
    """Functie die wordt aangeroepen wanneer een node wordt geselecteerd."""
    global selected_group

    selected_index = group_listbox.curselection()
    if selected_index:
        selected_group = group_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_group.split("(")[-1].strip(")")
        selected_group = address  # Opslaan voor gebruik
        sending = f"mesh target dst {selected_group}"
        send_serial_command(sending)

def on_model_select(event):
    """Functie die wordt aangeroepen wanneer een node wordt geselecteerd."""
    global selected_model

    selected_index = model_listbox.curselection()
    if selected_index:
        selected_model = model_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_model.split("(")[-1].strip(")")
        selected_model = address  # Opslaan voor gebruik


def led_on():
    send_serial_command("mesh test net-send 82020100") #led on 

def led_off():
    send_serial_command("mesh test net-send 82020000") #led off

def get_status():
    send_serial_command("mesh test nes-send 8201") #get status


def init_pr():
     global prinit
     send_serial_command("mesh init") #om mesh commands te kunnen gebruiken
     send_serial_command("mesh reset-local") #reset de node indien deze nog geprovisioned is
     send_serial_command("mesh prov uuid aaaabbbb") #geef uuid aan de provisioner
     send_serial_command("mesh cdb create") #maak een cdb netwerk aan
     send_serial_command("mesh prov local 0 0x0001") #self provision de node met netwerkkeyindex 0 en node address 0x0001
     send_serial_command("mesh models cfg appkey add 0 0") #add appkey aan het netwerk
     add_node("Provisioner:", "0x0001")
     prinit.pack_forget()

def find_dongle_port():
    """Automatically detect the correct port for the dongle."""
    ports = list_ports.comports()
    for port in ports:
        # Check if the port matches your dongle (adjust VID/PID or description)
        if port.device == "COM16":
            return port.device
    return None

def reinitialize_serial():
    """Attempt to reinitialize the serial connection."""
    global ser
    try:
        # Close the port if it's open
        if ser.is_open:
            ser.close()
        
        # Find the dongle's port
        dongle_port = find_dongle_port()
        if not dongle_port:
            print("Dongle not detected. Retrying...")
            return False

        # Reinitialize the serial connection
        ser.port = dongle_port
        ser.open()
        print(f"Reconnected to dongle on {dongle_port}")
        return True

    except serial.SerialException as e:
        print(f"Failed to reinitialize the serial port: {e}")
        return False

def watchdog_serial_communication():
    global ser
    try:
        # Try sending a test command
        ser.write(b"CHECK\n")
    except serial.SerialException:
        print("Communication error detected. Reinitializing the serial port...")
        success = reinitialize_serial()
        if not success:
            time.sleep(1)  # Wait and retry
            watchdog_serial_communication()  # Retry recursively

def appkey_add():
    reset_serial_buffers()
    time.sleep(0.1)

    sending = "mesh init"
    send_serial_command(sending)
    sending = "mesh models cfg appkey add 0 0"
    send_serial_command(sending)
    time.sleep(0.1)
    sending = f"mesh models cfg model app-bind {selected_address} 0 0x1000"
    send_serial_command(sending)
    sending = f"mesh models cfg model app-bind {selected_address} 0 0x1001"
    send_serial_command(sending)

def reconnect_provisioner():
    reset_serial_buffers()
    watchdog_serial_communication()
    time.sleep(0.1)
    # Add the app key to the network

def remote_prov():
    reset_serial_buffers()
    global next_address  # Use the global variable

    # Convert the address to a hexadecimal string
    address_str = f"0x{next_address:04X}"  

    send_serial_command("mesh prov beacon-listen on")  
    sending = f"mesh prov remote-adv dddd 0 {address_str} 30"
    send_serial_command(sending)  

    add_node(f"node{node_count}:", f"{address_str}")  
    next_address += 1  # Increment the address for the next node

def main():
    root = tk.Tk()
    root.title("TUI Domotica 2024/2025")
    root.geometry("1000x800")  # Set the window size
    
    # Set black background for the window
    root.configure(bg='#222222')

    root.grid_rowconfigure(0, weight=0)  # Top space (label)
    root.grid_rowconfigure(1, weight=0)  # Listboxes
    root.grid_rowconfigure(2, weight=0)  # Buttons
    root.grid_rowconfigure(3, weight=0)  # Empty row between buttons and output
    root.grid_rowconfigure(4, weight=1)  # Output area (more space)

    root.grid_columnconfigure(0, weight=1)  # Left space
    root.grid_columnconfigure(1, weight=1)  # Center space for the widgets
    root.grid_columnconfigure(2, weight=1)  # Right space

    # Add a label at the top
    label = tk.Label(root, text="TUI Domotica 2024/2025", font=('Helvetica', 20, 'bold'), fg='white', bg='#222222')
    label.grid(row=0, column=0, columnspan=3, pady=10)

    # Create a frame for the Listboxes
    listbox_frame = tk.Frame(root, bg='#222222')
    listbox_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

    # Add a Listbox to display nodes
    global node_listbox
    node_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    node_listbox.grid(row=0, column=0, padx=5, pady=5)
    node_listbox.bind("<<ListboxSelect>>", on_node_select)

    # Add a Listbox to display groups
    global group_listbox
    group_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    group_listbox.grid(row=0, column=1, padx=5, pady=5)
    group_listbox.bind("<<ListboxSelect>>", on_group_select)

    # Add a Listbox to display models
    global model_listbox
    model_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    model_listbox.grid(row=0, column=2, padx=5, pady=5)
    model_listbox.bind("<<ListboxSelect>>", on_model_select)

    # Create a frame for the buttons
    button_frame = tk.Frame(root, bg='#222222')
    button_frame.grid(row=2, column=0, columnspan=3, pady=10)

    # Define button size
    button_width = 25
    button_height = 2

    # Button styles (lighter black background and white text)
    button_style = {'width': button_width, 'height': button_height, 'font': ('Helvetica', 12, 'bold'), 'bg': '#333333', 'fg': 'white'}

    # Add buttons in a grid layout
    remove_button = tk.Button(button_frame, text="Verwijder Geselecteerde Node", command=remove_node, **button_style)
    remove_button.grid(row=0, column=0, padx=5, pady=5)

    ledon = tk.Button(button_frame, text="LED on", command=led_on, **button_style)
    ledon.grid(row=0, column=1, padx=5, pady=5)

    ledoff = tk.Button(button_frame, text="LED off", command=led_off, **button_style)
    ledoff.grid(row=0, column=2, padx=5, pady=5)

    prinit = tk.Button(button_frame, text="Initialize Provisioner", command=init_pr, **button_style)
    prinit.grid(row=1, column=0, padx=5, pady=5)

    addkey = tk.Button(button_frame, text="Add AppKey", command=appkey_add, **button_style)
    addkey.grid(row=1, column=1, padx=5, pady=5)

    givekey = tk.Button(button_frame, text="Reconnect Provisioner", command=reconnect_provisioner, **button_style)
    givekey.grid(row=1, column=2, padx=5, pady=5)

    creategroup = tk.Button(button_frame, text="Create Group", command=create_group, **button_style)
    creategroup.grid(row=2, column=0, padx=5, pady=5)

    subgroup = tk.Button(button_frame, text="Subscribe Node to Group", command=sub_group, **button_style)
    subgroup.grid(row=2, column=1, padx=5, pady=5)

    remoteprov = tk.Button(button_frame, text="Remote Provisioning", command=remote_prov, **button_style)
    remoteprov.grid(row=2, column=2, padx=5, pady=5)

    getstatus = tk.Button(button_frame, text="Get Status", command=get_status, **button_style)
    getstatus.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

    quit_button = tk.Button(button_frame, text="Afsluiten", command=root.quit, **button_style)
    quit_button.grid(row=3, column=1, columnspan=2, padx=5, pady=5)

    # Output text area
    global output_text
    output_text = tk.Text(root, height=10, width=80, bg='#222222', fg='white', font=('Helvetica', 12))
    output_text.grid(row=4, column=0, columnspan=3, padx=10, pady=30)

    # Start the GUI loop
    root.mainloop()

if __name__ == "__main__":
    main()
