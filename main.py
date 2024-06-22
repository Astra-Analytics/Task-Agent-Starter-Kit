import os

from app import create_app

# Allow testing on localhost
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = create_app()

if __name__ == "__main__":
    app.run("localhost", 8080, debug=True)
    print("Flask started")
