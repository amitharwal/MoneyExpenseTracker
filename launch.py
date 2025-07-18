import webbrowser
import os

# Open the HTML file in the default browser
file_path = os.path.abspath('templates/index.html')
webbrowser.open(f'file://{file_path}')

print("✅ Expense Tracker opened in your browser!")
print("💡 The app saves data automatically in your browser")
print("📊 Use the Export buttons to save your data")