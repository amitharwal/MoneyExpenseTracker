import tkinter as tk
from tkinter import Menu, messagebox, ttk
from database import DatabaseHandler
from summary import Summary
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import ttkbootstrap as tb


class ExpenseTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker")
        self.root.geometry("800x600")

        # Apply a modern dark theme
        self.style = tb.Style("superhero")
        self.root.configure(bg=self.style.colors.bg)

        self.db_handler = DatabaseHandler()  # Initialize the database handler
        self.summary_handler = Summary(self.db_handler.connection)  # Initialize the summary handler

        self.menubar()
        self.tabs()

    def menubar(self):
        my_menu = tk.Menu(self.root, bg=self.style.colors.primary, fg=self.style.colors.light)
        self.root.config(menu=my_menu)

        file = tk.Menu(my_menu, tearoff=0, bg=self.style.colors.primary, fg=self.style.colors.light)
        my_menu.add_cascade(label="File", menu=file)
        file.add_command(label="Export to JSON", command=self.export_to_json)
        file.add_command(label="Import from JSON", command=self.import_from_json)
        file.add_command(label="Exit", command=self.root.quit)

    def tabs(self):
        my_tab = ttk.Notebook(self.root, style="TNotebook")
        my_tab.pack(fill='both', expand=1)

        add_expense_frame = tb.Frame(my_tab)
        view_summary_frame = tb.Frame(my_tab)
        view_expenses_frame = tb.Frame(my_tab)

        add_expense_frame.pack(fill="both", expand=1)
        view_summary_frame.pack(fill="both", expand=1)
        view_expenses_frame.pack(fill="both", expand=1)

        my_tab.add(add_expense_frame, text="Add Expense")
        my_tab.add(view_summary_frame, text="View Summary")
        my_tab.add(view_expenses_frame, text="View All Expenses")

        self.configure_add_expense_tab(add_expense_frame)
        self.create_summary_view(view_summary_frame)
        self.configure_view_expenses_tab(view_expenses_frame)

    def configure_add_expense_tab(self, frame):
        tb.Label(frame, text="Date Of Expense (YYYY-MM-DD):", bootstyle="info").grid(row=0, column=0, padx=10, pady=10, sticky='e')
        self.dateEntry = tb.Entry(frame, width=30, bootstyle="info")
        self.dateEntry.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        tb.Label(frame, text="Amount Spent:", bootstyle="info").grid(row=1, column=0, padx=10, pady=10, sticky='e')
        self.amountEntry = tb.Entry(frame, width=30, bootstyle="info")
        self.amountEntry.grid(row=1, column=1, padx=10, pady=10, sticky='w')

        tb.Label(frame, text="Description:", bootstyle="info").grid(row=2, column=0, padx=10, pady=10, sticky='e')
        self.descriptionEntry = tb.Entry(frame, width=30, bootstyle="info")
        self.descriptionEntry.grid(row=2, column=1, padx=10, pady=10, sticky='w')

        tb.Label(frame, text="Category:", bootstyle="info").grid(row=3, column=0, padx=10, pady=10, sticky='e')
        categories = ["Bills", "Shopping", "Groceries", "Food", "Transportation", "Entertainment"]
        self.categorydropdown = tb.Combobox(frame, values=categories, width=28, bootstyle="info")
        self.categorydropdown.grid(row=3, column=1, padx=10, pady=10, sticky='w')

        tb.Button(frame, text='Submit', command=self.submit_expense, bootstyle="info-outline", style='Accent.TButton').grid(row=4, column=1, pady=20, sticky='w')

    def configure_view_expenses_tab(self, frame):
        self.expenses_tree = tb.Treeview(frame, columns=("ID", "Date", "Category", "Amount", "Description"), show='headings', style="info")
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

        scrollbar = tb.Scrollbar(frame, orient='vertical', command=self.expenses_tree.yview, bootstyle="info")
        self.expenses_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')

        tb.Button(frame, text='Delete Selected Expense', command=self.delete_selected_expense, bootstyle="danger-outline", style='Accent.TButton').grid(row=1, column=0, pady=10)

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.load_expenses()

    def create_summary_view(self, frame):
        summary_tab = ttk.Notebook(frame, style="TNotebook")
        summary_tab.pack(fill='both', expand=1)

        daily_summary_frame = tb.Frame(summary_tab)
        monthly_summary_frame = tb.Frame(summary_tab)
        category_summary_frame = tb.Frame(summary_tab)

        daily_summary_frame.pack(fill='both', expand=1)
        monthly_summary_frame.pack(fill='both', expand=1)
        category_summary_frame.pack(fill='both', expand=1)

        summary_tab.add(daily_summary_frame, text="Daily Summary")
        summary_tab.add(monthly_summary_frame, text="Monthly Summary")
        summary_tab.add(category_summary_frame, text="Category Summary")

        self.daily_summary_text = tk.Text(daily_summary_frame, height=15, wrap='word', bg=self.style.colors.inputbg, fg=self.style.colors.inputfg)
        self.daily_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        daily_plot_button = tb.Button(daily_summary_frame, text="Plot Daily Summary", command=self.plot_daily_summary, bootstyle="info-outline", style='Accent.TButton')
        daily_plot_button.pack(pady=10)

        self.monthly_summary_text = tk.Text(monthly_summary_frame, height=15, wrap='word', bg=self.style.colors.inputbg, fg=self.style.colors.inputfg)
        self.monthly_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        monthly_plot_button = tb.Button(monthly_summary_frame, text="Plot Monthly Summary", command=self.plot_monthly_summary, bootstyle="info-outline", style='Accent.TButton')
        monthly_plot_button.pack(pady=10)

        self.category_summary_text = tk.Text(category_summary_frame, height=15, wrap='word', bg=self.style.colors.inputbg, fg=self.style.colors.inputfg)
        self.category_summary_text.pack(fill='both', expand=1, padx=10, pady=10)
        category_plot_button = tb.Button(category_summary_frame, text="Plot Category Summary", command=self.plot_category_summary, bootstyle="info-outline", style='Accent.TButton')
        category_plot_button.pack(pady=10)

        self.load_summaries()

    def load_summaries(self):
        daily_summary = self.summary_handler.get_daily_summary()
        self.daily_summary_text.delete(1.0, tk.END)
        for date, total in daily_summary:
            self.daily_summary_text.insert(tk.END, f"{date}: ${total:.2f}\n")

        monthly_summary = self.summary_handler.get_monthly_summary()
        self.monthly_summary_text.delete(1.0, tk.END)
        for month, total in monthly_summary:
            self.monthly_summary_text.insert(tk.END, f"{month}: ${total:.2f}\n")

        category_summary = self.summary_handler.get_category_summary()
        self.category_summary_text.delete(1.0, tk.END)
        for category, total in category_summary:
            self.category_summary_text.insert(tk.END, f"{category}: ${total:.2f}\n")

    def plot_daily_summary(self):
        figure = self.summary_handler.get_daily_summary_plot()
        self.embed_plot(figure)

    def plot_monthly_summary(self):
        figure = self.summary_handler.get_monthly_summary_plot()
        self.embed_plot(figure)

    def plot_category_summary(self):
        figure = self.summary_handler.get_category_summary_plot()
        self.embed_plot(figure)

    def embed_plot(self, figure):
        plot_window = tb.Toplevel(self.root)
        plot_window.title("Summary Plot")
        plot_window.geometry("800x600")
        canvas = FigureCanvasTkAgg(figure, plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=1)
        canvas._tkcanvas.pack(fill='both', expand=1)

    def load_expenses(self):
        expenses = self.db_handler.read_expenses()
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)
        for expense in expenses:
            self.expenses_tree.insert('', 'end', values=expense)

    def submit_expense(self):
        date = self.dateEntry.get()
        amount = self.amountEntry.get()
        description = self.descriptionEntry.get()
        category = self.categorydropdown.get()

        try:
            if not date or not amount or not category:
                raise ValueError("All fields except description must be filled out.")
            amount = float(amount)
            self.db_handler.create_expense(date, category, amount, description)
            self.dateEntry.delete(0, tk.END)
            self.amountEntry.delete(0, tk.END)
            self.descriptionEntry.delete(0, tk.END)
            self.categorydropdown.set('')
            self.load_expenses()
            self.load_summaries()
            messagebox.showinfo("Success", "Expense submitted successfully.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def delete_selected_expense(self):
        selected_item = self.expenses_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an expense to delete.")
            return
        expense_id = self.expenses_tree.item(selected_item)['values'][0]
        self.db_handler.delete_expense(expense_id)
        self.load_expenses()
        self.load_summaries()
        messagebox.showinfo("Success", "Expense deleted successfully.")

    def export_to_json(self):
        try:
            self.db_handler.export_to_json()
            messagebox.showinfo("Success", "Data exported to expenses.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")

    def import_from_json(self):
        try:
            self.db_handler.import_from_json()
            self.load_expenses()
            self.load_summaries()
            messagebox.showinfo("Success", "Data imported from expenses.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import data: {str(e)}")


if __name__ == "__main__":
    root = tb.Window(themename="superhero")
    app = ExpenseTracker(root)
    root.mainloop()
