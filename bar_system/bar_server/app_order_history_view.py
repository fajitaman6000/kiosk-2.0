# bar_server/app_order_history_view.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from datetime import datetime, timedelta, timezone

class OrderHistoryView(QDialog):
    """
    A modal view to display and filter the history of all orders.
    It inherits from QDialog to provide modal behavior, blocking the main
    window until it is closed.
    """
    def __init__(self, order_manager, parent=None):
        super().__init__(parent)
        self.order_manager = order_manager

        self.setWindowTitle("Order History")
        self.setMinimumSize(1000, 700)
        self.setModal(True)

        self._setup_ui()
        self.filter_orders("today")  # Default view

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Filter buttons
        filter_layout = QHBoxLayout()
        today_btn = QPushButton("Today")
        today_btn.clicked.connect(lambda: self.filter_orders("today"))
        week_btn = QPushButton("Past 7 Days")
        week_btn.clicked.connect(lambda: self.filter_orders("week"))
        all_btn = QPushButton("All Time")
        all_btn.clicked.connect(lambda: self.filter_orders("all"))

        filter_layout.addWidget(QLabel("<b>Filter:</b>"))
        filter_layout.addWidget(today_btn)
        filter_layout.addWidget(week_btn)
        filter_layout.addWidget(all_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Orders table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Received Time", "Item", "Quantity", "Customer", "Room", "Status", "Completed Time"
        ])
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setSortingEnabled(True) # Allow column sorting
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.history_table, stretch=1)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def filter_orders(self, mode):
        all_orders = self.order_manager.pending_orders + self.order_manager.completed_orders

        now_utc = datetime.now(timezone.utc)
        filtered_list = []

        if mode == "today":
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            filtered_list = [
                o for o in all_orders
                if datetime.fromisoformat(o['received_timestamp_utc']) >= today_start
            ]
        elif mode == "week":
            week_ago = now_utc - timedelta(days=7)
            filtered_list = [
                o for o in all_orders
                if datetime.fromisoformat(o['received_timestamp_utc']) >= week_ago
            ]
        else:  # "all"
            filtered_list = all_orders

        # Sort by received time, newest first, before populating
        sorted_list = sorted(filtered_list, key=lambda o: o['received_timestamp_utc'], reverse=True)
        self.populate_table(sorted_list)

    def populate_table(self, orders):
        self.history_table.setSortingEnabled(False) # Disable sorting during population for performance
        self.history_table.setRowCount(0)  # Clear table
        for order in orders:
            row_position = self.history_table.rowCount()
            self.history_table.insertRow(row_position)

            # --- Column 0: Received Time ---
            received_dt_utc = datetime.fromisoformat(order['received_timestamp_utc'])
            received_dt_local = received_dt_utc.astimezone(None)
            self.history_table.setItem(row_position, 0, QTableWidgetItem(received_dt_local.strftime('%Y-%m-%d %H:%M:%S')))

            # --- Column 1: Item ---
            item_name = order.get('item_name', 'N/A')
            self.history_table.setItem(row_position, 1, QTableWidgetItem(item_name))

            # --- Column 2: Quantity ---
            quantity = str(order.get("sender_stats", {}).get("quantity", 1))
            self.history_table.setItem(row_position, 2, QTableWidgetItem(quantity))

            # --- Column 3: Customer ---
            customer = order.get("sender_stats", {}).get("customer_name", "N/A")
            self.history_table.setItem(row_position, 3, QTableWidgetItem(customer))

            # --- Column 4: Room ---
            # --- MODIFIED --- Use sender_hostname as the room identifier
            room = order.get("sender_hostname", "N/A")
            self.history_table.setItem(row_position, 4, QTableWidgetItem(room))

            # --- Column 5: Status ---
            status = order.get('status', 'Unknown')
            self.history_table.setItem(row_position, 5, QTableWidgetItem(status))

            # --- Column 6: Completed Time ---
            completed_time_str = "---"
            if 'completed_timestamp_utc' in order and order['completed_timestamp_utc']:
                completed_dt_utc = datetime.fromisoformat(order['completed_timestamp_utc'])
                completed_dt_local = completed_dt_utc.astimezone(None)
                completed_time_str = completed_dt_local.strftime('%Y-%m-%d %H:%M:%S')
            self.history_table.setItem(row_position, 6, QTableWidgetItem(completed_time_str))
        
        self.history_table.setSortingEnabled(True)