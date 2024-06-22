import base64
import os
import re

import google.oauth2.credentials
import googleapiclient.discovery
from flask import session

max_emails = int(os.getenv("INITIAL_EMAILS", 10))


def fetch_latest_email(service):
    # Fetch the latest message
    results = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=max_emails)
        .execute()
    )
    messages = results.get("messages", [])

    if not messages:
        return None

    msg = messages[0]
    txt = (
        service.users()
        .messages()
        .get(userId="me", id=msg["id"], format="full")
        .execute()
    )

    email_data = {
        "To": "",
        "From": "",
        "Subject": "",
        "Body": "",
        "Timestamp": "",
        "Message-ID": msg["id"],
    }

    # Parse headers for email details
    payload = txt["payload"]
    headers = payload["headers"]

    for header in headers:
        if header["name"] == "To":
            email_data["To"] = header["value"]
        elif header["name"] == "From":
            email_data["From"] = header["value"]
        elif header["name"] == "Subject":
            email_data["Subject"] = header["value"]
        elif header["name"] == "Date":
            email_data["Timestamp"] = header["value"]

    # Handle the body of the email
    if "parts" in payload:
        # Find 'text/plain' part
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                body_data = part["body"]["data"]
                break
    else:
        # This is a simple email with only one part
        body_data = payload["body"]["data"]

    # Decode the email body
    decoded_body = base64.urlsafe_b64decode(body_data.encode("ASCII")).decode("utf-8")

    # Optionally, strip out signature if it starts with '--'
    email_data["Body"] = re.split(r"\r?\n--\r?\n", decoded_body, 1)[0]

    return email_data


def gmail_service(credentials=None):
    if not credentials and "credentials" not in session:
        return None

    if not credentials:
        credentials = session["credentials"]

    credentials = google.oauth2.credentials.Credentials(**credentials)
    service = googleapiclient.discovery.build("gmail", "v1", credentials=credentials)
    return service
