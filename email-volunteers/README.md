# Sending volunteers introductory emails

We send introductroy emails with PDXDC's Proton mail account from a Python script that does a mail merge with with a list of not-yet-introduced-to volunteers from Airtable.

## Proton overview

With a generated SMTP token, we can have a script send emails from our Proton mail account.

### The token

We've followed the steps outlined in <https://proton.me/support/smtp-submission#setup>.

### Rate limits

Proton has [basic and extended rate limits](https://proton.me/support/email-sending-limits) for sending emails.

The basic limit is 50 emails/hr and 150 emails/day. We're on a paid plan, so our limit can be affected by our "reputation". The guidelines for increasing reputation:

- Start using your email address — the more you use it, the higher your sending limits will become.
- Encourage your friends to join Proton Mail — sending emails to other Proton Mail addresses has much higher sending limits.
- Don’t send spam — ensure you are only sending to individuals you know or are expecting an email from you.
- Avoid sending to undeliverable addresses.
- Avoid excessive use of BCC.
- Ensure all account information is up-to-date in your account settings.

We may not accrue enough rep to make a noticeable difference, but we should be aware that sending to undeliverable addresses may decrease our limit.

## The script

The script [main.py](./main.py):

1. reads a secrets file for the SMTP and Airtable tokens
1. logs in to Proton's SMTP server
1. gets a list of recipients to email from a view in the Volunteers table in Airtable, and for each recipient:
   - sends an email
   - marks the Volunteers record as having been emailed

The body of the email comes from an HTML file and is merged with fields from the Volunteers record.

The tokens must be put in a file named secrets.json and have two key-value pairs like the following:

```json
{
  "SMTP_TOKEN": "ABC123...",
  "AIRTABLE_TOKEN": "DEF456..."
}
```

The keys must be SMTP_TOKEN and AIRTABLE_TOKEN.

The HTML body file has regular markup with special {{field_name}} values, where field_name corresponds to the name of a column in the Volunteers table. The script will do a sanity check of the field names in the body file to make sure all specified fields actually exist in Airtable.
