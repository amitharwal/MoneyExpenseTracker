from flask import Flask, request, jsonify, render_template_string
import json
import os
from datetime import datetime

# Create the Flask app - this is like opening a restaurant
app = Flask(__name__)

# This is where we'll save expenses - like a filing cabinet
EXPENSES_FILE = 'expenses_data.json'


# Helper function to load expenses from our file
def load_expenses():
    """
    This opens our filing cabinet and reads what's inside.
    If the cabinet is empty, we start with an empty list.
    """
    if os.path.exists(EXPENSES_FILE):  # Check if file exists
        with open(EXPENSES_FILE, 'r') as f:  # Open the file
            return json.load(f)  # Read the data
    return []  # If no file, return empty list


# Helper function to save expenses to our file
def save_expenses(expenses):
    """
    This saves all expenses to our filing cabinet.
    It's like writing down all expenses on paper and filing it.
    """
    with open(EXPENSES_FILE, 'w') as f:  # Open file for writing
        json.dump(expenses, f, indent=2)  # Write data nicely formatted


# Route 1: Home page - serves the HTML
@app.route('/')
def home():
    """
    When someone visits your website, show them the expense tracker.
    The '/' means the main page (like the front door).
    """
    return render_template_string(HTML_TEMPLATE)


# Route 2: Get all expenses
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """
    When the app asks "what expenses do we have?",
    we open the filing cabinet and show them all.
    GET means "get me some data"
    """
    expenses = load_expenses()  # Load from file
    return jsonify(expenses)  # Send back as JSON (JavaScript format)


# Route 3: Add a new expense
@app.route('/api/expenses', methods=['POST'])
def add_expense():
    """
    When the app says "here's a new expense to save",
    we add it to our filing cabinet.
    POST means "post/add new data"
    """
    # Get the new expense from the request
    new_expense = request.json  # This is the data sent from the frontend

    # Add an ID if it doesn't have one
    if 'id' not in new_expense:
        new_expense['id'] = int(datetime.now().timestamp() * 1000)

    # Load existing expenses
    expenses = load_expenses()

    # Add the new expense
    expenses.append(new_expense)

    # Save back to file
    save_expenses(expenses)

    # Tell the frontend "success!"
    return jsonify({"message": "Expense added!", "expense": new_expense}), 201


# Route 4: Delete an expense
@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """
    When the app says "delete expense with ID 123",
    we find it in our filing cabinet and remove it.
    <int:expense_id> means "expect a number here"
    """
    # Load expenses
    expenses = load_expenses()

    # Filter out the expense with matching ID
    expenses = [e for e in expenses if e.get('id') != expense_id]

    # Save back to file
    save_expenses(expenses)

    # Tell the frontend "deleted!"
    return jsonify({"message": "Expense deleted!"}), 200


