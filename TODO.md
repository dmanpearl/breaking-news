# TODO

## Completed Items

- [x] Deploy to Railway.com (https://breaking-news.up.railway.app)
- [x] Partial Messages: Messages can be sent with any one of Headline, Message, or Attachment.
- [x] Send Button: Disable the Send button if any one of Headline, Message, or Attachment is not available.
- [x] History: Previous message view only displays Headline, Message, or Attachment if present.
- [x] History: When Message has only an Attachment (no Headline, no Message), Implement a custom message title for the History View built from file type and file size of the attachment.
- [x] Keyboard Enter/Return Key Sends message: when focus is in message editing field, the Enter key sends the message.

## Open Items

- [ ] Headline: Remove:
  - [ ] Headline: Add a Site Settings flag called headline_enable (default: False).
  - [ ] Headline: Remove Headline from Editor if headline_enable=False.
  - [ ] Headline: When headline_enable=False and a user edits a message with a Headline, prepend the Headline to the body separated by linefeeds.
- [ ] Instant Send: Idle mode is Create Message state, allowing immediate type and send.
- [ ] Allow Empty Message Text: Messages can be sent with only attachments (images only, not text).
- [ ] Paste Image Support: While editing a message with an image in the clipboard, keyboard paste auto-attaches the image.
- [ ] Deploy to custom domain (http://breakingnewschat.com, http://breakingnewsguys.com, http://thebreakingnewsguys.com)
- [ ] PDF: Support PDF file format attachments.
- [ ] Multi-Image Support: Allow attachment of multiple images to a message.
- [ ] Metrics: Get any metrics from Discord about message views and other stats that may be available.
- [ ] New Connection Type: Add another service we can post to in addition to Discord.
