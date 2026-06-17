import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds_path = "credenciais.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

about = drive_service.about().get(fields="storageQuota, user").execute()
print(json.dumps(about, indent=2))
