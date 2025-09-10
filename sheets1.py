from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
from loguru import logger
from typing import List, Dict, Any
import time
from datetime import datetime


class GoogleSheetsManager:
    def __init__(self, sheet_name: str = "Mackolik Matches"):
        self.creds_file = Path("sheets_creds.json")
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self.worksheet = None
        self.last_update = None
        self.batch_size = 100  # Process in batches for better performance

    def connect(self):
        """Connect to Google Sheets with improved error handling"""
        try:
            logger.info(f"🔗 Connecting to Google Sheets: {self.sheet_name}")

            # Verify credentials file exists
            if not self.creds_file.exists():
                raise FileNotFoundError(f"Credentials file not found: {self.creds_file}")

            # Set up authentication
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            creds = Credentials.from_service_account_file(
                str(self.creds_file),
                scopes=scopes
            )
            self.client = gspread.authorize(creds)

            # Open or create the spreadsheet
            try:
                self.sheet = self.client.open(self.sheet_name)
            except gspread.SpreadsheetNotFound:
                logger.warning(f"Spreadsheet '{self.sheet_name}' not found. Creating new one...")
                self.sheet = self.client.create(self.sheet_name)
                logger.info(f"✅ Created new spreadsheet: {self.sheet_name}")

            # Get the first worksheet
            self.worksheet = self.sheet.sheet1
            self.last_update = datetime.now()

            logger.success(f"✅ Successfully connected to Google Sheets: {self.sheet_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Google Sheets: {e}")
            raise

    def setup_headers(self, headers: List[str] = None):
        """Setup column headers for the spreadsheet"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected. Call connect() first.")

        if headers is None:
            headers = [
                "League", "Date", "Teams", "Odds_1", "Odds_X", "Odds_2",
                "Additional_Odds", "Timestamp", "Status", "Last_Updated"
            ]

        try:
            # Check if headers already exist
            existing_headers = self.worksheet.row_values(1)
            if not existing_headers or existing_headers != headers:
                # Clear the first row and add headers
                self.worksheet.insert_row(headers, 1)

                # Format headers (make them bold)
                self.worksheet.format('1:1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })

                logger.info(f"📋 Headers setup: {headers}")

        except Exception as e:
            logger.error(f"❌ Error setting up headers: {e}")
            raise

    def write_row(self, values: List[Any]):
        """Write a single row to the spreadsheet"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected. Call connect() first.")

        try:
            # Add timestamp if not provided
            if len(values) < 10:  # Assuming 10 columns including timestamp
                values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            self.worksheet.append_row(values)
            logger.debug(f"📝 Row written: {values[:3]}...")  # Log first 3 values
            return True

        except Exception as e:
            logger.error(f"❌ Error writing row: {e}")
            return False

    def write_rows_batch(self, rows: List[List[Any]]):
        """Write multiple rows in batch for better performance"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected. Call connect() first.")

        if not rows:
            return True

        try:
            # Add timestamps to rows that don't have them
            processed_rows = []
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for row in rows:
                if len(row) < 10:  # Assuming 10 columns
                    row = row + [current_time]
                processed_rows.append(row)

            # Write in batches to avoid API limits
            for i in range(0, len(processed_rows), self.batch_size):
                batch = processed_rows[i:i + self.batch_size]
                self.worksheet.append_rows(batch)
                logger.debug(f"📝 Batch written: {len(batch)} rows")

                # Small delay to respect API limits
                if len(processed_rows) > self.batch_size:
                    time.sleep(0.1)

            logger.success(f"✅ Successfully wrote {len(processed_rows)} rows to sheet")
            self.last_update = datetime.now()
            return True

        except Exception as e:
            logger.error(f"❌ Error writing batch: {e}")
            return False

    def clear_sheet(self):
        """Clear all data from the sheet"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected")

        try:
            self.worksheet.clear()
            logger.info("🧹 Sheet cleared")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing sheet: {e}")
            return False

    def get_all_records(self) -> List[Dict]:
        """Get all records from the sheet as dictionaries"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected")

        try:
            records = self.worksheet.get_all_records()
            logger.info(f"📊 Retrieved {len(records)} records from sheet")
            return records
        except Exception as e:
            logger.error(f"❌ Error retrieving records: {e}")
            return []

    def update_cell(self, row: int, col: int, value: Any):
        """Update a specific cell"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected")

        try:
            self.worksheet.update_cell(row, col, value)
            logger.debug(f"📝 Cell updated: ({row}, {col}) = {value}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating cell: {e}")
            return False

    def find_duplicate_matches(self, teams: str, date: str = None) -> List[int]:
        """Find rows with duplicate match names"""
        if not self.worksheet:
            return []

        try:
            all_values = self.worksheet.get_all_values()
            duplicate_rows = []

            for i, row in enumerate(all_values[1:], start=2):  # Skip header row
                if len(row) > 2 and row[2] == teams:  # Assuming teams are in column 3
                    if date is None or (len(row) > 1 and row[1] == date):
                        duplicate_rows.append(i)

            return duplicate_rows
        except Exception as e:
            logger.error(f"❌ Error finding duplicates: {e}")
            return []

    def remove_duplicates(self):
        """Remove duplicate matches from the sheet"""
        if not self.worksheet:
            raise RuntimeError("Google Sheets not connected")

        try:
            all_values = self.worksheet.get_all_values()
            if len(all_values) <= 1:  # Only headers or empty
                return

            seen_matches = set()
            rows_to_keep = [all_values[0]]  # Keep headers
            duplicates_removed = 0

            for row in all_values[1:]:
                if len(row) > 2:
                    match_key = f"{row[0]}_{row[1]}_{row[2]}"  # League_Date_Teams
                    if match_key not in seen_matches:
                        seen_matches.add(match_key)
                        rows_to_keep.append(row)
                    else:
                        duplicates_removed += 1

            if duplicates_removed > 0:
                # Clear and rewrite the sheet
                self.worksheet.clear()
                self.worksheet.append_rows(rows_to_keep)
                logger.info(f"🧹 Removed {duplicates_removed} duplicate matches")

        except Exception as e:
            logger.error(f"❌ Error removing duplicates: {e}")

    def get_sheet_stats(self) -> Dict[str, Any]:
        """Get statistics about the current sheet"""
        if not self.worksheet:
            return {}

        try:
            all_values = self.worksheet.get_all_values()
            row_count = len(all_values) - 1 if all_values else 0  # Exclude headers

            stats = {
                'total_matches': row_count,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'sheet_name': self.sheet_name,
                'columns': len(all_values[0]) if all_values else 0
            }

            return stats
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {}
