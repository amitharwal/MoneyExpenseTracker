import sqlite3
import json


class DatabaseHandler:
    def __init__(self, db_file='expenses.db'):
        self.db_file = db_file
        self.connection = self.connect_to_db()

    def connect_to_db(self):
        # Connect to SQLite database (or create it if it doesn't exist)
        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                category TEXT,
                amount REAL,
                description TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')
        connection.commit()
        return connection

    def create_expense(self, date, category, amount, description):
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO expenses (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (date, category, amount, description))
        self.connection.commit()

    def read_expenses(self):
        cursor = self.connection.cursor()
        cursor.execute('SELECT * FROM expenses')
        return cursor.fetchall()

    def update_expense(self, expense_id, date, category, amount, description):
        cursor = self.connection.cursor()
        cursor.execute('''
            UPDATE expenses
            SET date = ?, category = ?, amount = ?, description = ?
            WHERE id = ?
        ''', (date, category, amount, description, expense_id))
        self.connection.commit()

    def delete_expense(self, expense_id):
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        self.connection.commit()

    def export_to_json(self, json_file='expenses.json'):
        expenses = self.read_expenses()
        expenses_list = [
            {'id': exp[0], 'date': exp[1], 'category': exp[2], 'amount': exp[3], 'description': exp[4]}
            for exp in expenses
        ]
        with open(json_file, 'w') as file:
            json.dump(expenses_list, file, indent=4)
        print(f"Data exported to {json_file}")

    def import_from_json(self, json_file='expenses.json'):
        with open(json_file, 'r') as file:
            expenses_list = json.load(file)

        cursor = self.connection.cursor()
        for expense in expenses_list:
            cursor.execute('''
                INSERT INTO expenses (id, date, category, amount, description)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    date=excluded.date,
                    category=excluded.category,
                    amount=excluded.amount,
                    description=excluded.description
            ''', (expense['id'], expense['date'], expense['category'], expense['amount'], expense['description']))
        self.connection.commit()
        print(f"Data imported from {json_file}")

    def close_connection(self):
        self.connection.close()
