import mss
import numpy as np
import cv2
from paddleocr import PaddleOCR
from sheets import GoogleSheetsManager
import re
import time
from datetime import datetime
from typing import Dict, List, Optional


class FlexibleTurkishParser:
    def __init__(self):
        self.current_teams = None
        self.current_ht_score = None
        self.current_ft_score = None
        self.all_odds = {}
        self.processed_matches = set()

    def clean_text(self, text: str) -> str:
        """Clean text"""
        return re.sub(r'\s+', ' ', text.strip())

    def is_team_match(self, line: str) -> bool:
        """Detect team names - catch ANY possible team name"""
        line = line.strip()


        if len(line) < 3:
            return False


        if re.match(r'^[\d\-\s:\.,%]+$', line):
            return False


        skip_terms = [
            'Detay', 'Kadro', 'Anlatim', 'İstatistik', 'Karşılaştırma', 'İddaa', 'Forum',
            'Quick search', 'NESINE', 'OLEY', 'MISLI', 'tuttur', 'BILYONER',
            'ALT/UST', 'Alt/Ust', 'SONUC', 'SANS', 'HANDICAP', 'Var', 'Yok',
            'Evet', 'Hayir', 'PEN', 'mackolik', 'Gol', 'Karşılıklı'
        ]

        if any(term.upper() in line.upper() for term in skip_terms):
            return False


        if not any(c.isalpha() for c in line):
            return False


        common_words = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']
        if line.upper() in common_words:
            return False


        words = line.split()


        if len(words) == 1:
            word = words[0]
            # Must be at least 4 characters and contain mostly letters
            if len(word) >= 4:
                letter_count = sum(1 for c in word if c.isalpha())
                if letter_count >= len(word) * 0.7:  # 70% letters
                    return True


        elif 2 <= len(words) <= 5:
            # Check if it's mostly letters across all words
            total_chars = len(line.replace(' ', '').replace('.', ''))
            letter_count = sum(1 for c in line if c.isalpha())

            if letter_count >= total_chars * 0.6:  # 60% letters
                return True

        return False

    def is_score(self, line: str) -> bool:
        """Detect if line is a score like '1-0', '2-1', etc."""
        line = line.strip()


        score_patterns = [
            r'^\d+\s*-\s*\d+$',  # 1-0, 2-1
            r'^\(\d+\-\d+\)$',  # (1-0)
            r'^\d+\:\d+$',  # 1:0 format
            r'HT\s*\d+\-\d+',  # HT 1-0
            r'FT\s*\d+\-\d+',  # FT 1-0
        ]

        for pattern in score_patterns:
            if re.search(pattern, line):
                return True

        return False

    def is_odds_value(self, line: str) -> bool:
        """Detect if line looks like betting odds"""
        line = line.strip()

        if re.match(r'^\d{1,2}[,\.]\d{2}$', line):
            try:
                odds_val = float(line.replace(',', '.'))
                return 1.01 <= odds_val <= 100.0
            except:
                return False
        return False

    def find_hidden_score(self, ocr_lines: List[str]) -> str:
        """Look for score that might be misread by OCR"""

        for line in ocr_lines:
            line = self.clean_text(line)


            potential_scores = [
                r'[IO1l|]\s*[-\-−‒–—]\s*[O0oQ]',  # 1-0 variations (I-O, l-0, etc)
                r'[IO1l|]\s*[-\-−‒–—]\s*[IO1l|]',  # 1-1 variations
                r'[2zZ]\s*[-\-−‒–—]\s*[O0oQ]',  # 2-0 variations
                r'[2zZ]\s*[-\-−‒–—]\s*[IO1l|]',  # 2-1 variations
                r'[3Ɛ]\s*[-\-−‒–—]\s*[O0oQ]',  # 3-0 variations
            ]

            for pattern in potential_scores:
                if re.search(pattern, line, re.IGNORECASE):

                    normalized = line.replace('I', '1').replace('l', '1').replace('|', '1')
                    normalized = normalized.replace('O', '0').replace('o', '0').replace('Q', '0')
                    normalized = re.sub(r'[-\-−‒–—]', '-', normalized)


                    score_match = re.search(r'(\d\s*-\s*\d)', normalized)
                    if score_match:
                        return score_match.group(1).replace(' ', '')

        return None

    def extract_all_data(self, ocr_lines: List[str]) -> Dict:
        data = {
            'teams': None,
            'ht_score': None,
            'ft_score': None,
            'odds': [],
            'all_text': []
        }

        print(f"\n=== ALL OCR TEXT ===")

        team_candidates = []

        for i, line in enumerate(ocr_lines):
            line = self.clean_text(line)
            if len(line) < 1:
                continue

            data['all_text'].append(line)
            print(f"{i:3d}: '{line}'")


            if any(c.isdigit() for c in line) and any(c in line for c in ['-', '‒', '–', '—']):
                print(f"     → 🔍 POTENTIAL HIDDEN SCORE")


            if re.match(r'^\d{1,2}[,\.]\d{2}$', line):
                data['odds'].append(line)


            if (len(line) >= 3 and
                    not re.match(r'^[\d\-\s:\.,%]+$', line) and
                    line.upper() not in ['DETAY', 'KADRO', 'ISTATISTIK', 'IDDAA', 'FORUM', 'MACKOLIK', 'MS'] and
                    not any(
                        site in line.upper() for site in ['NESINE', 'NESTNE', 'OLEY', 'MISLI', 'MMISLI', 'TUTTUR']) and
                    not any(ui in line.upper() for ui in ['EV', 'DEP', 'DCP', 'SONUCU', 'YARI', 'TOPLAM', 'ROOTED'])):
                team_candidates.append(line)


        hidden_score = self.find_hidden_score(data['all_text'])
        if hidden_score:
            data['ft_score'] = hidden_score
            print(f"Found hidden score: {hidden_score}")
        else:
            data['ft_score'] = "0-0"


        if len(team_candidates) >= 2:
            data['teams'] = f"{team_candidates[0]} - {team_candidates[1]}"
        elif len(team_candidates) >= 1:
            data['teams'] = team_candidates[0]

        print(f"\nTeam candidates: {team_candidates}")
        print(f"Selected teams: {data['teams']}")
        print(f"Score: {data['ft_score']}")
        print(f"Odds found: {len(data['odds'])}")

        return data

    def create_flexible_row(self, data: Dict) -> List:
        """Create Google Sheets row from extracted data"""


        odds = [odd.replace(',', '.') for odd in data['odds']]


        while len(odds) < 15:
            odds.append('0')


        teams_info = data['teams']
        if not teams_info:
            if data['categories']:
                teams_info = f"Data from: {' | '.join(data['categories'][:2])}"
            elif data['betting_sites']:
                teams_info = f"Betting data: {' | '.join(data['betting_sites'][:2])}"
            else:
                teams_info = f"Odds data {datetime.now().strftime('%H:%M:%S')}"


        row = [
            # A:
            teams_info,

            # B:
            data['ht_score'] or "0-0",

            # C: )
            data['ft_score'] or "0-0",

            # D
            odds[0],  # D: Maç Sonucu 1
            odds[1],  # E: Maç Sonucu X
            odds[2],  # F: Maç Sonucu 2
            odds[3],  # G: Çifte Şans 1-X
            odds[4],  # H: Çifte Şans 1-2
            odds[5],  # I: Çifte Şans X-2
            odds[6],  # J: Handicap 1
            odds[7],  # K: Handicap X
            odds[8],  # L: Handicap 2
            odds[9],  # M: Handicap 2 1
            odds[10],  # N: Handicap 2 X
            odds[11],  # O: Handicap 2 2
            odds[12],  # Additional odds 1
            odds[13],  # Additional odds 2
            odds[14],  # Additional odds 3

            # P-Q: Metadata
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"Active - {len(data['odds'])} odds found"
        ]

        return row


