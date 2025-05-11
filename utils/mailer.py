import requests
import os

class Mailer:


    def send_email(self, subject=None, text=None, to=None, name=None):
        return requests.post(
            f"https://api.eu.mailgun.net/v3/{os.environ.get("MAILGUN_DOMAIN")}/messages",
            auth=("api", os.environ.get("MAILGUN_API_KEY")),
            data={"from": f"{name} <{os.environ.get("MAILGUN_SENDER_EMAIL")}>",
                "to": f"{to}",
                "subject": subject,
                "text": text}).json()