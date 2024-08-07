import tkinter as tk
from tkinter import Menu, messagebox, ttk
from database import DatabaseHandler
from summary import Summary
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


class ExpenseTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker")
        self.root.geometry("800x600")

        # Apply a modern theme
        style = ttk.Style(self.root)
        style.theme_use('clam')

        # Configure styles
        style.configure('TLabel', font=('Arial', 12), padding=10)
        style.configure('TButton', font=('Arial', 12), padding=5)
        style.configure('TEntry', padding=5)
        style.configure('Treeview.Heading', font=('Arial', 12, 'bold'))
        style.configure('Treeview', font=('Arial', 10))

        self.db_handler = DatabaseHandler()  # Initialize the database handler
        self.summary_handler = Summary(self.db_handler.connection)  # Initialize the summary handler

        self.menubar()
        self.tabs()

    def menubar(self):
        my_menu = Menu(self.root)
        self.root.config(menu=my_menu)

        file = Menu(my_menu, tearoff=0)
        my_menu.add_cascade(label="File", menu=file)
        file.add_command(label="Export to JSON", command=self.export_to_json)
        file.add_command(label="Import from JSON", command=self.import_from_json)
        file.add_command(label="Exit", command=self.root.quit)

    def tabs(self):
        my_tab = ttk.Notebook(self.root)
        my_tab.pack(fill='both', expand=1)

        # Create frames for each tab
        add_expense_frame = ttk.Frame(my_tab, width=800, height=600)
        view_summary_frame = ttk.Frame(my_tab, width=800, height=600)
        view_expenses_frame = ttk.Frame(my_tab, width=800, height=600)

        add_expense_frame.pack(fill="both", expand=1)
        view_summary_frame.pack(fill="both", expand=1)
        view_expenses_frame.pack(fill="both", expand=1)

        # Add frames to notebook as tabs
        my_tab.add(add_expense_frame, text="Add Expense")
        my_tab.add(view_summary_frame, text="View Summary")
        my_tab.add(view_expenses_frame, text="View All Expenses")

        # Configure Add Expense Tab
        self.configure_add_expense_tab(add_expense_frame)

        # Configure View Summary Tab
        self.create_summary_view(view_summary_frame)

        # Configure View All Expenses Tab
        self.configure_view_expenses_tab(view_expenses_frame)

    def configure_add_expense_tab(self, frame):
        # Configure Add Expense Tab
        ttk.Label(frame, text="Date Of Expense (YYYY-MM-DD):").grid(row=0, column=0, padx=10, pady=10, sticky='e')
        self.dateEntry = ttk.Entry(frame, width=30)
        self.dateEntry.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(frame, text="Amount Spent:").grid(row=1, column=0, padx=10, pady=10, sticky='e')
        self.amountEntry = ttk.Entry(frame, width=30)
        self.amountEntry.grid(row=1, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(frame, text="Description:").grid(row=2, column=0, padx=10, pady=10, sticky='e')
        self.descriptionEntry = ttk.Entry(frame, width=30)
        self.descriptionEntry.grid(row=2, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(frame, text="Category:").grid(row=3, column=0, padx=10, pady=10, sticky='e')
        categories = ["Bills", "Shopping", "Groceries", "Food", "Transportation", "Entertainment"]
        self.categorydropdown = ttk.Combobox(frame, values=categories, width=28)
        self.categorydropdown.grid(row=3, column=1, padx=10, pady=10, sticky='w')

        ttk.Button(frame, text='Submit', command=self.submit_expense).grid(row=4, column=1, pady=20, sticky='w')

    def configure_view_expenses_tab(self, frame):
        # Configure View All Expenses Tab
        self.expenses_tree = ttk.Treeview(frame, columns=("ID", "Date", "Category", "Amount", "Description"),
                                          show='headings')
        self.expenses_tree.heading("ID", text="ID")
        self.expenses_tree.heading("Date", text="Date")
        self.expenses_tree.heading("Category", text="Category")
        self.expenses_tree.heading("Amount", text="Amount")
        self.expenses_tree.heading("Description", text="Description")
        self.expenses_tree.column("ID", anchor='center', width=50)
        self.expenses_tree.column("Date", anchor='center', width=150)
        self.expenses_tree.column("Category", anchor='center', width=100)
        self.expenses_tree.column("Amount", anchor='center', width=100)
        self.expenses_tree.column("Description", anchor='center', width=200)
        self.expenses_tree.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.load_expenses()  # Load expenses into the treeview

    def create_summary_view(self, frame):
        # Create tab view for summaries
        summary_tab = ttk.Notebook(frame)
        summary_tab.pack(fill='both', expand=1)

        daily_summary_frame = ttk.Frame(summary_tab)
        monthly_summary_frame = ttk.Frame(summary_tab)
        category_summary_frame = ttk.Frame(summary_tab)

        daily_summary_frame.pack(fill='both', expand=1)
        monthly_summary_frame.pack(fill='both', expand=1)
        category_summary_frame.pack(fill='both', expand=1)

        summary_tab.add(daily_summary_frame, text="Daily Summary")
        summary_tab.add(monthly_summary_frame, text="Monthly Summary")
        summary_tab.add(category_summary_frame, text="Category Summary")

        # Daily Summary
        self.daily_summary_text = tk.Text(daily_summary_frame, height=15, wrap='word')
        self.daily_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        daily_plot_button = ttk.Button(daily_summary_frame, text="Plot Daily Summary",
                                       command=self.plot_daily_summary)
        daily_plot_button.pack(pady=10)

        # Monthly Summary
        self.monthly_summary_text = tk.Text(monthly_summary_frame, height=15, wrap='word')
        self.monthly_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        monthly_plot_button = ttk.Button(monthly_summary_frame, text="Plot Monthly Summary",
                                         command=self.plot_monthly_summary)
        monthly_plot_button.pack(pady=10)

        # Category Summary
        self.category_summary_text = tk.Text(category_summary_frame, height=15, wrap='word')
        self.category_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        category_plot_button = ttk.Button(category_summary_frame, text="Plot Category Summary",
                                          command=self.plot_category_summary)
        category_plot_button.pack(pady=10)

        # Load summaries
        self.load_summaries()

    def load_summaries(self):
        # Load daily summary
        daily_summary = self.summary_handler.get_daily_summary()
        self.daily_summary_text.delete(1.0, tk.END)
        for date, total in daily_summary:
            self.daily_summary_text.insert(tk.END, f"{date}: ${total:.2f}\n")

        # Load monthly summary
        monthly_summary = self.summary_handler.get_monthly_summary()
        self.monthly_summary_text.delete(1.0, tk.END)
        for month, total in monthly_summary:
            self.monthly_summary_text.insert(tk.END, f"{month}: ${total:.2f}\n")

        # Load category summary
        category_summary = self.summary_handler.get_category_summary()
        self.category_summary_text.delete(1.0, tk.END)
        for category, total in category_summary:
            self.category_summary_text.insert(tk.END, f"{category}: ${total:.2f}\n")

    def plot_daily_summary(self):
        # Embed daily summary plot in the app
        figure = self.summary_handler.get_daily_summary_plot()
        self.embed_plot(figure)

    def plot_monthly_summary(self):
        # Embed monthly summary plot in the app
        figure = self.summary_handler.get_monthly_summary_plot()
        self.embed_plot(figure)

    def plot_category_summary(self):
        # Embed category summary plot in the app
        figure = self.summary_handler.get_category_summary_plot()
        self.embed_plot(figure)

    def embed_plot(self, figure):
        plot_window = tk.Toplevel(self.root)
        plot_window.title("Summary Plot")
        plot_window.geometry("800x600")
        canvas = FigureCanvasTkAgg(figure, plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=1)
        canvas._tkcanvas.pack(fill='both', expand=1)

    def load_expenses(self):
        # Fetch all expenses from the database
        expenses = self.db_handler.read_expenses()

        # Clear existing data
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)

        # Insert data into treeview
        for expense in expenses:
            self.expenses_tree.insert('', 'end', values=expense)

    def submit_expense(self):
        date = self.dateEntry.get()
        amount = self.amountEntry.get()
        description = self.descriptionEntry.get()
        category = self.categorydropdown.get()

        try:
            # Validate input data
            if not date or not amount or not category:
                raise ValueError("All fields except description must be filled out.")
            # Ensure amount is a valid number
            amount = float(amount)

            # Insert the expense into the database
            self.db_handler.create_expense(date, category, amount, description)

            # Clear the form fields
            self.dateEntry.delete(0, tk.END)
            self.amountEntry.delete(0, tk.END)
            self.descriptionEntry.delete(0, tk.END)
            self.categorydropdown.set('')

            # Reload expenses in the treeview
            self.load_expenses()

            # Reload summaries
            self.load_summaries()

            messagebox.showinfo("Success", "Expense submitted successfully.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def export_to_json(self):
        try:
            self.db_handler.export_to_json()
            messagebox.showinfo("Success", "Data exported to expenses.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")

    def import_from_json(self):
        try:
            self.db_handler.import_from_json()
            messagebox.showinfo("Success", "Data imported from expenses.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import data: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ExpenseTracker(root)
    root.mainloop()
