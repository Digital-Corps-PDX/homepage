import json
import logging
import smtplib
import sys

from datetime import UTC, datetime
from email.message import EmailMessage
from email.headerregistry import Address
from html.parser import HTMLParser

# I got an SSL: CERTIFICATE_VERIFY_FAILED error trying to make
# an HTTPS call.  My resolution:
#  - as an admin, `pip install --upgrade certifi`
#  - then,        `export SSL_CERT_FILE=$(python3 -m certifi)`
#
# I don't know if the upgrade helped.
#
# Q: https://stackoverflow.com/questions/77442172
#  A: https://stackoverflow.com/a/77443265/246801
#  A: https://stackoverflow.com/a/79235523/246801
from airtable import Record, Table

SUBJECT = "🌲 PDX Digital Corps — Thanks for your interest!"

# The PDX Digital Corps base
BASE_ID = "appWwcOT5kBnEq6P9"
# The Volunteers table
TABLE_ID = "tblBizheg4s11n93a"
# The view of volunteers that have not been emailed the intro
VIEW_ID = "viwOUapltcR0kfXof"

VIEW_ID = "viwUYJjUwUNGqC4ir"  # dev-mode view of just ZachYoung_38


logging.basicConfig(
    format="%(asctime)s %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)


def main():
    smtp_token, airtable_token = get_tokens("secrets.json")

    html, text = get_email_bodies("body.html")

    volunteers = get_volunteers(airtable_token)
    if not volunteers:
        logging.info("no new volunteers; done")
        return

    mail_srv = connect_to_mail_srv(smtp_token)

    updates = send_emails(volunteers, mail_srv, html, text)

    mail_srv.close()
    logging.info("disconnected email server")

    update_volunteers(airtable_token, updates)


def get_tokens(fname: str) -> tuple[str, str]:
    """
    Read secrets JSON at fname, return smtp and airtable tokens.
    """
    smtp_token, airtable_token = "", ""
    try:
        with open(fname) as f:
            data = json.load(f)
            smtp_token = data["SMTP_TOKEN"]
            airtable_token = data["AIRTABLE_TOKEN"]
    except Exception as e:
        error_out(f"could not fetch secret tokens: {e}")

    logging.info("got smtp and airtable tokens")

    return smtp_token, airtable_token


def get_email_bodies(fname: str) -> tuple[str, str]:
    """
    Read the HTML body at fname, convert to TXT, return
    both HTML and TXT.
    """
    html = ""
    try:
        with open(fname) as f:
            html = f.read()
    except Exception as e:
        error_out(f"could not get HTML: {e}")

    txt = ""
    try:
        txt = html_to_text(html)
    except Exception as e:
        error_out(f"could not convert HTML to text: {e}")

    logging.info("got HTML body and converted to TXT")

    return html, txt


def get_volunteers(airtable_token: str) -> list[Record]:
    """
    Use airtable_token to read from a view in Airtable and get
    a list of volunteers.
    """

    table = Table(airtable_token, BASE_ID, TABLE_ID)

    volunteers: list[Record] = []
    try:
        volunteers = table.fetch(view=VIEW_ID, fields=["Full Name", "Email"])
        logging.info(f"got {len(volunteers)} Volunteers")
    except Exception as e:
        error_out(f"could not get volunteers: {e}")

    return volunteers


def connect_to_mail_srv(smtp_token: str) -> smtplib.SMTP:
    mail_srv = smtplib.SMTP("smtp.protonmail.ch", 587)
    try:
        mail_srv.starttls()
        logging.info("started tls")
        mail_srv.login("info@digitalcorpspdx.org", smtp_token)
        logging.info("connected to email server")
    except Exception as e:
        error_out(f"could not connect to email server: {e}")

    return mail_srv


def send_emails(volunteers: list[Record], mail_srv: smtplib.SMTP, html: str, text: str) -> list[Record]:
    """
    Iterate list of volunteers, composing emails with
    html and text bodies, and sending with mail_srv.
    """

    updates: list[Record] = []
    for x in volunteers:
        try:
            name, email = x["fields"]["Full Name"], x["fields"]["Email"]
        except Exception as e:
            logging.info(f"error: could not get name and email: {e}")
            continue

        # dev-mode sanity check to prevent emailing real volunteers
        dev_email = "zacharysyoung@gmail.com"
        if email != dev_email:
            raise ValueError(f"DEV-MODE: {email} != {dev_email}")

        try:
            msg = EmailMessage()
            msg["Subject"] = SUBJECT
            msg["From"] = Address(display_name="PDX Digital Corps", addr_spec="info@digitalcorpspdx.org")
            msg["To"] = Address(display_name=name, addr_spec=email)
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")

            mail_srv.sendmail(msg["From"], msg["To"], msg.as_string())
            logging.info(f"  sent mail to {name}")

            updates.append(
                {"id": x["id"], "fields": {"Intro_emailed": datetime.now(UTC).isoformat()}},
            )
        except Exception as e:
            error_out(f"could not compose and send message: {e}")

    return updates


def update_volunteers(airtable_token: str, updates: list[Record]):
    """
    Use airtable_token to send volunteer updates back to Airtable.
    """

    table = Table(airtable_token, BASE_ID, TABLE_ID)

    try:
        table.patch(updates)
        logging.info("updated volunteers")
    except Exception as e:
        error_out(f"could not update volunteers: {e}")


def html_to_text(html: str) -> str:
    """Somewhat intelligently pulls text out of html and formats it."""

    class MyHTMLParser(HTMLParser):
        """
        Builds up a string of just the text nodes;
        formats links, like '<a href="foo">Some bar</a>' as 'Some bar <foo>'.
        """

        s = ""
        skip_data = False
        href = ""

        def handle_starttag(self, tag, attrs):
            match tag:
                case "a":
                    self.href = dict(attrs)["href"]
                case "code":
                    self.s += "`"
                case "head":
                    self.skip_data = True

        def handle_endtag(self, tag):
            match tag:
                case "code":
                    self.s += "`"
                case "head":
                    self.skip_data = False

        def handle_data(self, data: str):
            if self.skip_data:
                return

            self.s += data

            if self.href:
                self.s += f" <{self.href}>"
                self.href = ""

        def to_string(self) -> str:
            """Normalizes white space in the built-up string."""
            raw_text = self.s.replace("\r", "\n").split("\n")

            out: list[str] = []
            for line in raw_text:
                line = line.strip()
                if line == "":
                    continue
                out.append(line)

            return "\n\n".join(out)

    parser = MyHTMLParser()
    parser.feed(html)
    return parser.to_string()


def error_out(msg: str):
    """Print msg to stderr and exit with code 2."""
    if not msg.startswith("error: "):
        msg = "error: " + msg
    print(msg, file=sys.stderr)
    exit(2)


main()
