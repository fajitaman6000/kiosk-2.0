import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import json
import threading
import time
import queue # For thread-safe communication between network thread and GUI

# --- Configuration ---
SERVER_HOST = 'localhost'
SERVER_PORT = 50888 # Must match receiver's port
CLIENT_HOSTNAME = socket.gethostname()

class BarClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Bar Kiosk Client - {CLIENT_HOSTNAME}")
        self.root.geometry("600x500")

        self.sock = None
        self.network_thread = None
        self.is_connected = False
        self.gui_queue = queue.Queue() # For messages from network thread to GUI

        self.items_cache = [] # List of item dicts {"id": "...", "name": "...", "description": "..."}

        # --- UI Elements ---
        self.status_label = ttk.Label(root, text="Status: Disconnected", padding=5)
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        self.connect_button = ttk.Button(root, text="Connect to Server", command=self.toggle_connection)
        self.connect_button.pack(side=tk.TOP, pady=5)

        # Frame for item buttons
        self.items_frame = ttk.Frame(root, padding=10)
        self.items_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(root, height=5, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.update_items_display()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_gui_queue() # Start polling the queue

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        print(f"[LOG] {message}")


    def toggle_connection(self):
        if not self.is_connected:
            self.connect_to_server()
        else:
            self.disconnect_from_server()

    def connect_to_server(self):
        if self.is_connected:
            self.log_message("Already connected.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0) # Connection timeout
            self.log_message(f"Attempting to connect to {SERVER_HOST}:{SERVER_PORT}...")
            self.sock.connect((SERVER_HOST, SERVER_PORT))
            self.sock.settimeout(None) # Back to blocking for recv, or set for recv
            self.is_connected = True
            self.status_label.config(text="Status: Connected")
            self.connect_button.config(text="Disconnect")
            self.log_message("Connected to server.")

            # Start network listener thread
            self.network_thread_stop_event = threading.Event()
            self.network_thread = threading.Thread(target=self.listen_for_server_messages, daemon=True)
            self.network_thread.start()

            # Request initial item list
            self.send_message("REQUEST_ITEMS", {})

        except socket.timeout:
            self.log_message("Connection timed out.")
            self.is_connected = False
            if self.sock: self.sock.close(); self.sock = None
            self.status_label.config(text="Status: Connection Failed (Timeout)")
        except ConnectionRefusedError:
            self.log_message("Connection refused by server.")
            self.is_connected = False
            if self.sock: self.sock.close(); self.sock = None
            self.status_label.config(text="Status: Connection Refused")
        except Exception as e:
            self.log_message(f"Connection error: {e}")
            self.is_connected = False
            if self.sock: self.sock.close(); self.sock = None
            self.status_label.config(text=f"Status: Error ({type(e).__name__})")


    def disconnect_from_server(self):
        if not self.is_connected and not self.sock:
            self.log_message("Not connected.")
            return

        self.is_connected = False # Set this first to signal network thread to stop
        if self.network_thread_stop_event:
            self.network_thread_stop_event.set()

        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except Exception as e:
                self.log_message(f"Error during socket shutdown: {e}")
            finally:
                self.sock = None
        
        if self.network_thread and self.network_thread.is_alive():
            self.network_thread.join(timeout=2) # Wait for thread to finish
            if self.network_thread.is_alive():
                self.log_message("Warning: Network thread did not stop cleanly.")

        self.status_label.config(text="Status: Disconnected")
        self.connect_button.config(text="Connect to Server")
        self.log_message("Disconnected from server.")
        self.items_cache = [] # Clear items on disconnect
        self.update_items_display()


    def listen_for_server_messages(self):
        buffer = b""
        if not self.sock:
            self.log_message("Network listener: No socket.")
            return

        self.sock.settimeout(1.0) # Timeout for recv to allow checking stop event
        
        while self.is_connected and not self.network_thread_stop_event.is_set():
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.log_message("Server closed connection (received empty chunk).")
                    self.gui_queue.put({"type": "_HANDLE_DISCONNECT"})
                    break 
                
                buffer += chunk
                while b'\n' in buffer:
                    message_json, buffer = buffer.split(b'\n', 1)
                    if not message_json.strip(): continue

                    try:
                        message = json.loads(message_json.decode('utf-8'))
                        self.gui_queue.put(message) # Send to GUI thread for processing
                    except json.JSONDecodeError:
                        self.log_message(f"Received invalid JSON: {message_json.decode(errors='ignore')}")
                    except Exception as e:
                        self.log_message(f"Error decoding/queueing server message: {e}")

            except socket.timeout:
                continue # Check stop event and loop again
            except ConnectionResetError:
                self.log_message("Connection reset by server.")
                self.gui_queue.put({"type": "_HANDLE_DISCONNECT"})
                break
            except Exception as e:
                if self.is_connected: # Only log if we weren't expecting to disconnect
                    self.log_message(f"Network error: {e}")
                self.gui_queue.put({"type": "_HANDLE_DISCONNECT"})
                break
        
        self.log_message("Network listener thread stopped.")
        if self.is_connected:
             self.gui_queue.put({"type": "_HANDLE_DISCONNECT"})


    def process_gui_queue(self):
        try:
            while True:
                message = self.gui_queue.get_nowait()
                self.handle_server_message(message)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_gui_queue)

    def handle_server_message(self, message):
        msg_type = message.get("type")
        payload = message.get("payload", {})
        self.log_message(f"Server -> Client: Type: {msg_type}, Payload: {str(payload)[:100]}...")

        if msg_type == "AVAILABLE_ITEMS" or msg_type == "AVAILABLE_ITEMS_UPDATE":
            self.items_cache = payload.get("items", [])
            self.update_items_display()
        elif msg_type == "ORDER_ACK":
            messagebox.showinfo("Order Acknowledged", f"Order for {payload.get('item_id', 'item')} (ID: {payload.get('order_id', 'N/A')}) processed successfully!")
        elif msg_type == "ORDER_NACK":
            messagebox.showerror("Order Rejected", f"Order for {payload.get('item_id', 'item')} (ID: {payload.get('order_id', 'N/A')}) rejected: {payload.get('reason', 'Unknown reason')}")
        elif msg_type == "ERROR":
            messagebox.showerror("Server Error", f"Received error from server: {payload.get('message', 'Unknown error')}")
        elif msg_type == "SERVER_SHUTDOWN":
            messagebox.showwarning("Server Shutdown", "The server is shutting down. Disconnecting.")
            self.disconnect_from_server()
        elif msg_type == "_HANDLE_DISCONNECT":
            if self.is_connected:
                self.log_message("Handling internal disconnect signal.")
                self.disconnect_from_server()

    def update_items_display(self):
        for widget in self.items_frame.winfo_children():
            widget.destroy()

        if not self.items_cache:
            ttk.Label(self.items_frame, text="No items available from server. Connect to load items.").pack(pady=20)
            return

        cols = 3
        row, col = 0, 0
        for item in self.items_cache:
            item_id = item["id"]
            item_name = item["name"]
            item_desc = item.get("description", "No description.")
            
            btn_frame = ttk.Frame(self.items_frame, borderwidth=1, relief="solid")
            
            name_label = ttk.Label(btn_frame, text=item_name, font=("Arial", 12, "bold"), anchor="center")
            name_label.pack(pady=(5,0), fill=tk.X)
            
            desc_label = ttk.Label(btn_frame, text=item_desc, wraplength=150, justify="center", font=("Arial", 8))
            desc_label.pack(pady=2, padx=5, fill=tk.X)

            order_button = ttk.Button(btn_frame, text=f"Order {item_name}",
                                   command=lambda i=item_id, n=item_name: self.prompt_and_send_order(i, n))
            order_button.pack(pady=(0,5), padx=5)
            
            btn_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.items_frame.grid_columnconfigure(col, weight=1)

            col += 1
            if col >= cols:
                col = 0
                row += 1
        if row > 0:
            for r in range(row +1):
                 self.items_frame.grid_rowconfigure(r, weight=1)

    def prompt_and_send_order(self, item_id, item_name):
        if not self.is_connected:
            messagebox.showerror("Not Connected", "Cannot send order. Please connect to the server first.")
            return

        quantity = simpledialog.askinteger("Order Quantity", f"Enter quantity for {item_name}:",
                                           parent=self.root, minvalue=1, initialvalue=1)
        if quantity is None:
            return

        customer_name = simpledialog.askstring("Customer Name", "Enter customer name (optional):",
                                               parent=self.root)
        if customer_name is None: customer_name = "Anonymous"

        order_id = f"{CLIENT_HOSTNAME}_{int(time.time())}_{item_id}"

        order_payload = {
            "order_id": order_id,
            "item_id": item_id,
            "sender_stats": {
                "quantity": quantity,
                "customer_name": customer_name,
                "order_time_local": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "sender_hostname": CLIENT_HOSTNAME
        }
        self.send_message("ORDER_ITEM", order_payload)
        self.log_message(f"Sent order for {quantity} of {item_id} (Order ID: {order_id}).")

    def send_message(self, msg_type, payload):
        if not self.is_connected or not self.sock:
            self.log_message("Cannot send message: Not connected.")
            return False
        
        message = {"type": msg_type, "payload": payload}
        try:
            self.sock.sendall(json.dumps(message).encode('utf-8') + b'\n')
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError) as e:
            self.log_message(f"Error sending message: {e}. Disconnecting.")
            self.gui_queue.put({"type": "_HANDLE_DISCONNECT"})
            return False
        except Exception as e:
            self.log_message(f"Unexpected error sending message: {e}")
            return False

    def on_closing(self):
        if self.is_connected:
            self.disconnect_from_server()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BarClientApp(root)
    root.mainloop()