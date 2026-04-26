"""run.py — Start the AI Timetable Flask server"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  AI Timetable System — SE Department")
    print("  http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)