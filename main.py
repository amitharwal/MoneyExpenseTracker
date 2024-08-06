import tkinter as tk
from tkinter import Menu, Toplevel, messagebox
from tkinter import ttk
from database import DatabaseHandler
from summary import Summary


class ExpenseTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker")
        self.root.geometry("600x400")
        self.db_handler = DatabaseHandler()  # Initialize the database handler
        self.menubar()
        self.tabs()
        self.summary_handler = Summary(self.db_handler.connection)  # Initialize the summary handler

    def menubar(self):
        my_menu = Menu(self.root)
        self.root.config(menu=my_menu)
        file = Menu(my_menu)
        my_menu.add_cascade(label="File", menu=file)
        file.add_command(label="Export to JSON", command=self.export_to_json)
        file.add_command(label="Import from JSON", command=self.import_from_json)
        file.add_command(label="Exit", command=self.root.quit)

        view = Menu(my_menu)  # Create view menu
        my_menu.add_cascade(label="View", menu=view)
        view.add_command(label="Daily Summary", command=self.daily_summary)
        view.add_command(label="Monthly Summary", command=self.monthly_summary)
        view.add_command(label="Category Summary", command=self.category_summary)  # Add category summary view

    def tabs(self):
        my_tab = ttk.Notebook(self.root)
        my_tab.pack(fill='both', expand=1)
        screen1 = ttk.Frame(my_tab, width=600, height=400)
        screen2 = ttk.Frame(my_tab, width=600, height=400)
        screen1.pack(fill="both", expand=1)
        screen2.pack(fill="both", expand=1)
        my_tab.add(screen1, text="Add Expense")
        my_tab.add(screen2, text="View Summary")

        # ADD EXPENSE TAB (screen1)

        # Date Entry
        self.dateEntry = ttk.Entry(screen1)
        self.dateEntry.grid(row=0, column=1, padx=5, pady=5)
        dateEntrylabel = ttk.Label(screen1, text="Date Of Expense (YYYY-MM-DD):")
        dateEntrylabel.grid(row=0, column=0, padx=5, pady=5)

        # Amount Entry
        self.amountEntry = ttk.Entry(screen1)
        self.amountEntry.grid(row=1, column=1, padx=5, pady=5)
        amountEntrylabel = ttk.Label(screen1, text="Amount Spent:")
        amountEntrylabel.grid(row=1, column=0, padx=5, pady=5)

        # Description Entry
        self.descriptionEntry = ttk.Entry(screen1)
        self.descriptionEntry.grid(row=2, column=1, padx=5, pady=5)
        descriptionEntrylabel = ttk.Label(screen1, text="Description:")
        descriptionEntrylabel.grid(row=2, column=0, padx=5, pady=5)

        # Categories dropdown
        categories = ["Bills", "Shopping", "Groceries", "Food", "Transportation", "Entertainment"]
        category = ttk.Label(screen1, text="Category:")
        category.grid(row=3, column=0, pady=5)
        self.categorydropdown = ttk.Combobox(screen1, values=categories)
        self.categorydropdown.grid(row=3, column=1, pady=5)

        # Submission button
        button = ttk.Button(screen1, text='Submit', command=self.submit_expense)
        button.grid(row=4, column=1, pady=10)

        # VIEW SUMMARY TAB (screen2)

        viewSummaryLabel = ttk.Label(screen2, text="Summary of Expenses", font=('Times', 18, 'bold'))
        viewSummaryLabel.grid(row=0, column=0, padx=5, pady=5)
        placeholder_label = ttk.Label(screen2, text="Use the 'View' menu to see summaries")
        placeholder_label.grid(row=1, column=0, padx=5, pady=5)

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

    def daily_summary(self):
        daily_summary = self.summary_handler.get_daily_summary()

        # Create a new window for displaying daily summary
        screen3 = Toplevel(self.root)
        screen3.title("Daily Summary")
        screen3.geometry("600x400")
        screen3_label = ttk.Label(screen3, text="Daily Summary", font=('Times', 18, 'bold'))
        screen3_label.grid(row=0, column=0, padx=5, pady=5)

        row_num = 1
        for date, total in daily_summary:
            summary_label = ttk.Label(screen3, text=f"{date}: ${total:.2f}")
            summary_label.grid(row=row_num, column=0, padx=5, pady=5)
            row_num += 1

        # Add button to plot daily summary
        plot_button = ttk.Button(screen3, text="Plot Daily Summary", command=self.summary_handler.plot_daily_summary)
        plot_button.grid(row=row_num, column=0, padx=5, pady=5)

    def monthly_summary(self):
        monthly_summary = self.summary_handler.get_monthly_summary()

        # Create a new window for displaying monthly summary
        screen4 = Toplevel(self.root)
        screen4.title("Monthly Summary")
        screen4.geometry("600x400")
        screen4_label = ttk.Label(screen4, text="Monthly Summary", font=('Times', 18, 'bold'))
        screen4_label.grid(row=0, column=0, padx=5, pady=5)

        row_num = 1
        for month, total in monthly_summary:
            summary_label = ttk.Label(screen4, text=f"{month}: ${total:.2f}")
            summary_label.grid(row=row_num, column=0, padx=5, pady=5)
            row_num += 1

        # Add button to plot monthly summary
        plot_button = ttk.Button(screen4, text="Plot Monthly Summary", command=self.summary_handler.plot_monthly_summary)
        plot_button.grid(row=row_num, column=0, padx=5, pady=5)

    def category_summary(self):
        category_summary = self.summary_handler.get_category_summary()

        # Create a new window for displaying category summary
        screen5 = Toplevel(self.root)
        screen5.title("Category Summary")
        screen5.geometry("600x400")
        screen5_label = ttk.Label(screen5, text="Category Summary", font=('Times', 18, 'bold'))
        screen5_label.grid(row=0, column=0, padx=5, pady=5)

        row_num = 1
        for category, total in category_summary:
            summary_label = ttk.Label(screen5, text=f"{category}: ${total:.2f}")
            summary_label.grid(row=row_num, column=0, padx=5, pady=5)
            row_num += 1

        # Add button to plot category summary
        plot_button = ttk.Button(screen5, text="Plot Category Summary", command=self.summary_handler.plot_category_summary)
        plot_button.grid(row=row_num, column=0, padx=5, pady=5)


if __name__ == "__main__":
    root = tk.Tk()
    app = ExpenseTracker(root)
    root.mainloop()
