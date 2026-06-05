"""Management command: log_messages - export messages to a YAML log file."""

import os
from datetime import datetime, time, timedelta
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from messaging.models import Message

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _env_subdir():
    return "prod" if os.environ.get("RAILWAY_ENVIRONMENT") else "dev"


def _log_dir():
    return BASE_DIR / "logs" / _env_subdir()


def _last_id_path():
    return _log_dir() / ".last_id"


def _read_last_id():
    path = _last_id_path()
    if path.exists():
        try:
            return int(path.read_text().strip())
        except ValueError:
            return None
    return None


def _write_last_id(pk):
    path = _last_id_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pk))


def _local_now():
    return datetime.now().astimezone()


def _format_ts(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _parse_date(value, flag):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise CommandError(f"{flag} must be in YYYY-MM-DD format, got: {value!r}")


def _parse_datetime(value, flag):
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).astimezone()
        except ValueError:
            continue
    raise CommandError(f"{flag} must be in YYYY-MM-DDTHH:MM format, got: {value!r}")


def _attachment_value(message):
    if not message.image:
        return None
    try:
        url = message.image.url
    except Exception:
        return None
    if url.startswith("http"):
        return url
    name = message.image.name or ""
    return f"media/{name}" if name else None


class _BlockStrDumper(yaml.Dumper):
    pass


def _str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockStrDumper.add_representer(str, _str_representer)


class Command(BaseCommand):
    help = (
        "Export messages to a timestamped YAML log file in logs/. "
        "Default (no flags): exports messages after the last logged id saved in "
        "logs/<env>/.last_id, or from yesterday if no last logged id exists. "
        "The last logged id is updated after every successful run."
    )

    def add_arguments(self, parser):
        start_group = parser.add_mutually_exclusive_group()
        start_group.add_argument(
            "--all",
            action="store_true",
            dest="all",
            help="Export all messages from the beginning of time.",
        )
        start_group.add_argument(
            "--since-id",
            type=int,
            metavar="N",
            help="Export messages with id greater than N. Example: --since-id 42",
        )
        start_group.add_argument(
            "--start-date",
            metavar="YYYY-MM-DD",
            help=(
                "Start from midnight (00:00:00) of this date (local time). "
                "Example: --start-date 2026-06-01"
            ),
        )
        start_group.add_argument(
            "--start-datetime",
            metavar="YYYY-MM-DD HH:MM",
            help=(
                "Start from this exact local datetime. "
                "Example: --start-datetime '2026-06-01 09:00'"
            ),
        )

        end_group = parser.add_mutually_exclusive_group()
        end_group.add_argument(
            "--end-date",
            metavar="YYYY-MM-DD",
            help=(
                "End at 23:59:59 of this date (inclusive, local time). "
                "Default: end of today. Example: --end-date 2026-06-04"
            ),
        )
        end_group.add_argument(
            "--end-datetime",
            metavar="YYYY-MM-DD HH:MM",
            help=(
                "End at this exact local datetime. "
                "Default: now. Example: --end-datetime '2026-06-04 17:30'"
            ),
        )

        parser.add_argument(
            "--output",
            metavar="FILE",
            help="Override the output file path.",
        )

    def handle(self, *args, **options):
        now = _local_now()

        # Resolve end bound
        if options["end_datetime"]:
            end_dt = _parse_datetime(options["end_datetime"], "--end-datetime")
        elif options["end_date"]:
            d = _parse_date(options["end_date"], "--end-date")
            end_dt = datetime.combine(d, time(23, 59, 59)).astimezone()
        else:
            end_dt = now

        # Build base queryset filtered by end bound, oldest-first for cursor tracking
        qs = Message.objects.filter(created_at__lte=end_dt).order_by("id")

        # Resolve start bound
        if options["all"]:
            pass  # no lower bound
        elif options["since_id"] is not None:
            qs = qs.filter(id__gt=options["since_id"])
        elif options["start_date"]:
            d = _parse_date(options["start_date"], "--start-date")
            start_dt = datetime.combine(d, time.min).astimezone()
            qs = qs.filter(created_at__gte=start_dt)
        elif options["start_datetime"]:
            start_dt = _parse_datetime(options["start_datetime"], "--start-datetime")
            qs = qs.filter(created_at__gte=start_dt)
        else:
            # Default: after last logged id, or yesterday 00:00:00 if no cursor
            last_id = _read_last_id()
            if last_id is not None:
                qs = qs.filter(id__gt=last_id)
            else:
                yesterday_start = datetime.combine(
                    (now - timedelta(days=1)).date(), time.min
                ).astimezone()
                qs = qs.filter(created_at__gte=yesterday_start)

        messages = list(qs.select_related("created_by"))

        if not messages:
            self.stdout.write("No messages found for the specified range.")
            return

        # Build records
        records = []
        for m in messages:
            record = {
                "id": m.pk,
                "timestamp": _format_ts(m.created_at),
                "author": m.display_sender_full,
            }
            if m.headline:
                record["headline"] = m.headline
            record["body"] = m.body or ""
            attachment = _attachment_value(m)
            if attachment:
                record["attachment"] = attachment
            records.append(record)

        # Resolve output path
        if options["output"]:
            out_path = Path(options["output"])
        else:
            ts_str = now.strftime("%Y-%m-%d_%H-%M-%S")
            out_path = _log_dir() / f"messages_{ts_str}.yaml"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(
                records,
                f,
                Dumper=_BlockStrDumper,
                allow_unicode=True,
                sort_keys=False,
            )

        _write_last_id(messages[-1].pk)

        self.stdout.write(f"Logged {len(messages)} message(s) to {out_path}")
