import requests
import os
class Mailer:
    def __init__(self, templatesDir="mailers"):
        self.templatesDir = templatesDir

    def _load_template(self, templateName, **templateVars):
        path = os.path.join(self.templatesDir, f"{templateName}.txt")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content.format(**templateVars)

    def send_email(self, sender, subject, templateName, to=None, **fields):
        textBody = self._load_template(templateName, **fields)

        return requests.post(
            f"https://api.eu.mailgun.net/v3/{os.environ.get('MAILGUN_DOMAIN')}/messages",
            auth=("api", os.environ.get("MAILGUN_API_KEY")),
            data={
                "from": f"{sender} <{os.environ.get('MAILGUN_SENDER_EMAIL')}>",
                "to": to,
                "subject": subject,
                "text": textBody
            }
        ).json()