class FlexibleSheetsManager:
    def __init__(self, sheet_name: str = "Mackolik Matches"):
        self.sheets = GoogleSheetsManager(sheet_name)
        self.headers_written = False

    def connect(self):
        return self.sheets.connect()

    def ensure_headers(self):
        """Add Turkish headers"""
        if not self.headers_written:
            headers = [
                "Takimlar",  # A: Teams
                "Ilk Yari Skoru",  # B: Halftime Score
                "Maç Sonucu Skoru",  # C: Full Score
                "Maç Sonucu 1",  # D: Match Result 1
                "Maç Sonucu X",  # E: Match Result X
                "Maç Sonucu 2",  # F: Match Result 2
                "Çifte Şans 1-X",  # G: Double Chance 1-X
                "Çifte Şans 1-2",  # H: Double Chance 1-2
                "Çifte Şans X-2",  # I: Double Chance X-2
                "Hnd. MS (1:0) 1",  # J: Handicap (1:0) 1
                "Hnd MS (1:0) X",  # K: Handicap (1:0) X
                "Hnd. MS (1:0) 2",  # L: Handicap (1:0) 2
                "Hnd. MS (2:0) 1",  # M: Handicap (2:0) 1
                "Hnd. MS (2:0) X",  # N: Handicap (2:0) X
                "Hnd. MS (2:0) 2",  # O: Handicap (2:0) 2
                "Timestamp",  # P: When captured
                "Status"  # Q: Status
            ]

            try:
                print("🧹 Adding separator and Turkish headers...")
                self.sheets.write_row(["=== FLEXIBLE TURKISH PARSER ==="])
                self.sheets.write_row(headers)
                self.headers_written = True
                print("📋 Turkish headers added!")
            except Exception as e:
                print(f"❌ Header error: {e}")

    def write_data(self, data_row: List):
        """Write the extracted data"""
        self.ensure_headers()

        try:
            self.sheets.write_row(data_row)
            print(f"✅ Data written: {data_row[0]} | {data_row[1]} | {data_row[2]}")
            return True
        except Exception as e:
            print(f"❌ Write error: {e}")
            return False


