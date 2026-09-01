"""
Shift rules for attendance.

One place decides what "late" and "early out" mean, so the API, the admin and
the React app can never drift apart. The window itself lives on CompanySettings
(shiftStart / shiftEnd) and defaults to 10:05 AM - 7:00 PM.

Times are "HH:MM" 24-hour strings throughout; that format sorts the same way it
ticks, which keeps the comparisons trivial.
"""
from __future__ import annotations

DEFAULT_SHIFT_START = "10:05"
DEFAULT_SHIFT_END = "19:00"

# Statuses an admin sets by hand. The shift rules never overwrite these — if
# someone is marked Absent or on Leave, a stray check-in shouldn't undo it.
MANUAL_STATUSES = {"Absent", "Leave", "On Field", "Holiday"}


def to_minutes(hhmm: str) -> int | None:
    """"10:05" -> 605. Returns None for blank or unparseable input.

    Accepts a few shapes the UI has produced over time: "10:05", "10:05:30",
    and the 12-hour "10:05 AM" a manual edit might paste in.
    """
    raw = str(hhmm or "").strip().upper()
    if not raw:
        return None

    meridiem = ""
    if raw.endswith("AM") or raw.endswith("PM"):
        meridiem = raw[-2:]
        raw = raw[:-2].strip()

    parts = raw.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= minute < 60):
        return None

    if meridiem == "AM":
        if not (1 <= hour <= 12):
            return None
        hour = 0 if hour == 12 else hour
    elif meridiem == "PM":
        if not (1 <= hour <= 12):
            return None
        hour = 12 if hour == 12 else hour + 12
    elif not (0 <= hour < 24):
        return None

    return hour * 60 + minute


def shift_window(company=None) -> tuple[str, str]:
    """(start, end) for the configured shift, falling back to 10:05 / 19:00."""
    start = getattr(company, "shiftStart", "") or DEFAULT_SHIFT_START
    end = getattr(company, "shiftEnd", "") or DEFAULT_SHIFT_END
    # A malformed value in the database shouldn't take attendance down with it.
    if to_minutes(start) is None:
        start = DEFAULT_SHIFT_START
    if to_minutes(end) is None:
        end = DEFAULT_SHIFT_END
    return start, end


def evaluate(check_in: str, check_out: str, company=None, current_status: str = ""):
    """Derive (status, late_minutes, early_minutes) from a punch pair.

    Rules, exactly as configured:
      * check-in at or before shiftStart  -> Present
      * check-in after shiftStart         -> Late Present (lateMinutes > 0)
      * check-out at or after shiftEnd    -> full shift (earlyMinutes = 0)
      * check-out before shiftEnd         -> Early Out (earlyMinutes > 0)

    A late arrival outranks an early departure in the single `status` field,
    because arriving late is the stricter signal; `earlyMinutes` still records
    the short departure so both show up in reports.
    """
    start, end = shift_window(company)
    start_m = to_minutes(start)
    end_m = to_minutes(end)

    in_m = to_minutes(check_in)
    out_m = to_minutes(check_out)

    late = max(0, in_m - start_m) if in_m is not None and start_m is not None else 0
    early = max(0, end_m - out_m) if out_m is not None and end_m is not None else 0

    # Never fight a deliberate admin choice.
    if current_status in MANUAL_STATUSES:
        return current_status, late, early

    if in_m is None:
        # No punch recorded: leave whatever status was set (usually Absent).
        return current_status or "Absent", late, early

    if late > 0:
        return "Late Present", late, early
    if early > 0:
        return "Early Out", late, early
    return "Present", late, early


def humanise_minutes(minutes: int) -> str:
    """65 -> "1h 5m". Used in exports and the admin list."""
    minutes = int(minutes or 0)
    if minutes <= 0:
        return "—"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    return f"{hours}h" if hours else f"{mins}m"
