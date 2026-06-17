import json
from google.oauth2.credentials import Credentials
import gspread

with open("token.json", "r") as token:
    creds = Credentials.from_authorized_user_info(json.load(token))

client = gspread.authorize(creds)
sheet = client.open_by_key("16mc0DiY_T4XXVXHuKi_ui82lbvDVAamtnTUt3mGWqQU").sheet1
print(f"Total rows: {sheet.row_count}")
all_vals = sheet.get_all_values()
print(f"Non-empty rows: {len(all_vals)}")
for i, r in enumerate(all_vals[-5:]):  # print last 5 non-empty rows
    print(f"Row {len(all_vals) - 5 + i}: {r}")
