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
- [x] PDF bug: File downloads as 'upload.pdf', but should have the original filename.
- [x] New Connection Type: Add Slack (text-only) in addition to Discord.
- [x] Connection disable inhibits send for any Connection and removes green toolbar connection light.
- [x] Slack Connection: Add file attachment support.
- [x] App icon: Update with a dark background.
- [x] Add better Connection management Enable/Disable controls in Admin view.
- [x] Delete message capability.
- [x] Deploy to Squarespace domain http://breakingnewsguys.com.
- [x] Users without Editor, Staff, or Admin permission are no longer able to send or edit chat messages.
- [x] When the app starts up, it should land on create message. Or if user doesn't have edit permission, it should land on View first message.
- [x] Implement poll API so enterprise users can pull messages from us.
- [x] Implement streaming API so enterprise users can open a socket with us and receive messages instantly.
- [x] API Usage log.
- [x] Tie all API keys to a User called owner.
- [x] Send messages faster
- [x] Fix connection exhaustion under SSE load bug, PostgreSQL error "sorry, too many clients already"

## Open Items

- [ ] Breaking News history list auto-refreshes as new messages arrive from another node.
- [ ] Display more message info in the history panel:
    1. Always display up to four lines of text in the history panel.
    2. Provide spin-down capability to display the entire text and image for any message right there in the history panel.
    3. Provide a toggle that spins-opens all messages simultaneously. Setting is persistent per user.
    4. Make history panel wider.
    5. Make history pane width adjustable. Setting is persistent. Edge case caution!
- [ ] Bug: Messages send slowly. Look for parallization and other options
- [ ] Bug: Ocassional Forbidden (403) CSRF verification failed. Request aborted. More information is available with DEBUG=True.
      I had the error on the login page because it when I closed down my computer and then I opened it back up and then I get to the username and password and that’s where I had the issue
      Refreshed and help I had to go to a different URL I had to go to the Messages breaking news page instead of the login breaking news page
- [ ] Implement Usage Log for Users similar to the existing API Usage Log
- [ ] Admin panel delete messages bulk one of the confirmation buttons is truncated (bottom half cut off)
- [ ] Support multiple send groups (for developers and differing client types)
