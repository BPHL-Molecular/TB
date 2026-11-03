# TBQuery

**Version 1.0**

TBQuery takes TB sample summary files from Varipipeline and adds drug-resistance
grades from the **WHO mutation catalogue** (`WHO-UCN-TB-2023.7-eng.xlsx`).

For each mutation in a sample, TBQuery finds it in the WHO catalogue, adds the
WHO grade, and saves a **separate Excel file for each sample**. Cells that need a
closer look (low quality, or mutations the WHO catalogue doesn't list) are
colored so they stand out.

## Requirements

- Python 3.8+
- [`openpyxl`](https://openpyxl.readthedocs.io/)

```bash
pip install openpyxl
```

## Inputs

1. **Sample summaries** — one or more Varipipeline `*_summary.txt` files. Each
   file has four sections: `Sample Summary`, `Target Coverage Summary`,
   `Variant Summary`, and `Interpretations Summary`.
2. **WHO catalogue** — `WHO-UCN-TB-2023.7-eng.xlsx` (TBQuery reads its
   `Catalogue_master_file` sheet).

## Running

TBQuery reads one **list file** that contains the path of each sample file, one
per line. Empty lines and lines starting with `#` are skipped. If a path is
relative, it is read relative to the folder that holds the list file, so you can
run the command from any folder.

`samples.txt`:

```text
# TB sample summaries to process
JTS26000149-20260414-M08887-122_S17_summary.txt
JTS26000158-20260609-M08887-126_S5_summary.txt
JTT26003666-20260609-M08887-126_S17_summary.txt
```

```bash
python3 tbquery.py samples.txt
```

Print the software version:

```bash
python3 tbquery.py --version
```

By default, the separate workbooks are written to `who_summaries/`. To choose a
different destination:

```bash
python3 tbquery.py samples.txt --out-dir review_files
```

| Argument    | Default                      | Description                                                |
| ----------- | ---------------------------- | ---------------------------------------------------------- |
| `list_file` | *(required)*                 | Text file of sample paths, one per line (`#` for comments) |
| `--catalog` | `WHO-UCN-TB-2023.7-eng.xlsx` | WHO catalogue workbook                                    |
| `--out-dir` | `who_summaries`              | Directory for the separate per-sample Excel workbooks     |
| `--version` |                              | Print `TBQuery 1.0` and exit                              |

## Output

TBQuery creates **one Excel workbook per sample**. The default filenames for the
example list are:

```text
who_summaries/
├── JTS26000149_who_summary.xlsx
├── JTS26000158_who_summary.xlsx
└── JTT26003666_who_summary.xlsx
```

Each workbook contains one worksheet following the same layout as its input
file, with the WHO grades added. Characters that are not valid in filenames are
replaced with underscores. If two samples have the same name, later files
receive a numeric suffix such as `_2_who_summary.xlsx`.

- **Provenance** — a short block at the top of every sheet recording which
  software and catalogue were used and when the report was generated, for CLIA
  cross-checking: `TBQuery version` (`1.0`), `Catalogue file`,
  `Catalogue version` (derived from the catalogue file name, e.g.
  `WHO-UCN-TB-2023.7-eng`), `Catalogue modified` (the catalogue workbook's
  last-modified date), and `Report generated`.
- **Sample Summary** and **Target Coverage Summary** — copied as-is from the
  input.
- **Variant Summary** — the original mutation table with two extra columns,
  `WHO Grading` and `Catalog Source`. `WHO Grading` shows the WHO grade for the
  mutation (for example `1) Assoc w R`), or `REVIEW (not in WHO catalog)` if the
  WHO catalogue does not list the mutation. `Catalog Source` points to the exact
  cell the grade came from (for example `row 5763, col DB`) so a technologist can
  open the catalogue and verify it directly.
- **Interpretations Summary (Varipipeline)** — the calls made by Varipipeline
  itself, kept so you can compare them with the WHO grades.
- **WHO Interpretations Summary** — columns `Drug`, `Variant`, `WHO Grading`,
  and `Catalog Source`, with one line **per drug** for each mutation (one gene
  can cause resistance to more than one drug). Repeated lines are removed.

The `Catalog Source` reference always points to the catalogue's grading column
(`col DB` in `WHO-UCN-TB-2023.7-eng.xlsx`); the row number is the row where that
variant lives, whose `variant` label is in **column D**.

### Colored cells

Instead of a separate flag column, TBQuery colors the cells directly:

- **Amber** on the `Read Depth` cell when the depth is below 30, and on the
  `Percent Alt Allele` cell when the value is below 10%.
- **Red** on the `WHO Grading` cell for any mutation the WHO catalogue does not
  list (shown as `REVIEW (not in WHO catalog)`). This appears in both the
  Variant Summary and the WHO Interpretations Summary.

The cut-off values are set near the top of `tbquery.py`:

- `MIN_READ_DEPTH = 30`
- `MIN_PERCENT_ALT = 10.0`

## How the lookup works

For each mutation in a sample, TBQuery builds one or more search keys and looks
them up in the catalogue's `variant` column (for example `katG_p.Ser315Thr`).

1. **Building the key** — a key looks like `<gene>_<change>`. TBQuery tries, in
   order:
   1. the amino-acid change (`p....`), then
   2. the nucleotide change (`c....`).
   The first key that exists in the catalogue is used.

2. **Name fixes** (from the bioinformatics notes) — the same mutation is named
   differently in the two files, so TBQuery adjusts:
   - gene `mmpR` → **`Rv0678`** (the name used in the catalogue).
   - for gene `rrl`, a nucleotide change written as `c.` is changed to `n.`
     (this gene makes RNA, not protein).

3. **Grading** — TBQuery copies the matched catalogue row's
   `FINAL CONFIDENCE GRADING` exactly as written. The catalogue uses five
   levels:

   | Grading (from WHO Excel)      | Meaning                              |
   | ----------------------------- | ------------------------------------ |
   | `1) Assoc w R`                | Associated with resistance           |
   | `2) Assoc w R - Interim`      | Associated with resistance (interim) |
   | `3) Uncertain significance`   | Uncertain                            |
   | `4) Not assoc w R - Interim`  | Not associated (interim)             |
   | `5) Not assoc w R`            | Not associated with resistance       |

4. **Multiple drugs** — one mutation can appear against several drugs in the
   catalogue, so it can produce several lines in the WHO Interpretations Summary
   (one per drug).

5. **Not in catalogue** — variants with no match are labelled
   `REVIEW (not in WHO catalog)` (and highlighted red) rather than dropped.

TBQuery finds the catalogue columns by their **header names**, not by fixed
positions, so it keeps working if a future WHO release moves or adds columns.
