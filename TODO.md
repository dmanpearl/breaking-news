# TODO

## Completed Items

- [x] Deploy to Railway.com (https://breaking-news.up.railway.app)
- [x] Partial Messages: Messages can be sent with any one of Headline, Message, or Attachment.
- [x] Send Button: Disable the Send button if any one of Headline, Message, or Attachment is not available.
- [x] History: Previous message view only displays Headline, Message, or Attachment if present.
- [x] History: When Message has only an Attachment (no Headline, no Message), Implement a custom message title for the History View built from file type and file size of the attachment.
- [x] Keyboard Enter/Return Key Sends message: when focus is in message editing field, the Enter key sends the message.
- [x] Headline: Remove:
  - [x] Headline: Add a Site Settings flag called headline_enable (default: False).
  - [x] Headline: Remove Headline from Editor if headline_enable=False.
  - [x] Headline: When headline_enable=False and a user edits a message with a Headline, prepend the Headline to the body separated by linefeeds.
- [x] Auto-focus cursor in new message body after pressing '+ New' to help quickly type new messages.
- [x] Instant Send: After sending a message, immediately create a new message.
- [x] Allow Empty Message Text: Messages can be sent with only attachments (images only, not text).
- [x] Paste Image Support: While editing a message with an image in the clipboard, keyboard paste auto-attaches the image.
- [x] Drag and drop image support to add an image to a message.
- [x] Fix Image Display Bug: Images cease to display in the app after sending, need to implement Cloudinary SAAS service.
- [x] Add eyeball button in password fields to view plaintext passwords (Login & Admin User Create)
- [x] PDF: Support PDF file format attachments
- [x] Display sender's name with message info

## Open Items

- [ ] Delete message capability.
- [ ] PDF bug: File downloads as 'upload.pdf', but should have the original filename.
- [ ] Deploy to custom domain (http://breakingnewschat.com, http://breakingnewsguys.com, http://thebreakingnewsguys.com)
- [ ] Video: Support video file format attachments
- [ ] Multi-Image Support: Allow attachment of multiple images to a message.
- [ ] Metrics: Get any metrics from Discord about message views and other stats that may be available.
- [ ] New Connection Type: Add another service we can post to in addition to Discord.
