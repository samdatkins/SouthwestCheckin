from __future__ import print_function

import datetime
import os.path
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly', 
          'https://www.googleapis.com/auth/drive.metadata.readonly']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1BMxNlcjawgCKpyLh2uwxHwxZhJYQsIci-9gdmroKiM8'
RANGE_NAMES = ['SAtkins!A2:D', 'DMartin!A2:D']

def get_last_modified_date(creds):
    drive_service = build('drive', 'v3', credentials=creds)
    sheet_metadata = drive_service.files().get(fileId=SPREADSHEET_ID,fields='modifiedTime').execute()
    mod_time = sheet_metadata['modifiedTime']
    return datetime.datetime.strptime(mod_time, '%Y-%m-%dT%H:%M:%S.%fZ')

def build_creds():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def get_sheet_value_rows(creds, sheet_id, ranges):
    sheets_service = build('sheets', 'v4', credentials=creds)

    values = []
    for range in RANGE_NAMES:
        # Call the Sheets API
        sheet = sheets_service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id,
                                    range=range).execute()
        new_values = result.get('values', [])

        if not new_values:
            print('No data found for ' + range)
        else:
            values.extend(new_values)
    
    return values
