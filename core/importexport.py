"""
Excel (.xlsx) and CSV import/export for the master-data tables.

Three endpoints per collection, all driven by one column spec:

    GET  /api/<collection>/template/?format=xlsx   blank template with headers,
                                                   help text and one sample row
    GET  /api/<collection>/export/?format=xlsx     every row, same column order
    POST /api/<collection>/import/                 multipart upload, upsert

Because the template, the export and the importer all read the same SPEC, a
file exported from the app is always a valid file to import back — which is how
people actually do bulk edits.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass
class Column:
    """One column in the template / export / import mapping."""

    key: str  # model field name
    header: str  # what the user sees in row 1
    required: bool = False
    kind: str = "text"  # text | number | int
    help: str = ""  # shown in the Instructions sheet
    sample: str = ""  # value used in the sample row
    # Callable returning a list of allowed values, used for the dropdown.
    choices: object = None


@dataclass
class Spec:
    """Everything the import/export machinery needs for one collection."""

    name: str  # "Outlet, Wholesalers & Dealer"
    filename: str  # "shops"
    id_field: str  # primary key column, used to decide insert vs update
    columns: list = field(default_factory=list)

    def by_header(self) -> dict:
        """Header text (normalised) -> Column, for reading uploaded files."""
        return {normalise_header(c.header): c for c in self.columns}

    def by_key(self) -> dict:
        return {c.key: c for c in self.columns}


def normalise_header(text) -> str:
    """Loose header matching so 'Shop Name', 'shop name' and 'shop_name' agree."""
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------
def coerce(value, column: Column):
    """Turn a spreadsheet cell into something the model field will accept."""
    if value is None:
        return None if column.kind == "fk" else ("" if column.kind == "text" else 0)

    if isinstance(value, str):
        value = value.strip()

    if column.kind == "fk":
        # A blank cell means "unassigned" -> None, not the FK id "".
        if not value:
            return None
        if isinstance(value, float) and value.is_integer():
            value = str(int(value))
        return str(value)

    if column.kind == "text":
        # Excel loves turning a phone number into a float. Undo that.
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    if value == "":
        return 0

    if column.kind == "int":
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            raise ValueError(f"{column.header}: '{value}' is not a whole number")

    # number (Decimal-backed money)
    try:
        return Decimal(str(value).replace(",", "").replace("৳", "").strip() or "0")
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{column.header}: '{value}' is not a number")


# ---------------------------------------------------------------------------
# Writing: template and export
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
REQUIRED_FILL = PatternFill("solid", fgColor="8B2E3C")
SAMPLE_FILL = PatternFill("solid", fgColor="F2F6FB")


def _write_sheet(ws, spec: Spec, rows: list, *, sample_row: bool):
    ws.title = spec.name[:31]

    for idx, col in enumerate(spec.columns, start=1):
        cell = ws.cell(row=1, column=idx, value=col.header + (" *" if col.required else ""))
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = REQUIRED_FILL if col.required else HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        # Roughly fit the content: header length, sample length, floor of 12.
        width = max(12, len(col.header) + 4, len(str(col.sample)) + 2)
        ws.column_dimensions[get_column_letter(idx)].width = min(width, 38)

    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"

    row_at = 2
    if sample_row:
        for idx, col in enumerate(spec.columns, start=1):
            cell = ws.cell(row=row_at, column=idx, value=col.sample)
            cell.fill = SAMPLE_FILL
            cell.font = Font(italic=True, color="5A6B7F")
        row_at += 1

    for record in rows:
        for idx, col in enumerate(spec.columns, start=1):
            value = record.get(col.key, "")
            if isinstance(value, Decimal):
                value = float(value)
            ws.cell(row=row_at, column=idx, value=value)
        row_at += 1

    # Dropdowns for the columns that have a known option list. Excel caps an
    # inline list at 255 characters, so fall back to free text past that — the
    # importer accepts any value regardless, this is only a typing aid.
    for idx, col in enumerate(spec.columns, start=1):
        options = list(col.choices() if callable(col.choices) else (col.choices or []))
        if not options:
            continue
        joined = ",".join(str(o).replace(",", " ") for o in options)
        if len(joined) > 250:
            continue
        dv = DataValidation(type="list", formula1=f'"{joined}"', allow_blank=not col.required)
        dv.error = "Pick a value from the list, or clear the cell."
        dv.errorTitle = col.header
        letter = get_column_letter(idx)
        ws.add_data_validation(dv)
        dv.add(f"{letter}2:{letter}2000")


def _write_instructions(wb, spec: Spec):
    ws = wb.create_sheet("Instructions")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 74

    title = ws.cell(row=1, column=1, value=f"{spec.name} — bulk import guide")
    title.font = Font(bold=True, size=14)

    notes = [
        f"Fill in the '{spec.name[:31]}' sheet. Row 1 is the header — do not rename or reorder it.",
        "Delete the grey sample row before importing; it is only there to show the expected format.",
        f"'{spec.by_key()[spec.id_field].header}' decides what happens: leave it blank to create a "
        "new record, or keep the existing value to update that record.",
        "Columns marked * are required. Extra columns are ignored, so you can keep your own notes.",
        "You can re-import a file exported from the app — the columns already line up.",
    ]
    row = 3
    for note in notes:
        ws.cell(row=row, column=1, value="•").alignment = Alignment(horizontal="right")
        cell = ws.cell(row=row, column=3, value=note)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    row += 1
    head = row
    for idx, text in enumerate(("Column", "Required", "Notes"), start=1):
        cell = ws.cell(row=head, column=idx, value=text)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
    row += 1

    for col in spec.columns:
        ws.cell(row=row, column=1, value=col.header)
        ws.cell(row=row, column=2, value="Yes" if col.required else "—")
        cell = ws.cell(row=row, column=3, value=col.help)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1


def build_xlsx(spec: Spec, rows: list, *, template: bool) -> bytes:
    wb = Workbook()
    _write_sheet(wb.active, spec, rows, sample_row=template)
    _write_instructions(wb, spec)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_csv(spec: Spec, rows: list, *, template: bool) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([c.header + (" *" if c.required else "") for c in spec.columns])
    if template:
        writer.writerow([c.sample for c in spec.columns])
    for record in rows:
        writer.writerow(
            [
                float(record[c.key]) if isinstance(record.get(c.key), Decimal) else record.get(c.key, "")
                for c in spec.columns
            ]
        )
    # BOM so Excel opens UTF-8 (Bangla shop names, ৳) without mangling it.
    return "﻿" + buffer.getvalue()


# ---------------------------------------------------------------------------
# Reading: parse an uploaded file into row dicts
# ---------------------------------------------------------------------------
def _rows_from_xlsx(upload) -> list:
    wb = load_workbook(upload, data_only=True, read_only=True)
    # Prefer the data sheet over Instructions, whatever the user renamed it to.
    ws = next((s for s in wb.worksheets if s.title.lower() != "instructions"), wb.worksheets[0])
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _rows_from_csv(upload) -> list:
    raw = upload.read()
    if isinstance(raw, bytes):
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                raw = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not read that CSV — save it as UTF-8 and try again.")
    return [row for row in csv.reader(io.StringIO(raw))]


def parse_upload(upload, spec: Spec) -> tuple[list, list]:
    """Read an uploaded .xlsx/.csv into (rows, errors).

    Each row is a dict of model field -> coerced value. Errors are per-row and
    non-fatal: a bad row is reported and skipped, the rest still import. That
    matters for a 500-line shop list where two phone numbers are malformed.
    """
    name = (getattr(upload, "name", "") or "").lower()
    if name.endswith(".csv"):
        table = _rows_from_csv(upload)
    elif name.endswith((".xlsx", ".xlsm")):
        table = _rows_from_xlsx(upload)
    else:
        raise ValueError("Upload a .xlsx or .csv file.")

    table = [r for r in table if any(str(c or "").strip() for c in r)]
    if not table:
        raise ValueError("That file has no rows in it.")

    header_map = spec.by_header()
    headers = table[0]
    # Column index -> Column. Unknown columns are silently ignored so people can
    # keep their own working notes in the sheet.
    positions = {}
    for idx, cell in enumerate(headers):
        key = normalise_header(str(cell or "").rstrip("* "))
        if key in header_map:
            positions[idx] = header_map[key]

    if not positions:
        raise ValueError(
            "None of the column headers matched. Download the template and use its header row."
        )

    missing_required = [
        c.header for c in spec.columns if c.required and c not in positions.values()
    ]
    if missing_required:
        raise ValueError("Missing required column(s): " + ", ".join(missing_required))

    rows, errors = [], []
    for line_no, raw_row in enumerate(table[1:], start=2):
        record, row_errors = {}, []
        for idx, column in positions.items():
            value = raw_row[idx] if idx < len(raw_row) else None
            try:
                record[column.key] = coerce(value, column)
            except ValueError as exc:
                row_errors.append(str(exc))

        # Skip the grey sample row the template ships with, and blank lines.
        if not any(str(v).strip() for v in record.values() if v is not None and v not in (0, Decimal("0"))):
            continue

        for column in spec.columns:
            if column.required and not str(record.get(column.key, "")).strip():
                row_errors.append(f"{column.header} is required")

        if row_errors:
            errors.append({"row": line_no, "errors": row_errors})
        else:
            rows.append(record)

    return rows, errors
