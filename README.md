# OddsExtractor
Python tool that extracts betting data from a betting app (Turkish app Mackolik specifically) using OCR and logs it to Google Sheets.

FEATURES: 

Auto Window Detection: Automatically finds and targets Mackolik/BlueStacks window
Real-time OCR: Extracts team names, scores, and betting odds in real-time
Multi-site Support: Captures odds from NESINE, OLEY, MISLI, tuttur
Google Sheets Integration: Automatically organizes data in structured spreadsheet format
Turkish Language Support: Handles Turkish characters and betting terminology
Duplicate Prevention: Avoids logging the same match multiple times

REQUIREMENTS:

bashpip install paddleocr opencv-python mss gspread google-auth loguru numpy pygetwindow
Setup

Google Sheets API:

Create Google Cloud project
Enable Google Sheets API and Google Drive API
Create service account credentials
Download JSON file as sheets_creds.json


BlueStacks Setup:

Install BlueStacks emulator
Install Mackolik app
Keep window visible during operation

Output Format
Data is organized in Google Sheets with columns for:

Team names
Match scores
Odds from different betting sites
Timestamps
Processing status

Technical Details:

Uses PaddleOCR for text recognition
Window detection via pygetwindow
Real-time screen capture with MSS
Configurable processing intervals

This tool is for educational and data analysis purposes. Users are responsible for compliance with applicable terms of service and regulations.
