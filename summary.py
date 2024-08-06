import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

class Summary:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def get_daily_summary(self):
        cursor = self.db_connection.cursor()
        # Query to group expenses by date and sum the amounts
        cursor.execute('''
            SELECT date, SUM(amount) FROM expenses GROUP BY date
        ''')
        return cursor.fetchall()

    def get_monthly_summary(self):
        cursor = self.db_connection.cursor()
        # Query to extract the month and year, group by them, and sum the amounts
        cursor.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount) FROM expenses GROUP BY month
        ''')
        return cursor.fetchall()

    def get_category_summary(self):
        cursor = self.db_connection.cursor()
        # Query to group expenses by category and sum the amounts
        cursor.execute('''
            SELECT category, SUM(amount) FROM expenses GROUP BY category
        ''')
        return cursor.fetchall()

    def plot_daily_summary(self):
        daily_summary = self.get_daily_summary()

        dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in daily_summary]
        amounts = [row[1] for row in daily_summary]

        plt.figure(figsize=(10, 6))
        plt.plot(dates, amounts, marker='o')
        plt.title('Daily Expenses')
        plt.xlabel('Date')
        plt.ylabel('Total Amount')
        plt.grid(True)
        plt.tight_layout()
        plt.xticks(rotation=45)
        plt.show()

    def plot_monthly_summary(self):
        monthly_summary = self.get_monthly_summary()

        months = [row[0] for row in monthly_summary]
        amounts = [row[1] for row in monthly_summary]

        plt.figure(figsize=(10, 6))
        plt.bar(months, amounts, color='skyblue')
        plt.title('Monthly Expenses')
        plt.xlabel('Month')
        plt.ylabel('Total Amount')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

    def plot_category_summary(self):
        category_summary = self.get_category_summary()

        categories = [row[0] for row in category_summary]
        amounts = [row[1] for row in category_summary]

        plt.figure(figsize=(10, 6))
        plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140)
        plt.title('Expenses by Category')
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.tight_layout()
        plt.show()
