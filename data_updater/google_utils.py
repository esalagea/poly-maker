from google.oauth2.service_account import Credentials
import gspread
import os


def get_spreadsheet():
    """Get the main Google Spreadsheet using credentials and URL from environment variables"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    credentials = Credentials.from_service_account_file('credentials.json', scopes=scope)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_url(os.getenv("SPREADSHEET_URL"))
    return spreadsheet