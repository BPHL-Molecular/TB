#!/usr/bin/env python3
"""TBQuery 1.0 — annotate Varipipeline sample summaries with WHO TB catalogue grading.

Usage:
    python tbquery.py samples.txt [--catalog WHO-UCN-TB-2023.7-eng.xlsx] \
        [--out-dir who_summaries] [--include-lof]

`samples.txt` is a list file with one sample summary path per line (blank lines
and '#' comments are ignored).

Produces one Excel workbook per sample (named '<sample>_who_summary.xlsx' in the
output directory) mirroring the input layout, with the WHO FINAL CONFIDENCE
GRADING added. Sub-threshold Read Depth / Percent Alt Allele cells and
not-in-catalogue variants are highlighted.
"""
import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

__version__ = "1.0"

# --- Catalogue layout ---
# Columns are resolved by header text (see resolve_columns) rather than by a
# fixed index, so the tool keeps working if WHO reorders or adds columns in a
# future catalogue release. Values are the lower-cased header labels to match.
CATALOG_SHEET = "Catalogue_master_file"
REQUIRED_COLUMNS = {
    "drug": "drug",
    "gene": "gene",
    "mutation": "mutation",
    "variant": "variant",
    "tier": "tier",
    "effect": "effect",
    "grading": "final confidence grading",
    "comment": "comment",
}

# Read depth / allele-fraction review thresholds
MIN_READ_DEPTH = 30
MIN_PERCENT_ALT = 10.0

# Label used for variants absent from the WHO catalogue.
REVIEW_LABEL = "REVIEW (not in WHO catalog)"


def resolve_columns(header_row):
    """Map required field names to 0-based column indices from a header row.

    header_row is the tuple of cell values for the catalogue header line.
    Matching is case-insensitive against the labels in REQUIRED_COLUMNS.
    """
    norm = {}
    for idx, value in enumerate(header_row):
        if value is None:
            continue
        norm.setdefault(str(value).strip().lower(), idx)
    cols = {}
    missing = []
    for field, label in REQUIRED_COLUMNS.items():
        if label in norm:
            cols[field] = norm[label]
        else:
            missing.append(label)
    if missing:
        raise ValueError(f"Catalogue is missing expected column(s): {', '.join(missing)}")
    return cols


def catalog_version(xlsx_path):
    """Human-readable catalogue version derived from the file name.

    The WHO release identifier is embedded in the filename (e.g.
    'WHO-UCN-TB-2023.7-eng.xlsx' -> 'WHO-UCN-TB-2023.7-eng'); the catalogue
    workbook carries no clean internal version string, so the filename is the
    authoritative source recorded for CLIA cross-checking.
    """
    return os.path.splitext(os.path.basename(xlsx_path))[0]


