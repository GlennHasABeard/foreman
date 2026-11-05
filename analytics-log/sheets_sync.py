#!/usr/bin/env python3
"""Tracker upsert (v1.2). A re-pull for the same date updates that row.

It never appends a second row for a date already in the file. No network calls.
`tracker_col_a_file` is the optional companion whose column A is that date.
"""


def row_date(row, date_field="date"):
    if not isinstance(row, dict):
        return ""
    raw = row.get(date_field) or row.get("pulled_at_et") or ""
    return str(raw)[:10]


def plan_tracker_upsert(rows, new_row, date_field="date"):
    """Return (rows, 'update' or 'append'). Same date replaces the first match and drops dupes."""
    rows = list(rows or [])
    new_row = dict(new_row or {})
    key = row_date(new_row, date_field)
    new_row[date_field] = key
    out, found = [], False
    for row in rows:
        if key and row_date(row, date_field) == key:
            if not found:
                merged = dict(row)
                merged.update({k: v for k, v in new_row.items() if v is not None})
                merged[date_field] = key
                out.append(merged)
                found = True
        else:
            out.append(row)
    if not found:
        out.append(new_row)
    return out, ("update" if found else "append")


def column_a_rows(rows, date_field="date"):
    """One column, named A, holding the tracker date. Used when tracker_col_a_file is set."""
    return [{"A": row_date(r, date_field)} for r in rows or []]