# HTML Template with updated JavaScript to use the backend
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💰 Expense Tracker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .server-status {
            display: inline-block;
            padding: 5px 15px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 20px;
            font-size: 14px;
            margin-top: 10px;
        }

        .content {
            padding: 30px;
        }

        .add-expense {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }

        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }

        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }

        button:hover {
            transform: translateY(-2px);
        }

        .expense-list {
            margin-top: 30px;
        }

        .expense-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: transform 0.2s;
        }

        .expense-item:hover {
            transform: translateX(5px);
        }

        .expense-details {
            flex: 1;
        }

        .expense-date {
            font-size: 14px;
            color: #666;
            margin-bottom: 5px;
        }

        .expense-description {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .expense-category {
            display: inline-block;
            padding: 4px 12px;
            background: #e0e0e0;
            border-radius: 20px;
            font-size: 14px;
        }

        .expense-amount {
            font-size: 24px;
            font-weight: 700;
            color: #667eea;
            margin-right: 20px;
        }

        .delete-btn {
            background: #ff4757;
            padding: 8px 16px;
            font-size: 14px;
        }

        .total-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin-top: 30px;
        }

        .total-amount {
            font-size: 36px;
            font-weight: 700;
        }

        .empty-state {
            text-align: center;
            padding: 60px;
            color: #999;
        }

        @media (max-width: 600px) {
            .form-row {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 Expense Tracker</h1>
            <p>Full-Stack Application with Backend Storage</p>
            <div class="server-status">🟢 Connected to Backend</div>
        </div>

        <div class="content">
            <div class="add-expense">
                <h2>Add New Expense</h2>
                <form id="expense-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="date">Date</label>
                            <input type="date" id="date" required>
                        </div>
                        <div class="form-group">
                            <label for="amount">Amount ($)</label>
                            <input type="number" id="amount" step="0.01" min="0.01" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="description">Description</label>
                        <input type="text" id="description" placeholder="What did you spend on?" required>
                    </div>

                    <div class="form-group">
                        <label for="category">Category</label>
                        <select id="category" required>
                            <option value="">Select a category</option>
                            <option value="Food">🍔 Food</option>
                            <option value="Transport">🚗 Transport</option>
                            <option value="Shopping">🛍️ Shopping</option>
                            <option value="Bills">📱 Bills</option>
                            <option value="Entertainment">🎬 Entertainment</option>
                            <option value="Health">🏥 Health</option>
                            <option value="Other">📌 Other</option>
                        </select>
                    </div>

                    <button type="submit">Add Expense</button>
                </form>
            </div>

            <div class="expense-list" id="expense-list">
                <!-- Expenses will be loaded here -->
            </div>

            <div class="total-section">
                <h3>Total Spending</h3>
                <div class="total-amount" id="total">$0.00</div>
            </div>
        </div>
    </div>

    <script>
        // This is the JavaScript that talks to our backend
        let expenses = [];

        // Set today's date as default
        document.getElementById('date').valueAsDate = new Date();

        // Load expenses when page loads
        loadExpenses();

        // Function to load expenses from backend
        async function loadExpenses() {
            try {
                // Ask the backend "what expenses do we have?"
                const response = await fetch('/api/expenses');
                expenses = await response.json();
                renderExpenses();
            } catch (error) {
                console.error('Error loading expenses:', error);
            }
        }

        // Function to add expense to backend
        async function addExpenseToBackend(expense) {
            try {
                // Tell the backend "here's a new expense"
                const response = await fetch('/api/expenses', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(expense)
                });
                const result = await response.json();
                return result.expense;
            } catch (error) {
                console.error('Error adding expense:', error);
            }
        }

        // Function to delete expense from backend
        async function deleteExpenseFromBackend(id) {
            try {
                // Tell the backend "delete this expense"
                await fetch(`/api/expenses/${id}`, {
                    method: 'DELETE'
                });
            } catch (error) {
                console.error('Error deleting expense:', error);
            }
        }

        // Form submission
        document.getElementById('expense-form').addEventListener('submit', async function(e) {
            e.preventDefault();

            const expense = {
                date: document.getElementById('date').value,
                amount: parseFloat(document.getElementById('amount').value),
                description: document.getElementById('description').value,
                category: document.getElementById('category').value
            };

            // Add to backend
            const savedExpense = await addExpenseToBackend(expense);
            if (savedExpense) {
                expenses.push(savedExpense);
                renderExpenses();
            }

            // Reset form
            e.target.reset();
            document.getElementById('date').valueAsDate = new Date();
        });

        // Delete expense function
        async function deleteExpense(id) {
            if (confirm('Are you sure you want to delete this expense?')) {
                await deleteExpenseFromBackend(id);
                expenses = expenses.filter(expense => expense.id !== id);
                renderExpenses();
            }
        }

        // Render expenses function (same as before)
        function renderExpenses() {
            const expenseList = document.getElementById('expense-list');
            const totalElement = document.getElementById('total');

            const sortedExpenses = expenses.sort((a, b) => new Date(b.date) - new Date(a.date));

            if (sortedExpenses.length === 0) {
                expenseList.innerHTML = `
                    <div class="empty-state">
                        <h3>No expenses yet</h3>
                        <p>Add your first expense to get started!</p>
                    </div>
                `;
            } else {
                expenseList.innerHTML = sortedExpenses.map(expense => `
                    <div class="expense-item">
                        <div class="expense-details">
                            <div class="expense-date">${formatDate(expense.date)}</div>
                            <div class="expense-description">${expense.description}</div>
                            <span class="expense-category">${getCategoryEmoji(expense.category)} ${expense.category}</span>
                        </div>
                        <div class="expense-amount">$${expense.amount.toFixed(2)}</div>
                        <button class="delete-btn" onclick="deleteExpense(${expense.id})">Delete</button>
                    </div>
                `).join('');
            }

            const total = expenses.reduce((sum, expense) => sum + expense.amount, 0);
            totalElement.textContent = `$${total.toFixed(2)}`;
        }

        function formatDate(dateString) {
            const options = { year: 'numeric', month: 'long', day: 'numeric' };
            return new Date(dateString).toLocaleDateString(undefined, options);
        }

        function getCategoryEmoji(category) {
            const emojis = {
                'Food': '🍔',
                'Transport': '🚗',
                'Shopping': '🛍️',
                'Bills': '📱',
                'Entertainment': '🎬',
                'Health': '🏥',
                'Other': '📌'
            };
            return emojis[category] || '📌';
        }
    </script>
</body>
</html>
'''

# Start the server when this file is run
if __name__ == '__main__':
    # Run the app - like turning on the "OPEN" sign at a restaurant
    # debug=True means show helpful error messages
    # port=5000 means use door number 5000
    app.run(debug=True, port=5000)