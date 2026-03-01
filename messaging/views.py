import logging

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from connections.models import Connection
from connections.services import (
    EDIT_FAILED,
    EDIT_OK,
    EDIT_SKIPPED_DISABLED,
    EDIT_SKIPPED_NO_ID,
    dispatch_message,
    update_sent_messages,
)

from core.models import SiteSettings
from .forms import MessageForm
from .models import Message

logger = logging.getLogger(__name__)


def _base_context():
    """Common context injected into every messaging view."""
    settings = SiteSettings.get()
    return {
        "history": Message.objects.all(),
        "connections": Connection.objects.all(),
        "headline_enabled": settings.headline_enable,
    }


@login_required
def index(request):
    return render(request, "messaging/index.html", _base_context())


@login_required
def message_detail(request, pk):
    message = get_object_or_404(Message, pk=pk)
    receipts = message.receipts.select_related("connection").all()
    ctx = _base_context()
    ctx.update({"message": message, "receipts": receipts, "mode": "view"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_create(request):
    headline_enabled = SiteSettings.get().headline_enable
    if request.method == "POST":
        form = MessageForm(
            request.POST, request.FILES, headline_enabled=headline_enabled
        )
        if form.is_valid():
            msg = form.save(commit=False)
            msg.created_by = request.user
            msg.save()
            action = request.POST.get("action", "save")
            if action == "send":
                _do_send(request, msg)
            else:
                flash.success(request, "Draft saved.")
            return redirect("messaging:detail", pk=msg.pk)
    else:
        form = MessageForm(headline_enabled=headline_enabled)
    ctx = _base_context()
    ctx.update({"form": form, "mode": "create"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_edit(request, pk):
    message = get_object_or_404(Message, pk=pk)
    if not message.can_edit:
        flash.error(
            request,
            "This message has been sent and none of its connections allow editing. "
            "Enable Can edit sent on the connection in the admin panel.",
        )
        return redirect("messaging:detail", pk=pk)
    headline_enabled = SiteSettings.get().headline_enable
    if request.method == "POST":
        form = MessageForm(
            request.POST,
            request.FILES,
            instance=message,
            headline_enabled=headline_enabled,
        )
        if form.is_valid():
            msg = form.save()
            if msg.sent:
                # Message was previously delivered — attempt in-place edits.
                results = update_sent_messages(msg)
                _report_edit_results(request, results)
            else:
                # Never successfully sent — treat Update as a fresh send.
                _do_send(request, msg)
            return redirect("messaging:detail", pk=msg.pk)
    else:
        # If headline is disabled and this message has one, migrate it into body.
        if not SiteSettings.get().headline_enable and message.headline:
            merged_body = (
                (message.headline + "\n\n" + message.body)
                if message.body
                else message.headline
            )
            migrated = message.__class__(
                pk=message.pk,
                headline="",
                body=merged_body,
                image=message.image,
                sent=message.sent,
                last_error=message.last_error,
                created_by=message.created_by,
                created_at=message.created_at,
                updated_at=message.updated_at,
            )
            form = MessageForm(instance=migrated, headline_enabled=False)
        else:
            form = MessageForm(instance=message, headline_enabled=headline_enabled)
    receipts = message.receipts.select_related("connection").all()
    ctx = _base_context()
    ctx.update({"form": form, "message": message, "receipts": receipts, "mode": "edit"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_send(request, pk):
    """POST-only: (re)send a message to all enabled connections."""
    if request.method != "POST":
        return redirect("messaging:detail", pk=pk)
    message = get_object_or_404(Message, pk=pk)
    _do_send(request, message)
    return redirect("messaging:detail", pk=pk)


@login_required
def message_delete(request, pk):
    if request.method == "POST":
        msg = get_object_or_404(Message, pk=pk)
        msg.delete()
        flash.success(request, "Message deleted.")
        return redirect("messaging:index")
    return redirect("messaging:detail", pk=pk)


@login_required
def history_partial(request):
    """Returns only the history list partial (for HTMX / reactive use)."""
    return render(
        request, "messaging/history_list.html", {"history": Message.objects.all()}
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _do_send(request, message):
    """Dispatch message to all enabled connections and flash results."""
    try:
        dispatch_message(message)
        if message.sent:
            flash.success(request, "Message sent successfully.")
        else:
            flash.error(request, f"Send failed: {message.last_error}")
    except Exception as exc:
        logger.error("Dispatch error: %s", exc)
        flash.error(request, f"Send error: {exc}")


def _report_edit_results(request, results: dict):
    """Flash a clear message for each connection edit outcome."""
    if not results:
        flash.warning(
            request,
            "Local changes saved. No connections attempted — "
            "either no messages have been sent yet, or all receipts are missing.",
        )
        return

    ok = [n for n, (s, _) in results.items() if s == EDIT_OK]
    failed = [(n, e) for n, (s, e) in results.items() if s == EDIT_FAILED]
    disabled = [(n, e) for n, (s, e) in results.items() if s == EDIT_SKIPPED_DISABLED]
    no_id = [(n, e) for n, (s, e) in results.items() if s == EDIT_SKIPPED_NO_ID]

    if ok:
        flash.success(request, f"Discord updated on: {', '.join(ok)}.")

    for name, err in failed:
        flash.error(request, f"Edit failed on {name}: {err}")

    for name, _ in disabled:
        flash.warning(
            request,
            f"Local changes saved, but '{name}' was not updated in Discord — "
            f"'Can edit sent' is disabled on that connection. "
            f"Enable it in the admin panel to allow in-place Discord edits.",
        )

    for name, _ in no_id:
        flash.warning(
            request,
            f"Local changes saved, but '{name}' could not be edited — "
            f"no Discord message ID was stored for that delivery.",
        )
