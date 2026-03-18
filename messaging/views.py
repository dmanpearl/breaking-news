import logging

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from connections.services import (
    EDIT_FAILED,
    EDIT_OK,
    DELETE_OK,
    DELETE_FAILED,
    dispatch_message,
    update_sent_messages,
    delete_sent_messages,
)

from core.models import SiteSettings
from .forms import MessageForm
from .models import Message

logger = logging.getLogger(__name__)


def is_editor(user):
    """Return True if the user can create/edit/send/delete messages.

    Editors are: Django superusers, Django staff, or members of the
    'editor' or 'admin' groups.  Everyone else is treated as a viewer
    (read-only).
    """
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=["editor", "admin"]).exists()


def is_api_consumer(user):
    """Return True if the user has access to the API docs nav link.

    Superusers, staff, and members of the 'api_consumer' group all qualify.
    """
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name="api_consumer").exists()


def _base_context(request):
    """Common context injected into every messaging view."""
    settings = SiteSettings.get()
    return {
        "history": Message.objects.select_related("created_by").all(),
        "headline_enabled": settings.headline_enable,
        "user_is_editor": is_editor(request.user),
        "user_is_api_consumer": is_api_consumer(request.user),
        "user_is_staff": request.user.is_active and (request.user.is_staff or request.user.is_superuser),
    }


@login_required
def index(request):
    if is_editor(request.user):
        return redirect("messaging:create")
    # Viewer: redirect to the most recent message, or show the empty landing page.
    latest = Message.objects.first()
    if latest:
        return redirect("messaging:detail", pk=latest.pk)
    return render(request, "messaging/index.html", _base_context(request))


@login_required
def message_detail(request, pk):
    message = get_object_or_404(Message, pk=pk)
    receipts = message.receipts.select_related("connection").all()
    ctx = _base_context(request)
    ctx.update(
        {
            "message": message,
            "receipts": receipts,
            "mode": "view",
        }
    )
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_create(request):
    if not is_editor(request.user):
        flash.error(request, "You do not have permission to create messages.")
        latest = Message.objects.first()
        if latest:
            return redirect("messaging:detail", pk=latest.pk)
        return redirect("messaging:index")
    # Read SiteSettings once -- _base_context also calls it, but that
    # call is deferred to render time; we need headline_enabled now.
    settings = SiteSettings.get()
    headline_enabled = settings.headline_enable
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
                return redirect("messaging:create")
            return redirect("messaging:detail", pk=msg.pk)
    else:
        form = MessageForm(headline_enabled=headline_enabled)
    ctx = _base_context(request)
    ctx.update({"form": form, "mode": "create"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_edit(request, pk):
    if not is_editor(request.user):
        flash.error(request, "You do not have permission to edit messages.")
        return redirect("messaging:detail", pk=pk)
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
        if not headline_enabled and message.headline:
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
    ctx = _base_context(request)
    ctx.update({"form": form, "message": message, "receipts": receipts, "mode": "edit"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_send(request, pk):
    """POST-only: (re)send a message to all enabled connections."""
    if not is_editor(request.user):
        flash.error(request, "You do not have permission to send messages.")
        return redirect("messaging:detail", pk=pk)
    if request.method != "POST":
        return redirect("messaging:detail", pk=pk)
    message = get_object_or_404(Message, pk=pk)
    _do_send(request, message)
    return redirect("messaging:detail", pk=pk)


@login_required
def message_delete_confirm(request, pk):
    """GET: show the two-option delete confirmation page."""
    if not is_editor(request.user):
        flash.error(request, "You do not have permission to delete messages.")
        return redirect("messaging:detail", pk=pk)
    message = get_object_or_404(Message, pk=pk)
    ctx = _base_context(request)
    ctx.update({"message": message})
    return render(request, "messaging/delete_confirm.html", ctx)


@login_required
def message_delete(request, pk):
    """POST-only: delete a message. mode = 'everywhere' or 'local'."""
    if not is_editor(request.user):
        flash.error(request, "You do not have permission to delete messages.")
        return redirect("messaging:detail", pk=pk)
    if request.method != "POST":
        return redirect("messaging:delete_confirm", pk=pk)

    msg = get_object_or_404(Message, pk=pk)
    mode = request.POST.get("mode", "local")

    if mode == "everywhere" and msg.sent:
        results = delete_sent_messages(msg)
        _report_delete_results(request, results)

    msg.delete()
    flash.success(request, "Message deleted from Breaking News.")
    return redirect("messaging:index")


@login_required
def landing(request):
    """Always renders the landing/empty-state page regardless of message history.
    Used by the nav logo easter egg so editors/viewers can always reach it."""
    return render(request, "messaging/index.html", _base_context(request))


@login_required
def history_partial(request):
    """Returns only the history list partial (for HTMX / reactive use)."""
    return render(
        request, "messaging/history_list.html", {"history": Message.objects.select_related("created_by").all()}
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


def _report_delete_results(request, results: dict):
    """Flash results for connection deletes.

    Only reports when something actually happened -- no flash when all
    connections are disabled and results is empty.
    """
    if not results:
        return  # no enabled connections -- nothing happened, nothing to report

    ok = [n for n, (s, _) in results.items() if s == DELETE_OK]
    failed = [(n, e) for n, (s, e) in results.items() if s == DELETE_FAILED]

    if ok:
        flash.success(request, f"Deleted from Discord: {', '.join(ok)}.")
    for name, err in failed:
        flash.error(request, f"Discord delete failed on {name}: {err}")


def _report_edit_results(request, results: dict):
    """Flash results for connection edits.

    Only reports when something actually happened -- no flash when all
    connections are disabled and results is empty.
    """
    if not results:
        flash.success(request, "Local changes saved.")
        return

    ok = [n for n, (s, _) in results.items() if s == EDIT_OK]
    failed = [(n, e) for n, (s, e) in results.items() if s == EDIT_FAILED]

    if ok:
        flash.success(request, f"Discord updated on: {', '.join(ok)}.")
    for name, err in failed:
        flash.error(request, f"Edit failed on {name}: {err}")
