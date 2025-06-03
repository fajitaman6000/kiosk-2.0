import socket
import json
import argparse
import time

# --- Configuration ---
RECEIVER_HOST = 'localhost'  # IP address or hostname of the receiver app
RECEIVER_PORT = 50888        # <--- IMPORTANT: MATCH THIS PORT WITH YOUR RECEIVER APP
SENDER_HOSTNAME = socket.gethostname()

def send_order(item_id: str, quantity: int, customer_name: str):
    """
    Constructs an order and sends it to the receiver.
    """
    order_payload = {
        "item_id": item_id,
        "sender_stats": {
            "quantity": quantity,
            "customer_name": customer_name,
            "order_time_local": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "sender_hostname": SENDER_HOSTNAME
    }

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Attempting to connect to {RECEIVER_HOST}:{RECEIVER_PORT}...")
            s.connect((RECEIVER_HOST, RECEIVER_PORT))
            print(f"Connected. Sending order for item: {item_id}")
            
            json_payload = json.dumps(order_payload)
            s.sendall(json_payload.encode('utf-8'))
            
            # Wait for acknowledgment (optional, but good practice)
            s.settimeout(5.0) # Don't wait forever for ACK
            try:
                ack = s.recv(1024)
                print(f"Receiver ACK: {ack.decode('utf-8')}")
            except socket.timeout:
                print("Receiver ACK timed out.")
            except Exception as e:
                print(f"Error receiving ACK: {e}")

    except ConnectionRefusedError:
        print(f"ERROR: Connection refused. Is the receiver app running on {RECEIVER_HOST}:{RECEIVER_PORT}?")
        print(f"       (Double-check port {RECEIVER_PORT} in receiver_app.py and that the app is active)")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send an order to the receiver app.")
    parser.add_argument("item_id", type=str, help="ID of the item to order (e.g., 'apple', 'banana', '1').")
    parser.add_argument("-q", "--quantity", type=int, default=1, help="Quantity to order.")
    parser.add_argument("-c", "--customer", type=str, default="Anonymous", help="Customer name.")
    
    args = parser.parse_args()

    print(f"Sending order: Item ID='{args.item_id}', Quantity={args.quantity}, Customer='{args.customer}'")
    send_order(args.item_id, args.quantity, args.customer)

    # Example of sending multiple orders or different items:
    # print("\nSending another order...")
    # time.sleep(1) # Small delay
    # send_order("banana", 2, "John Doe")

    # print("\nSending an order for an unknown item (for testing error handling)...")
    # time.sleep(1)
    # send_order("watermelon", 1, "Test Invalid") # Assuming 'watermelon' is not in ITEMS_DATA