"""
validation.py - checking what the user typed.

Each function returns (clean_values, errors).
If `errors` is not empty, the page shows the messages and nothing is saved.
Validation happens here on the server even though the HTML forms also have
basic checks, because browser checks can be bypassed.
"""
import re
from datetime import date, datetime

STOCK_OUT_REASONS = ["Sold", "Used internally", "Damaged", "Expired", "Returned to supplier", "Lost", "Other"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^[0-9+()\-\s.]{5,20}$")


def _text(form, key):
    return (form.get(key) or "").strip()


def _whole_number(raw, label, errors, key, minimum=0, maximum=10_000_000):
    """Parse a whole number such as 12. Rejects 'abc', '1.5' and out-of-range values."""
    raw = (raw or "").strip()
    if raw == "":
        errors[key] = f"{label} is required."
        return None
    try:
        number = int(raw)
    except ValueError:
        errors[key] = f"{label} must be a whole number."
        return None
    if number < minimum:
        if minimum == 0:
            errors[key] = f"{label} cannot be negative."
        else:
            errors[key] = f"{label} must be at least {minimum}."
        return None
    if number > maximum:
        errors[key] = f"{label} is too large."
        return None
    return number


def validate_product(form, editing=False):
    errors, clean = {}, {}

    clean["name"] = _text(form, "name")
    if not clean["name"]:
        errors["name"] = "Product name is required."
    elif len(clean["name"]) > 120:
        errors["name"] = "Product name must be at most 120 characters."

    clean["sku"] = _text(form, "sku").upper()
    if not clean["sku"]:
        errors["sku"] = "SKU is required."
    elif not re.fullmatch(r"[A-Z0-9][A-Z0-9._\-]{0,39}", clean["sku"]):
        errors["sku"] = "SKU may only contain letters, numbers, dots, dashes and underscores (max 40)."

    clean["category"] = _text(form, "category") or "General"
    if len(clean["category"]) > 60:
        errors["category"] = "Category must be at most 60 characters."

    # Quantity is only typed when a product is first created (opening stock).
    # After that it changes only through stock-in / stock-out so history stays correct.
    if not editing:
        clean["quantity"] = _whole_number(form.get("quantity", "0") or "0", "Quantity", errors, "quantity")

    price_raw = _text(form, "unit_price") or "0"
    try:
        price = float(price_raw)
        if price != price or price in (float("inf"), float("-inf")):
            raise ValueError
    except ValueError:
        errors["unit_price"] = "Unit price must be a number."
        price = None
    else:
        if price < 0:
            errors["unit_price"] = "Unit price cannot be negative."
        elif price > 100_000_000:
            errors["unit_price"] = "Unit price is too large."
    clean["unit_price"] = round(price, 2) if price is not None and "unit_price" not in errors else None

    clean["reorder_level"] = _whole_number(form.get("reorder_level", "0") or "0", "Reorder level", errors, "reorder_level")

    target_raw = _text(form, "target_level")
    if target_raw == "":
        # Sensible default: three times the reorder level (at least the reorder level).
        clean["target_level"] = None if clean["reorder_level"] is None else clean["reorder_level"] * 3
    else:
        clean["target_level"] = _whole_number(target_raw, "Target stock level", errors, "target_level")
    if (clean["target_level"] is not None and clean["reorder_level"] is not None
            and clean["target_level"] < clean["reorder_level"]):
        errors["target_level"] = "Target stock level must be at least the reorder level."

    supplier_raw = _text(form, "supplier_id")
    if supplier_raw == "":
        clean["supplier_id"] = None
    elif supplier_raw.isdigit():
        clean["supplier_id"] = int(supplier_raw)
    else:
        errors["supplier_id"] = "Please choose a valid supplier."
    return clean, errors


def validate_supplier(form):
    errors, clean = {}, {}
    clean["name"] = _text(form, "name")
    if not clean["name"]:
        errors["name"] = "Supplier name is required."
    elif len(clean["name"]) > 120:
        errors["name"] = "Supplier name must be at most 120 characters."

    clean["contact_person"] = _text(form, "contact_person")
    if len(clean["contact_person"]) > 120:
        errors["contact_person"] = "Contact person must be at most 120 characters."

    clean["phone"] = _text(form, "phone")
    if clean["phone"] and not _PHONE.match(clean["phone"]):
        errors["phone"] = "Phone may contain digits, spaces, + - ( ) and be 5-20 characters long."

    clean["email"] = _text(form, "email")
    if clean["email"] and not _EMAIL.match(clean["email"]):
        errors["email"] = "Please enter a valid email address, e.g. name@example.com."

    clean["address"] = _text(form, "address")
    if len(clean["address"]) > 300:
        errors["address"] = "Address must be at most 300 characters."
    return clean, errors


def parse_date(raw, label, errors, key, allow_future=False):
    raw = (raw or "").strip()
    if not raw:
        errors[key] = f"{label} is required."
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        errors[key] = f"{label} must be a valid date (YYYY-MM-DD)."
        return None
    if not allow_future and parsed > date.today():
        errors[key] = f"{label} cannot be in the future."
        return None
    return parsed.isoformat()


def validate_movement(form, kind):
    """Checks the stock-in / stock-out form. kind is 'IN' or 'OUT'."""
    errors, clean = {}, {}

    product_raw = _text(form, "product_id")
    if not product_raw.isdigit():
        errors["product_id"] = "Please select a product."
        clean["product_id"] = None
    else:
        clean["product_id"] = int(product_raw)

    clean["quantity"] = _whole_number(form.get("quantity"), "Quantity", errors, "quantity", minimum=1)
    clean["transaction_date"] = parse_date(form.get("transaction_date"), "Date", errors, "transaction_date")

    clean["reference"] = _text(form, "reference")
    if len(clean["reference"]) > 60:
        errors["reference"] = "Reference must be at most 60 characters."
    clean["notes"] = _text(form, "notes")
    if len(clean["notes"]) > 300:
        errors["notes"] = "Notes must be at most 300 characters."

    clean["reason"] = ""
    if kind == "OUT":
        clean["reason"] = _text(form, "reason")
        if clean["reason"] not in STOCK_OUT_REASONS:
            errors["reason"] = "Please choose a reason."
    return clean, errors
