from flask import Flask, request, jsonify, render_template
import json
import os
from datetime import datetime

app = Flask(__name__)

# Where we save expenses
EXPENSES_FILE = 'expenses_data.json'


def load_expenses():
    """Load expenses from our JSON file"""
    if os.path.exists(EXPENSES_FILE):
        with open(EXPENSES_FILE, 'r') as f:
            return json.load(f)
    return []


def save_expenses(expenses):
    """Save expenses to our JSON file"""
    with open(EXPENSES_FILE, 'w') as f:
        json.dump(expenses, f, indent=2)


# Route 1: Home page - serves the HTML from templates folder
@app.route('/')
def home():
    return render_template('index.html')


# Route 2: Get all expenses
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """Get all expenses from our file"""
    expenses = load_expenses()
    return jsonify(expenses)


# Route 3: Add a new expense
@app.route('/api/expenses', methods=['POST'])
def add_expense():
    """Add a new expense to our file"""
    new_expense = request.json

    # Add ID if missing
    if 'id' not in new_expense:
        new_expense['id'] = int(datetime.now().timestamp() * 1000)

    # Load, add, save
    expenses = load_expenses()
    expenses.append(new_expense)
    save_expenses(expenses)

    return jsonify({"message": "Expense added!", "expense": new_expense}), 201


# Route 4: Delete an expense
@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense by ID"""
    expenses = load_expenses()
    expenses = [e for e in expenses if e.get('id') != expense_id]
    save_expenses(expenses)

    return jsonify({"message": "Expense deleted!"}), 200


# Route 5: Export as CSV
@app.route('/api/export/csv')
def export_csv():
    """Export all expenses as CSV"""
    import csv
    import io

    expenses = load_expenses()
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Date', 'Description', 'Category', 'Amount'])

    # Data rows
    for expense in sorted(expenses, key=lambda x: x['date'], reverse=True):
        writer.writerow([
            expense['date'],
            expense['description'],
            expense['category'],
            f"${expense['amount']:.2f}"
        ])

    csv_content = output.getvalue()

    return csv_content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=expenses.csv'
    }


if __name__ == '__main__':
    # Create templates and static folders if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    app.run(debug=True, port=5001)