import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime


class Summary:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def get_daily_summary(self):
        cursor = self.db_connection.cursor()
        cursor.execute('''
            SELECT date, SUM(amount) FROM expenses GROUP BY date ORDER BY date DESC
        ''')
        return cursor.fetchall()

    def get_monthly_summary(self):
        cursor = self.db_connection.cursor()
        cursor.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount) FROM expenses GROUP BY month ORDER BY month DESC
        ''')
        return cursor.fetchall()

    def get_category_summary(self):
        cursor = self.db_connection.cursor()
        cursor.execute('''
            SELECT category, SUM(amount) FROM expenses GROUP BY category
        ''')
        return cursor.fetchall()

    def get_daily_summary_plot(self):
        daily_summary = self.get_daily_summary()

        dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in daily_summary]
        amounts = [row[1] for row in daily_summary]

        figure, ax = plt.subplots(figsize=(10, 6))
        ax.plot(dates, amounts, marker='o')
        ax.set_title('Daily Expenses')
        ax.set_xlabel('Date')
        ax.set_ylabel('Total Amount')
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        return figure

    def get_monthly_summary_plot(self):
        monthly_summary = self.get_monthly_summary()

        months = [row[0] for row in monthly_summary]
        amounts = [row[1] for row in monthly_summary]

        figure, ax = plt.subplots(figsize=(10, 6))
        ax.bar(months, amounts, color='skyblue')
        ax.set_title('Monthly Expenses')
        ax.set_xlabel('Month')
        ax.set_ylabel('Total Amount')
        plt.xticks(rotation=45)
        plt.tight_layout()
        return figure

    def get_category_summary_plot(self):
        category_summary = self.get_category_summary()

        categories = [row[0] for row in category_summary]
        amounts = [row[1] for row in category_summary]

        figure, ax = plt.subplots(figsize=(10, 6))
        ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140)
        ax.set_title('Expenses by Category')
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.tight_layout()
        return figure
