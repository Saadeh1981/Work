# backend/services/patterns.py
import re

# generic number like 49.56 or 1,234.5
NUM = r'(?:(?:\d{1,3}(?:,\d{3})+)|\d+)(?:\.\d+)?'

# Accept KWDC, KW DC, kW-DC, etc., and the “TOTAL DC SYSTEM RATING … 49.56KWDC” style
KWDC = re.compile(
    rf'(?is)\b({NUM})\s*(?:k|kw)\s*[-\s]*d\s*c\b|'
    rf'total\s+dc\s+(?:system\s+)?rating.*?({NUM})\s*k[w]?\s*d[c]\b'
)

# Accept kWAC, KW AC and “AC capacity/rating … 42 kWac”
KWAC = re.compile(
    rf'(?is)\b({NUM})\s*(?:k|kw)\s*[-\s]*a\s*c\b|'
    rf'ac\s+(?:capacity|rating)\D{{0,20}}({NUM})\s*k[w]?\s*a[c]\b'
)

MOD_COUNT = re.compile(rf'(?is)\b(?:total\s+module\s+count|modules?\s+total|quantity|qty)\b\D{{0,10}}({NUM})')
INV_COUNT = re.compile(rf'(?is)\b(?:total\s+inverter\s+count|inverters?\s+total)\b\D{{0,10}}({NUM})')

# Pull models after "Module -" / "Inverter -", capturing full token with () / - / /
MOD_MODEL = re.compile(
    r'(?im)^\s*module\s*[-:]\s*(?P<model>[A-Z0-9][A-Z0-9\-\(\)\/\s\.]+?)\s*(?:class|ungrounded|voltage|count|total|\Z)',
    re.I
)
INV_MODEL = re.compile(
    r'(?im)^\s*inverter\s*[-:]\s*(?P<model>[A-Z0-9][A-Z0-9\-\(\)\/\s\.]+?)\s*(?:\(\d+v\)|total|count|updated|\Z)',
    re.I
)

# Plant name: uppercase title lines, but skip generic headings
PLANT_LINE = re.compile(r'(?im)^\s*([A-Z][A-Z0-9&\-\s]{6,})\s*$')
PLANT_SKIP = {
    'COVER SHEET','SYSTEM SPECIFICATIONS','SHEET INDEX','SCOPE OF WORK',
    'PRELIMINARY DESIGN','UPDATED LAYOUT DESCRIPTION','UPDATED INVERTER',
    'ELECTRICAL CALCULATIONS & SPEC SHEETS', 'SYMBOLS, ABBREVIATIONS, & SPECIFICATIONS'
}
