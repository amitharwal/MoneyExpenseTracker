// Global variable to store expenses
let expenses = [];

// When the page loads, do this
document.addEventListener('DOMContentLoaded', function() {
    // Set today's date as default
    document.getElementById('date').valueAsDate = new Date();

    // Load expenses from backend
    loadExpenses();

    // Set up form submission
    document.getElementById('expense-form').addEventListener('submit', handleFormSubmit);
});

// Show success message with animation
function showSuccess(message) {
    const successEl = document.getElementById('success-message');
    const textEl = successEl.querySelector('.success-text');

    // Update message text
    textEl.textContent = message;

    // Show with animation
    successEl.style.display = 'flex';
    successEl.style.animation = 'slideInDown 0.5s ease-out';

    // Hide after 3 seconds
    setTimeout(() => {
        successEl.style.animation = 'slideOutUp 0.5s ease-out';
        setTimeout(() => {
            successEl.style.display = 'none';
        }, 500);
    }, 3000);
}

// Show/hide loading spinner
function setLoading(isLoading) {
    const loadingEl = document.getElementById('loading');
    loadingEl.style.display = isLoading ? 'block' : 'none';
}

// Load expenses from backend
async function loadExpenses() {
    setLoading(true);

    try {
        const response = await fetch('/api/expenses');
        expenses = await response.json();
        renderExpenses();
    } catch (error) {
        console.error('Error loading expenses:', error);
        alert('Failed to load expenses. Please refresh the page.');
    } finally {
        setLoading(false);
    }
}

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();

    // Get form data
    const expense = {
        date: document.getElementById('date').value,
        amount: parseFloat(document.getElementById('amount').value),
        description: document.getElementById('description').value,
        category: document.getElementById('category').value
    };

    // Add to backend
    try {
        const response = await fetch('/api/expenses', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(expense)
        });

        const result = await response.json();

        if (result.expense) {
            expenses.push(result.expense);
            renderExpenses();
            showSuccess('✅ Expense added successfully!');

            // Reset form with animation
            e.target.reset();
            document.getElementById('date').valueAsDate = new Date();

            // Animate the form
            e.target.style.animation = 'shake 0.3s ease-out';
            setTimeout(() => {
                e.target.style.animation = '';
            }, 300);
        }
    } catch (error) {
        console.error('Error adding expense:', error);
        alert('Failed to add expense. Please try again.');
    }
}

// Delete expense
async function deleteExpense(id) {
    if (!confirm('Are you sure you want to delete this expense?')) {
        return;
    }

    try {
        await fetch(`/api/expenses/${id}`, {
            method: 'DELETE'
        });

        // Remove from local array with animation
        const expenseEl = document.querySelector(`[data-expense-id="${id}"]`);
        if (expenseEl) {
            expenseEl.style.animation = 'fadeOutRight 0.5s ease-out';
            setTimeout(() => {
                expenses = expenses.filter(expense => expense.id !== id);
                renderExpenses();
                showSuccess('🗑️ Expense deleted!');
            }, 500);
        }
    } catch (error) {
        console.error('Error deleting expense:', error);
        alert('Failed to delete expense.');
    }
}

// Render expenses to the page
function renderExpenses() {
    const expenseList = document.getElementById('expense-list');
    const totalElement = document.getElementById('total');

    // Sort by date (newest first)
    const sortedExpenses = expenses.sort((a, b) => new Date(b.date) - new Date(a.date));

    if (sortedExpenses.length === 0) {
        expenseList.innerHTML = `
            <div class="empty-state">
                <h3>No expenses yet</h3>
                <p>Add your first expense to get started!</p>
            </div>
        `;
    } else {
        expenseList.innerHTML = sortedExpenses.map((expense, index) => `
            <div class="expense-item" data-expense-id="${expense.id}" 
                 style="animation-delay: ${index * 0.1}s">
                <div class="expense-details">
                    <div class="expense-date">${formatDate(expense.date)}</div>
                    <div class="expense-description">${expense.description}</div>
                    <span class="expense-category">
                        ${getCategoryEmoji(expense.category)} ${expense.category}
                    </span>
                </div>
                <div class="expense-amount">$${expense.amount.toFixed(2)}</div>
                <button class="delete-btn" onclick="deleteExpense(${expense.id})">
                    Delete
                </button>
            </div>
        `).join('');
    }

    // Calculate and animate total
    const total = expenses.reduce((sum, expense) => sum + expense.amount, 0);

    // Animate the total number
    animateValue(totalElement, 0, total, 1000);
}

// Animate number counting up
function animateValue(element, start, end, duration) {
    const range = end - start;
    const increment = range / (duration / 16); // 60 FPS
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= end) {
            current = end;
            clearInterval(timer);
        }
        element.textContent = `$${current.toFixed(2)}`;
    }, 16);
}

// Format date nicely
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

// Get emoji for category
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

// Export to CSV
async function exportToCSV() {
    try {
        const response = await fetch('/api/export/csv');
        const csvContent = await response.text();

        // Create download
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'expenses.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showSuccess('📊 Exported to CSV!');
    } catch (error) {
        alert('Failed to export CSV');
    }
}

// Export to JSON
function exportToJSON() {
    const jsonContent = JSON.stringify(expenses, null, 2);

    // Create download
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'expenses.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    showSuccess('💾 Exported to JSON!');
}

// Add shake animation to CSS dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-5px); }
        75% { transform: translateX(5px); }
    }
    
    @keyframes fadeOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
    
    @keyframes slideOutUp {
        from {
            opacity: 1;
            transform: translateY(-20px);
        }
    }
`;
document.head.appendChild(style);