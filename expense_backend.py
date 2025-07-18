import json
import csv
from datetime import datetime
from pathlib import Path


class ExpenseManager:
    def __init__(self):
        self.data_file = "expenses.json"
        self.expenses = []

    def load_expenses(self, json_data=None):
        """Load expenses from JSON data or file"""
        if json_data:
            self.expenses = json.loads(json_data)
        else:
            try:
                with open(self.data_file, 'r') as f:
                    self.expenses = json.load(f)
            except FileNotFoundError:
                print("No expenses file found. Starting fresh!")
                self.expenses = []

    def save_expenses(self):
        """Save expenses to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.expenses, f, indent=2)
        print(f"Saved {len(self.expenses)} expenses to {self.data_file}")

    def add_expense(self, date, amount, description, category):
        """Add a new expense"""
        expense = {
            'id': int(datetime.now().timestamp() * 1000),
            'date': date,
            'amount': float(amount),
            'description': description,
            'category': category
        }
        self.expenses.append(expense)
        return expense

    def export_to_csv(self, filename="expenses.csv"):
        """Export expenses to CSV file"""
        if not self.expenses:
            print("No expenses to export!")
            return

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Date', 'Description', 'Category', 'Amount']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for expense in sorted(self.expenses, key=lambda x: x['date'], reverse=True):
                writer.writerow({
                    'Date': expense['date'],
                    'Description': expense['description'],
                    'Category': expense['category'],
                    'Amount': f"${expense['amount']:.2f}"
                })

        print(f"Exported {len(self.expenses)} expenses to {filename}")

    def get_summary(self):
        """Get expense summary"""
        if not self.expenses:
            return "No expenses recorded yet!"

        total = sum(e['amount'] for e in self.expenses)

        # Category breakdown
        categories = {}
        for expense in self.expenses:
            cat = expense['category']
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += expense['amount']

        # Create summary
        summary = f"\n{'=' * 50}\n"
        summary += f"EXPENSE SUMMARY\n"
        summary += f"{'=' * 50}\n\n"
        summary += f"Total Expenses: ${total:.2f}\n"
        summary += f"Number of Transactions: {len(self.expenses)}\n"
        summary += f"Average per Transaction: ${total / len(self.expenses):.2f}\n\n"

        summary += f"BREAKDOWN BY CATEGORY:\n"
        summary += f"{'-' * 30}\n"
        for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total) * 100
            summary += f"{cat:.<20} ${amount:>8.2f} ({percentage:>5.1f}%)\n"

        return summary

    def get_monthly_summary(self):
        """Get monthly breakdown"""
        if not self.expenses:
            return "No expenses recorded yet!"

        # Group by month
        monthly = {}
        for expense in self.expenses:
            month_key = expense['date'][:7]  # YYYY-MM
            if month_key not in monthly:
                monthly[month_key] = 0
            monthly[month_key] += expense['amount']

        summary = f"\n{'=' * 50}\n"
        summary += f"MONTHLY BREAKDOWN\n"
        summary += f"{'=' * 50}\n\n"

        for month, amount in sorted(monthly.items(), reverse=True):
            summary += f"{month}: ${amount:,.2f}\n"

        return summary


# Simple CLI interface
def main():
    manager = ExpenseManager()

    while True:
        print("\n" + "=" * 50)
        print("EXPENSE TRACKER - PYTHON BACKEND")
        print("=" * 50)
        print("1. Load expenses from file")
        print("2. Add new expense")
        print("3. Export to CSV")
        print("4. View summary")
        print("5. View monthly breakdown")
        print("6. Save and exit")
        print("7. Exit without saving")

        choice = input("\nEnter your choice (1-7): ").strip()

        if choice == '1':
            manager.load_expenses()
            print(f"Loaded {len(manager.expenses)} expenses")

        elif choice == '2':
            date = input("Date (YYYY-MM-DD): ").strip()
            amount = float(input("Amount: $").strip())
            description = input("Description: ").strip()
            print("\nCategories: Food, Transport, Shopping, Bills, Entertainment, Health, Other")
            category = input("Category: ").strip()

            expense = manager.add_expense(date, amount, description, category)
            print(f"Added expense: {description} - ${amount:.2f}")

        elif choice == '3':
            filename = input("Enter filename (default: expenses.csv): ").strip()
            if not filename:
                filename = "expenses.csv"
            manager.export_to_csv(filename)

        elif choice == '4':
            print(manager.get_summary())

        elif choice == '5':
            print(manager.get_monthly_summary())

        elif choice == '6':
            manager.save_expenses()
            print("Goodbye!")
            break

        elif choice == '7':
            print("Exiting without saving. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()