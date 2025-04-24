# Sending volunteers introductory emails

Send introductroy emails with PDXDC's Proton mail account from a Python script from a list of not-yet-introduced-to volunteers from Airtable.

## Install and run it

### Install

- Up-to-date Python.

  The script was developed with Python 3.13.0. Python 3.10 **might** be recent enough.

- Install latest certificates.

  I got an SSL: CERTIFICATE_VERIFY_FAILED error (I believe when the mail server tries to start TLS). My resolution:

  - as an admin, `pip install --upgrade certifi`
  - then make sure Python sees the new certs before each run by setting the SSL_CERT_FILE var:

    ```shell
    SSL_CERT_FILE=$(python3 -m certifi); python3 main.py
    ```

    I don't know if the upgrade helped, or just specifying the path:

    - Q: https://stackoverflow.com/questions/77442172
      - A: https://stackoverflow.com/a/77443265/246801
      - A: https://stackoverflow.com/a/79235523/246801

### Run

On macOS/\*nix, use [run.sh](./run.sh).

[run.cmd](./run.cmd) was created for Windows, but hasn't been tested.

## Proton

With a paid plan (a must) and an SMTP token, the script sends emails from our Proton mail account.

### The token

To get an SMTP token, follow the steps outlined in <https://proton.me/support/smtp-submission#setup>.

### Rate limits

Proton has [basic and extended rate limits](https://proton.me/support/email-sending-limits) for sending emails.

The basic limit is 50 emails/hr and 150 emails/day. For paid plans, the limit can be affected by our "reputation". The guidelines for increasing reputation:

- Start using your email address — the more you use it, the higher your sending limits will become.
- Encourage your friends to join Proton Mail — sending emails to other Proton Mail addresses has much higher sending limits.
- Don’t send spam — ensure you are only sending to individuals you know or are expecting an email from you.
- Avoid sending to undeliverable addresses.
- Avoid excessive use of BCC.
- Ensure all account information is up-to-date in your account settings.

We may not accrue enough rep to make a noticeable difference, but we should be aware that sending to undeliverable addresses may decrease our limit; no real way to avoid sending undeliverables... just FYI.

## Airtable

With a personal access token (PAT), the script reads a list of volunteers in Airtable that need to be sent an intro email, and then updates that list in Airtable (to remove them from the list).

Generate a PAT at <https://airtable.com/create/tokens>, the PAT needs:

- the `data.records:read` and `data.records:write` scopes
- access to the particular base with the volunteers

Save the generated token somewhere safe/secure; and remember that the short `pat123ABC...` ID displayed in tokens dashboard will not work as the actual token (#lifelessons 😖).

## The script

The script [main.py](./main.py):

1. reads a secrets file for the SMTP and Airtable tokens
1. reads an HTML file for the bodies of the emails
1. gets a list of volunteers from Airtable; exits if no volunteers to email, otherwise...
1. logs in to Proton's SMTP server
1. for each volunteer:
   - sends an email
   - creates an update with a sent-intro-email timestamp
1. closes the connection to the SMTP server
1. sends all the updates to Airtable

### The tokens and HTML files

The script expects to find secrets.json and body.html in the working directory.

- **secrets.json**: a JSON file with two keys SMTP_TOKEN and AIRTABLE_TOKEN, e.g.:

  ```json
  {
    "SMTP_TOKEN": "ABC123...",
    "AIRTABLE_TOKEN": "DEF456..."
  }
  ```

- **body.html**: an HTML file (CSS can be embedded in the head).

  The script derives plain text from the HTML as a fallback in case that the recipient's email client does not display HTML.
