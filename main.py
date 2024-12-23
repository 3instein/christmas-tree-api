from fastapi import FastAPI, HTTPException, Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


app = FastAPI()

# Define the scopes for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Path to your Google credentials JSON file
CREDENTIALS_FILE = "credentials.json"

# In-memory token storage (replace with persistent storage for production)
token_storage = {}


@app.get("/")
def root():
    return {"message": "Google Drive API Integration with FastAPI"}


@app.get("/authorize")
def authorize():
    """Generate the authorization URL."""
    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES)
    flow.redirect_uri = "http://127.0.0.1:8000/callback"  # Replace with your callback URL
    auth_url, state = flow.authorization_url(prompt='consent')
    token_storage['state'] = state
    return {"authorization_url": auth_url}


@app.get("/callback")
async def callback(request: Request):
    state = token_storage.get('state')
    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = "http://127.0.0.1:8000/callback"  # Ensure this matches the redirect_uri used in /authorize
    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response, include_client_id=True)
    credentials = flow.credentials

    # Save the credentials (for demonstration purposes, use memory storage)
    token_storage['credentials'] = credentials_to_dict(credentials)
    return {"message": "Authorization successful. You can now access Google Drive."}


@app.get("/list-files")
def list_files():
    """List files in the user's Google Drive."""
    credentials = token_storage.get('credentials')
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Please authorize first.")

    creds = Credentials.from_authorized_user_info(credentials, SCOPES)

    try:
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(pageSize=10, fields="files(id, name)").execute()
        files = results.get('files', [])
        return {"files": files}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.get("/list-folders")
def list_folders():
    """List folders in the user's Google Drive."""
    credentials = token_storage.get('credentials')
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Please authorize first.")

    creds = Credentials.from_authorized_user_info(credentials, SCOPES)

    try:
        service = build('drive', 'v3', credentials=creds)
        # Query to filter only folders
        query = "mimeType='application/vnd.google-apps.folder'"
        results = service.files().list(q=query, pageSize=10, fields="files(id, name)").execute()
        folders = results.get('files', [])
        return {"folders": folders}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

@app.get("/folder-contents/{folder_id}")
def get_folder_contents(folder_id: str, page_token: str = None):
    """
    Get the contents of a specific folder in Google Drive with pagination.
    :param folder_id: The ID of the folder whose contents you want to retrieve.
    :param page_token: Token to retrieve the next page of results (optional).
    """
    credentials = token_storage.get('credentials')
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Please authorize first.")

    creds = Credentials.from_authorized_user_info(credentials, SCOPES)

    try:
        service = build('drive', 'v3', credentials=creds)
        # Query to get files with the given folder_id as a parent
        query = f"'{folder_id}' in parents"
        results = service.files().list(
            q=query,
            pageSize=10,  # Set page size
            pageToken=page_token,  # Use the page token if provided
            fields="nextPageToken, files(id, name, mimeType, webViewLink)"
        ).execute()

        folder_contents = results.get('files', [])
        next_page_token = results.get('nextPageToken')  # Get the next page token, if available

        return {
            "folder_id": folder_id,
            "contents": folder_contents,
            "next_page_token": next_page_token  # Include the token in the response
        }
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")



def credentials_to_dict(credentials):
    """Helper function to convert credentials to a dictionary."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
