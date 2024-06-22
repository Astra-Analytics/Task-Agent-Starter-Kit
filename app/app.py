import os
import threading
from calendar import c

import flask
import google.oauth2.credentials
import google_auth_oauthlib.flow
import requests
from flask import Blueprint, g, jsonify, redirect, render_template, session, url_for

from integrations.email.fetcher import email_fetcher
from tasks.processor import start_processing, tasks_storage

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_LOGIN_URI = os.getenv("GOOGLE_LOGIN_URI")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html", google_client_id=CLIENT_ID)


@main.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    tasks = tasks_storage.get_tasks(condition="actionStatus = 'Active'")
    agent_tasks = [task for task in tasks.values() if task["agent"] == "AI"]
    human_tasks = [task for task in tasks.values() if task["agent"] != "AI"]

    if "credentials" not in session:
        return redirect(url_for("main.index"))

    # Start the background processes for email fetching and task processing
    if not hasattr(g, "email_fetcher_thread"):
        start_processing()
        email_fetcher_thread = threading.Thread(
            target=email_fetcher,
            args=(session["credentials"],),
            daemon=True,
            name="email_fetcher",
        )

        email_fetcher_thread.start()
        g.email_fetcher_thread = email_fetcher_thread

    return render_template(
        "dashboard.html", agent_tasks=agent_tasks, human_tasks=human_tasks
    )


@main.route("/tasks")
def get_tasks():
    tasks = tasks_storage.get_tasks(condition="actionStatus = 'Active'")
    agent_tasks = [task for task in tasks.values() if task["agent"] == "AI"]
    human_tasks = [task for task in tasks.values() if task["agent"] != "AI"]
    return jsonify(agent_tasks=agent_tasks, human_tasks=human_tasks)


@main.route("/authorize", methods=["GET", "POST"])
def authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = url_for("main.oauth2callback", _external=True)
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@main.route("/oauth2callback", methods=["GET", "POST"])
def oauth2callback():
    state = session["state"]
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = url_for("main.oauth2callback", _external=True)
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)

    return redirect(url_for("main.dashboard"))


@main.route("/revoke")
def revoke():
    if "credentials" not in session:
        return 'You need to <a href="/authorize">authorize</a> before testing the code to revoke credentials.'

    credentials = google.oauth2.credentials.Credentials(**session["credentials"])

    revoke = requests.post(
        "https://oauth2.googleapis.com/revoke",
        params={"token": credentials.token},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    status_code = getattr(revoke, "status_code")
    if status_code == 200:
        return "Credentials successfully revoked."
    else:
        return "An error occurred."


@main.route("/clear")
def clear_credentials():
    if "credentials" in session:
        del session["credentials"]
    return "Credentials have been cleared."


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
