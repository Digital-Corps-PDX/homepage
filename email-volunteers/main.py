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


logging.basicConfig(
    format="%(asctime)s %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)


def main():

    # -- Get secret tokens --------------------------------------------------------

    smtp_token, airtable_token = "", ""
    try:
        with open("secrets.json") as f:
            data = json.load(f)
            smtp_token = data["SMTP_TOKEN"]
            airtable_token = data["AIRTABLE_TOKEN"]
    except Exception as e:
        print(f"could not fetch secret tokens: {e}", file=sys.stderr)
        exit(2)
    logging.info("got token from secrets.json")

    # -- Get the HTML file for the body, make text ----------------------------

    html_body = ""
    try:
        with open("body.html") as f:
            html_body = f.read()
    except Exception as e:
        print(f"could not get body.html: {e}", file=sys.stderr)
        exit(2)
    text_body = html_to_text(html_body)

    # -- Get list of volunteers to email from Airtable ----------------------------

    # The Volunteers table of the PDX Digital Corps base
    BASE_ID = "appWwcOT5kBnEq6P9"
    TABLE_ID = "tblBizheg4s11n93a"
    # The view of volunteers that have not been emailed the intro
    VIEW_ID = "viwOzosoARJrI14cw"

    table = Table(airtable_token, BASE_ID, TABLE_ID)
    logging.info("created Airtable connection")
    volunteers = table.fetch(view=VIEW_ID, fields=["Full Name", "Email", "Intro_emailed"])
    logging.info(f"got {len(volunteers)} Volunteers")

    # -- Log in to SMTP email server  ---------------------------------------------

    mail = smtplib.SMTP("smtp.protonmail.ch", 587)
    mail.starttls()
    logging.info("started tls")
    mail.login("info@digitalcorpspdx.org", smtp_token)
    logging.info("logged in to smtp server")

    # -- Iterate volunteers, send  ------------------------------------------------

    SUBJECT = "🌲 PDX Digital Corps — Thanks for your interest!"

    for x in volunteers:
        name, email = x["fields"]["Full Name"], x["fields"]["Email"]

        # dev-mode sanity check to prevent emailing real volunteers
        if email != (want := "zacharysyoung@gmail.com"):
            raise ValueError(f"{email} != {want}")

        msg = EmailMessage()
        msg["Subject"] = SUBJECT
        msg["From"] = Address(display_name="PDX Digital Corps", addr_spec="info@digitalcorpspdx.org")
        msg["To"] = Address(display_name=name, addr_spec=email)
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        mail.sendmail(msg["From"], msg["To"], msg.as_string())
        logging.info(f" sent mail to {name}")

    mail.close()
    logging.info("closed connection to smtp server")

    # -- Update records in Airtable  ----------------------------------------------

    updates: list[Record] = []
    for x in volunteers:
        updates.append(
            {
                "id": x["id"],
                "fields": {"Intro_emailed": datetime.now(UTC).isoformat()},
            }
        )
    table.patch(updates)
    logging.info("updated Volunteers emailed-timestamp in Airtable")


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


main()
