import json
import pyperclip
from expense_backend import ExpenseManager


def sync_from_web():
    """
    To use this:
    1. Open the web app in your browser
    2. Open browser console (F12)
    3. Type: copy(localStorage.getItem('expenses'))
    4. Run this script
    """
    print("\n" + "=" * 50)
    print("SYNC FROM WEB APP")
    print("=" * 50)
    print("\nInstructions:")
    print("1. Open the expense tracker in your browser")
    print("2. Press F12 to open developer console")
    print("3. In the console, type: copy(localStorage.getItem('expenses'))")
    print("4. Press Enter (this copies your expenses to clipboard)")
    print("5. Come back here and press Enter to continue...")

    input("\nPress Enter when you've copied the data...")

    try:
        # Get data from clipboard
        json_data = pyperclip.paste()

        # Load into manager
        manager = ExpenseManager()
        manager.load_expenses(json_data)

        print(f"\n✅ Successfully loaded {len(manager.expenses)} expenses!")

        # Show options
        print("\nWhat would you like to do?")
        print("1. Export to CSV")
        print("2. View summary")
        print("3. View monthly breakdown")
        print("4. Save to file")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice == '1':
            manager.export_to_csv()
        elif choice == '2':
            print(manager.get_summary())
        elif choice == '3':
            print(manager.get_monthly_summary())
        elif choice == '4':
            manager.save_expenses()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you copied the data from the browser console!")


if __name__ == "__main__":
    sync_from_web()