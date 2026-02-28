import logging

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from connections.models import Connection
from connections.services import dispatch_message, edit_discord_message

from .forms import MessageForm
from .models import DeliveryReceipt, Message

logger = logging.getLogger(__name__)


def _base_context():
    """Common context injected into every messaging view."""
    return {
        "history": Message.objects.all(),
        "connections": Connection.objects.all(),
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
    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.created_by = request.user
            msg.save()
            action = request.POST.get("action", "save")
            if action == "send":
                _send_message(request, msg)
            flash.success(request, "Message saved.")
            return redirect("messaging:detail", pk=msg.pk)
    else:
        form = MessageForm()
    ctx = _base_context()
    ctx.update({"form": form, "mode": "create"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_edit(request, pk):
    message = get_object_or_404(Message, pk=pk)
    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES, instance=message)
        if form.is_valid():
            msg = form.save()
            action = request.POST.get("action", "save")
            if action == "send":
                _send_message(request, msg)
                _edit_discord_messages(msg)
            flash.success(request, "Message updated.")
            return redirect("messaging:detail", pk=msg.pk)
    else:
        form = MessageForm(instance=message)
    receipts = message.receipts.select_related("connection").all()
    ctx = _base_context()
    ctx.update({"form": form, "message": message, "receipts": receipts, "mode": "edit"})
    return render(request, "messaging/message_view.html", ctx)


@login_required
def message_send(request, pk):
    """POST-only: send (or resend) a message."""
    if request.method != "POST":
        return redirect("messaging:detail", pk=pk)
    message = get_object_or_404(Message, pk=pk)
    _send_message(request, message)
    flash.success(request, "Message dispatched.")
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


def _send_message(request, message):
    try:
        dispatch_message(message)
        if not message.sent and message.last_error:
            flash.error(request, f"Send failed: {message.last_error}")
    except Exception as exc:
        logger.error("Dispatch error: %s", exc)
        flash.error(request, f"Send error: {exc}")


def _edit_discord_messages(message):
    """Attempt to edit Discord messages that support editing."""
    receipts = DeliveryReceipt.objects.filter(
        message=message, success=True
    ).select_related("connection")
    for receipt in receipts:
        concrete = receipt.connection.get_concrete()
        if (
            concrete.connection_type == "discord"
            and concrete.can_edit_sent
            and receipt.remote_message_id
        ):
            image_path = None
            if message.image:
                try:
                    image_path = message.image.path
                except Exception:
                    pass
            edit_discord_message(
                concrete,
                receipt.remote_message_id,
                message.headline,
                message.body,
                image_path,
            )