def load_catalog(xlsx_path):
    """Return (catalog, meta).

    catalog maps a variant string (e.g. 'katG_p.Ser315Thr') to a list of match
    dicts. Each match records its source cell location ('source', e.g.
    'row 5763, col DB') so the grading can be traced back to the catalogue.

    meta records the catalogue provenance (file name, derived version, workbook
    modified date, grading column letter).

    The header row is located by content (first row containing 'drug', 'gene'
    and 'variant'), then column positions are resolved by header text.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb[CATALOG_SHEET]
    catalog = defaultdict(list)
    cols = None
    grading_col_letter = None
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
        if cols is None:
            labels = {str(v).strip().lower() for v in row if v is not None}
            if {"drug", "gene", "variant"} <= labels:
                cols = resolve_columns(row)
                grading_col_letter = get_column_letter(cols["grading"] + 1)
            continue
        variant = row[cols["variant"]]
        if not variant:
            continue
        catalog[str(variant).strip()].append(
            {
                "drug": row[cols["drug"]],
                "grading": row[cols["grading"]],
                "comment": row[cols["comment"]],
                "tier": row[cols["tier"]],
                "effect": row[cols["effect"]],
                "source": f"row {row_idx}, col {grading_col_letter}",
            }
        )
    modified = wb.properties.modified
    wb.close()
    if cols is None:
        raise ValueError(f"Could not find a header row in sheet {CATALOG_SHEET!r}")
    meta = {
        "file": os.path.basename(xlsx_path),
        "version": catalog_version(xlsx_path),
        "modified": modified.date().isoformat() if modified else "(unknown)",
        "grading_col": grading_col_letter,
    }
    return catalog, meta


def is_lof_change(aa_change):
    """True if an amino-acid change is a loss-of-function (LoF) type.

    WHO grades frameshift, premature stop (nonsense) and start-lost variants
    collectively under a pooled '<gene>_LoF' catalogue entry. Inframe indels,
    stop-lost and missense changes are NOT treated as LoF.
    """
    aa = (aa_change or "").strip()
    if not aa or aa.upper() == "NA":
        return False
    if "fs" in aa:  # frameshift, e.g. p.His221fs
        return True
    if aa.endswith("*") and "ext" not in aa:  # stop_gained, e.g. p.Arg18*
        return True
    if "Met1?" in aa:  # start_lost, e.g. p.Met1?
        return True
    return False


def candidate_keys(gene, nt_change, aa_change, include_lof=False):
    """Build catalogue lookup keys from a variant, applying documented remaps.

    - gene mmpR  -> Rv0678
    - gene rrl   -> nucleotide change 'c.' rewritten as 'n.'
    - when include_lof is true, LoF variants also try the pooled '<gene>_LoF'
      entry last, so an exact per-variant grading always takes precedence.
    """
    lookup_gene = "Rv0678" if gene == "mmpR" else gene

    changes = []
    if aa_change and str(aa_change).strip().upper() != "NA":
        changes.append(str(aa_change).strip())
    if nt_change and str(nt_change).strip().upper() != "NA":
        nt = str(nt_change).strip()
        if gene == "rrl" and nt.startswith("c."):
            nt = "n." + nt[2:]
        changes.append(nt)

    keys = []
    for change in changes:
        key = f"{lookup_gene}_{change}"
        if key not in keys:
            keys.append(key)

    if include_lof and is_lof_change(aa_change):
        lof_key = f"{lookup_gene}_LoF"
        if lof_key not in keys:
            keys.append(lof_key)
    return keys


def lookup_variant(gene, nt_change, aa_change, catalog, include_lof=False):
    """Return (matched_key, [match dicts]). [] matches => unmatched."""
    for key in candidate_keys(gene, nt_change, aa_change, include_lof=include_lof):
        if key in catalog:
            return key, catalog[key]
    return None, []


def parse_summary(txt_path):
    """Parse a Varipipeline summary into its named blocks.

    Returns a dict with raw line-lists for each block plus parsed variant rows.
    """
    with open(txt_path, encoding="utf-8") as fh:
        lines = [line.rstrip("\n") for line in fh]

    blocks = {}
    current = None
    headers = {
        "Sample Summary:": "sample",
        "Target Coverage Summary:": "coverage",
        "Variant Summary:": "variant",
        "Interpretations Summary:": "interp",
    }
    for line in lines:
        stripped = line.strip()
        if stripped in headers:
            current = headers[stripped]
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)

    # Trim trailing blank lines in each block
    for key in blocks:
        while blocks[key] and not blocks[key][-1].strip():
            blocks[key].pop()

    # Parse the variant table rows (skip its header line)
    variant_rows = []
    vlines = [ln for ln in blocks.get("variant", []) if ln.strip()]
    for line in vlines[1:]:  # first non-blank line is the column header
        cols = line.split("\t")
        if len(cols) < 2:  # not a real data row
            continue
        if len(cols) < 7:  # pad e.g. a blank trailing Annotation column
            cols = cols + [""] * (7 - len(cols))
        variant_rows.append(
            {
                "pos": cols[0],
                "gene": cols[1],
                "nt_change": cols[2],
                "aa_change": cols[3],
                "read_depth": cols[4],
                "percent_alt": cols[5],
                "annotation": cols[6],
            }
        )

    return {
        "path": txt_path,
        "sample": blocks.get("sample", []),
        "coverage": blocks.get("coverage", []),
        "interp": blocks.get("interp", []),
        "variant_header": vlines[0] if vlines else "",
        "variant_rows": variant_rows,
    }


def _to_float(value):
    try:
        return float(str(value).strip())
    except (ValueError, AttributeError):
        return None


def row_flags(read_depth, percent_alt):
    flags = []
    depth = _to_float(read_depth)
    if depth is not None and depth < MIN_READ_DEPTH:
        flags.append("LOW_DEPTH")
    alt = _to_float(percent_alt)
    if alt is not None and alt < MIN_PERCENT_ALT:
        flags.append("LOW_AF")
    return flags


def sample_id(sample_block):
    for line in sample_block:
        if line.strip().startswith("Sample ID:"):
            return line.split("\t", 1)[-1].strip()
    return "(unknown sample)"


def sample_name(sample_block):
    for line in sample_block:
        if line.strip().startswith("Sample Name:"):
            return line.split("\t", 1)[-1].strip()
    return sample_id(sample_block)


def enrich_variants(sample, catalog, include_lof=False):
    """Look up each variant once; shared by the text and Excel renderers."""
    enriched = []
    for v in sample["variant_rows"]:
        key, matches = lookup_variant(v["gene"], v["nt_change"], v["aa_change"], catalog)
        if not matches and is_lof_change(v["aa_change"]):
            lookup_gene = "Rv0678" if v["gene"] == "mmpR" else v["gene"]
            lof_key = f"{lookup_gene}_LoF"
            if lof_key in catalog:
                if not include_lof:
                    continue
                key, matches = lof_key, catalog[lof_key]
        flags = row_flags(v["read_depth"], v["percent_alt"])
        enriched.append({"v": v, "key": key, "matches": matches, "flags": flags})
    return enriched


def variant_who_grading(e):
    """Full WHO grading label(s) for the Variant Summary.

    Returns the catalogue's FINAL CONFIDENCE GRADING text (e.g. '1) Assoc w R').
    If a variant matches several catalogue rows with different gradings, the
    unique labels are joined with ' / '. Unmatched variants return REVIEW_LABEL.
    """
    if e["matches"]:
        gradings = sorted({str(m["grading"]) for m in e["matches"]})
        return " / ".join(gradings)
    return REVIEW_LABEL


def variant_who_source(e):
    """Catalogue source cell(s) backing a variant's grading, for cross-checking.

    Mirrors variant_who_grading: unique source locations joined with ' / '.
    Unmatched variants have no catalogue source and return an empty string.
    """
    if not e["matches"]:
        return ""
    sources = sorted({str(m["source"]) for m in e["matches"] if m.get("source")})
    return " / ".join(sources)


def who_interp_rows(enriched):
    """Expand enriched variants to (drug, variant, grading) rows.

    A single variant produces one row per associated drug (WHO Notes: one gene
    may code resistance to multiple drugs). Unmatched variants yield a row with
    grading = REVIEW_LABEL so nothing silently disappears. Identical rows are
    de-duplicated (preserving first-seen order) — e.g. several frameshifts that
    all resolve to the same pooled '<gene>_LoF' entry collapse to a single line.

    Each row is (drug, variant, grading, source), where source is the catalogue
    cell location backing the grading (empty for unmatched variants).
    """
    rows = []
    seen = set()

    def add(row):
        if row not in seen:
            seen.add(row)
            rows.append(row)

    for e in enriched:
        v = e["v"]
        if e["matches"]:
            display = e["key"]
            for m in e["matches"]:
                add((str(m["drug"]), display, str(m["grading"]), str(m.get("source", ""))))
        else:
            aa = v["aa_change"]
            change = aa if aa and aa.upper() != "NA" else v["nt_change"]
            display = f"{v['gene']}_{change}"
            add(("", display, REVIEW_LABEL, ""))
    return rows


# --- Excel rendering ---
LOW_FILL = PatternFill(fill_type="solid", start_color="FFF2CC", end_color="FFF2CC")
REVIEW_FILL = PatternFill(fill_type="solid", start_color="F8CBAD", end_color="F8CBAD")
TITLE_FONT = Font(bold=True, size=12)
HEADER_FONT = Font(bold=True)


def _num_or_str(value):
    """Return a number when the cell parses cleanly, else the original string."""
    f = _to_float(value)
    if f is None:
        return value
    return int(f) if f.is_integer() else f


def _safe_sheet_title(name, used):
    """Excel-legal, <=31 char, unique sheet title."""
    title = re.sub(r"[\\/*?:\[\]]", "_", name).strip() or "Sample"
    title = title[:31]
    base, n = title, 2
    while title in used:
        suffix = f"_{n}"
        title = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(title)
    return title


def _write_cells(ws, row, values, font=None, fills=None):
    """Write `values` across `row` (1-based cols). fills maps col_index->PatternFill."""
    for i, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=i, value=val)
        if font is not None:
            cell.font = font
        if fills and i in fills:
            cell.fill = fills[i]
    return row + 1


def _autosize(ws, max_width=60):
    widths = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            col = cell.column_letter
            widths[col] = min(max(widths.get(col, 0), len(str(cell.value)) + 2), max_width)
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def _write_verbatim_block(ws, row, lines, header_first=True):
    """Write tab-delimited raw lines; bold the first (header) line if present."""
    kept = [ln for ln in lines if ln.strip()]
    for i, line in enumerate(kept):
        font = HEADER_FONT if header_first and i == 0 else None
        row = _write_cells(ws, row, line.split("\t"), font=font)
    return row


def _provenance_rows(meta):
    """Ordered (label, value) pairs describing the catalogue/run provenance."""
    return [
        ("TBQuery version:", __version__),
        ("Catalogue file:", meta.get("file", "(unknown)")),
        ("Catalogue version:", meta.get("version", "(unknown)")),
        ("Catalogue modified:", meta.get("modified", "(unknown)")),
        ("Report generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]


def _safe_filename(name, used):
    """Filesystem-safe, unique '<sample>_who_summary.xlsx' name."""
    base = re.sub(r'[\\/*?:\[\]<>"|]+', "_", name).strip() or "sample"
    filename = f"{base}_who_summary.xlsx"
    n = 2
    while filename in used:
        filename = f"{base}_{n}_who_summary.xlsx"
        n += 1
    used.add(filename)
    return filename


def _render_sample_sheet(ws, sample, enriched, meta):
    """Render one sample's full report onto worksheet `ws`.

    Read Depth and Percent Alt Allele cells below threshold get an amber fill;
    not-in-catalogue calls get a red fill. `meta` is the catalogue provenance
    dict from load_catalog; the sheet opens with a Provenance block and WHO
    gradings carry a 'Catalog Source' cell reference.
    """
    r = 1

    r = _write_cells(ws, r, ["Provenance"], font=TITLE_FONT)
    for label, value in _provenance_rows(meta):
        r = _write_cells(ws, r, [label, value])
    r += 1

    r = _write_cells(ws, r, ["Sample Summary"], font=TITLE_FONT)
    r = _write_verbatim_block(ws, r, sample["sample"], header_first=False)
    r += 1

    r = _write_cells(ws, r, ["Target Coverage Summary"], font=TITLE_FONT)
    r = _write_verbatim_block(ws, r, sample["coverage"])
    r += 1

    r = _write_cells(ws, r, ["Variant Summary"], font=TITLE_FONT)
    header = sample["variant_header"].split("\t") + ["WHO Grading", "Catalog Source"]
    r = _write_cells(ws, r, header, font=HEADER_FONT)
    for e in enriched:
        v = e["v"]
        values = [
            v["pos"],
            v["gene"],
            v["nt_change"],
            v["aa_change"],
            _num_or_str(v["read_depth"]),
            _num_or_str(v["percent_alt"]),
            v["annotation"],
            variant_who_grading(e),
            variant_who_source(e),
        ]
        fills = {}
        if "LOW_DEPTH" in e["flags"]:
            fills[5] = LOW_FILL  # Read Depth column
        if "LOW_AF" in e["flags"]:
            fills[6] = LOW_FILL  # Percent Alt Allele column
        if not e["matches"]:
            fills[8] = REVIEW_FILL  # WHO Grading column
        r = _write_cells(ws, r, values, fills=fills)
    r += 1

    if sample["interp"]:
        r = _write_cells(ws, r, ["Interpretations Summary (Varipipeline)"], font=TITLE_FONT)
        r = _write_verbatim_block(ws, r, sample["interp"])
        r += 1

    r = _write_cells(ws, r, ["WHO Interpretations Summary"], font=TITLE_FONT)
    r = _write_cells(ws, r, ["Drug", "Variant", "WHO Grading", "Catalog Source"], font=HEADER_FONT)
    for drug, variant, grading, source in who_interp_rows(enriched):
        fills = {3: REVIEW_FILL} if grading == REVIEW_LABEL else None
        r = _write_cells(ws, r, [drug, variant, grading, source], fills=fills)

    _autosize(ws)


def write_sample_workbooks(samples, out_dir, meta=None):
    """Write one Excel workbook per sample into `out_dir`.

    `samples` is a list of (parsed_sample, enriched) tuples. Each workbook is
    named '<sample>_who_summary.xlsx'; colliding names get a numeric suffix.
    Returns the list of written file paths.
    """
    meta = meta or {}
    os.makedirs(out_dir, exist_ok=True)
    used = set()
    written = []
    for sample, enriched in samples:
        name = sample_name(sample["sample"])
        path = os.path.join(out_dir, _safe_filename(name, used))
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _safe_sheet_title(name, set())
        _render_sample_sheet(ws, sample, enriched, meta)
        wb.save(path)
        written.append(path)
    return written


def read_sample_list(list_path):
    """Read sample summary paths from a list file (one path per line).

    Blank lines and lines starting with '#' are ignored. Relative paths are
    resolved against the list file's own directory, so a list file stays valid
    regardless of the working directory it is run from.
    """
    base = os.path.dirname(os.path.abspath(list_path))
    paths = []
    with open(list_path, encoding="utf-8") as fh:
        for raw in fh:
            entry = raw.strip()
            if not entry or entry.startswith("#"):
                continue
            paths.append(entry if os.path.isabs(entry) else os.path.join(base, entry))
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        action="version",
        version=f"TBQuery {__version__}",
    )
    parser.add_argument(
        "list_file",
        help="Text file of sample summary paths, one per line (# comments allowed)",
    )
    parser.add_argument(
        "--catalog",
        default="WHO-UCN-TB-2023.7-eng.xlsx",
        help="WHO catalogue .xlsx (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        default="who_summaries",
        help="Directory for per-sample Excel files (default: %(default)s)",
    )
    parser.add_argument(
        "--include-lof",
        action="store_true",
        help="Use pooled <gene>_LoF matches when no exact WHO match exists",
    )
    args = parser.parse_args(argv)

    sample_paths = read_sample_list(args.list_file)
    if not sample_paths:
        parser.error(f"no sample paths found in list file: {args.list_file}")

    print(f"Loading catalogue: {args.catalog} ...", file=sys.stderr)
    catalog, meta = load_catalog(args.catalog)
    print(
        f"  {len(catalog)} catalogued variants loaded "
        f"(version {meta['version']}, modified {meta['modified']}).",
        file=sys.stderr,
    )

    parsed = []
    for path in sample_paths:
        print(f"Annotating: {path}", file=sys.stderr)
        sample = parse_summary(path)
        enriched = enrich_variants(sample, catalog, include_lof=args.include_lof)
        parsed.append((sample, enriched))

    written = write_sample_workbooks(parsed, args.out_dir, meta)
    for path in written:
        print(f"Wrote {path}", file=sys.stderr)
    print(f"Done: {len(written)} file(s) in {args.out_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