def main():
    print("🔥 FLEXIBLE TURKISH PARSER - READS EVERYTHING!")
    print("=" * 60)

    # Initialize
    sheets_manager = FlexibleSheetsManager("Mackolik Matches")
    sheets_manager.connect()

    ocr = PaddleOCR(lang='en', use_gpu=False)
    parser = FlexibleTurkishParser()

    # Capture settings
    monitor = {"top": 100, "left": 200, "width": 500, "height": 800}

    last_process_time = 0
    process_interval = 10  # Every 10 seconds

    print(f"📱 Monitoring: {monitor}")
    print(f"⏱️ Processing every: {process_interval} seconds")
    print("Press 'q' to quit, 's' to process now")
    print("=" * 60)

    with mss.mss() as sct:
        while True:

            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            cv2.imshow("Flexible Turkish Parser", img)


            current_time = time.time()
            if current_time - last_process_time >= process_interval:
                print(f"\n🔍 PROCESSING EVERYTHING ON SCREEN... {datetime.now().strftime('%H:%M:%S')}")

                try:
                    # Run OCR
                    results = ocr.ocr(img)
                    if results and results[0]:
                        ocr_lines = [line[1][0] for line in results[0] if line[1][0].strip()]
                        print(f"📝 OCR found {len(ocr_lines)} text lines")


                        extracted_data = parser.extract_all_data(ocr_lines)


                        if extracted_data['teams'] or len(extracted_data['odds']) >= 3:
                            data_row = parser.create_flexible_row(extracted_data)


                            odds_summary = ''.join(extracted_data['odds'][:5])
                            timestamp = datetime.now().strftime("%H%M%S")
                            data_id = f"{extracted_data['teams']}_{extracted_data['ft_score']}_{odds_summary}_{timestamp}"


                            if len(extracted_data['odds']) >= 3:
                                success = sheets_manager.write_data(data_row)
                                if success:
                                    print(f"🎉 NEW ODDS DATA CAPTURED AND SAVED!")
                                    parser.processed_matches.add(data_id)
                                else:
                                    print(f"❌ Failed to save data")
                            else:
                                print(
                                    f"⏳ Not enough odds data found (need at least 3, found {len(extracted_data['odds'])})")
                        else:
                            print(f"⏳ No meaningful data found on screen")
                    else:
                        print("❌ OCR found no text")

                except KeyboardInterrupt:
                    print("\n⏸️ Interrupted by user")
                    break
                except Exception as e:
                    print(f"❌ Processing error: {e}")
                    import traceback
                    traceback.print_exc()

                last_process_time = current_time


            key = cv2.waitKey(100) & 0xFF
            if key == ord('q'):
                print("\n👋 Quitting...")
                break
            elif key == ord('s'):
                print("\n💾 Manual processing...")
                last_process_time = 0

    cv2.destroyAllWindows()
    print("✅ Flexible parser ended!")


if __name__ == "__main__":
    main()