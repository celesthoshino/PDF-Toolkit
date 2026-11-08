# PDF Toolkit

Five PDF tools in one script:

- **merge**: combine several PDFs into one
- **split**: save every page as its own PDF
- **extract**: copy only some pages into a new PDF
- **compress**: make PDFs smaller
- **images**: turn photos or scans into one PDF

Put your files in the `input` folder, run the script, pick a tool, and get the results in the `output` folder.

## Folder layout

```
pdf_toolkit/
├── pdf_tool.py        the script
├── requirements.txt   Python packages to install
├── README.md          this file
├── input/             put your PDFs (or images) here
└── output/            results appear here
```

## Setup (one time)

1. Install **Python 3.9 or newer** from https://www.python.org/downloads/
   (on Windows, tick "Add Python to PATH" during install).
2. Open a terminal in the `pdf_toolkit` folder and run:

   ```
   pip install -r requirements.txt
   ```

## How to use

1. Copy your PDFs (or images, for the images tool) into the `input` folder.
2. Open a terminal in the `pdf_toolkit` folder and run:

   ```
   python pdf_tool.py
   ```

3. Pick a tool from the menu by typing its number.
4. The results are saved in the `output` folder.

You can also name the tool straight away so it skips the menu:

| Command | What it does |
|---|---|
| `python pdf_tool.py` | Shows the menu |
| `python pdf_tool.py merge` | Combines all PDFs into `output/merged.pdf` |
| `python pdf_tool.py merge -n "Tax 2024"` | Same, but saved as `output/Tax 2024.pdf` |
| `python pdf_tool.py split` | Every page of every PDF becomes its own file |
| `python pdf_tool.py split --every 10` | Splits into files of 10 pages each |
| `python pdf_tool.py extract 1-3,7` | Copies pages 1, 2, 3 and 7 of each PDF into a new PDF |
| `python pdf_tool.py extract 5-` | Copies page 5 to the end |
| `python pdf_tool.py compress` | Makes every PDF smaller |
| `python pdf_tool.py compress -l high` | Makes them as small as possible (pictures get blurrier) |
| `python pdf_tool.py images` | Turns all images into `output/images.pdf`, one image per page |
| `python pdf_tool.py images --page-size letter` | Same, on US Letter pages instead of A4 |
| `python pdf_tool.py --help` | Shows all tools. Use `python pdf_tool.py split --help` for one tool's options |

## The tools

### merge
Combines every PDF in `input` into one PDF, in **alphabetical order**. Numbers are sorted the way you'd expect
(`2.pdf` comes before `10.pdf`), so the easiest way to choose the order is to start the names with numbers:
`01 cover.pdf`, `02 report.pdf`, `03 appendix.pdf`. Each original file becomes a bookmark in the merged PDF.

If any PDF can't be read, nothing is merged, so you never get a merged file with something silently missing.

| Option | Default | Meaning |
|---|---|---|
| `-n`, `--name` | `merged` | Name of the merged file |

### split
Saves each page as its own PDF, in a folder named after the original:
`input/report.pdf` → `output/report/report_page_1.pdf`, `report_page_2.pdf`, ...

| Option | Default | Meaning |
|---|---|---|
| `--every` | `1` | Pages per file. `--every 10` makes files of 10 pages: `report_pages_01-10.pdf`, `report_pages_11-20.pdf`, ... |

### extract
Copies the pages you choose from each PDF into a new PDF: `input/report.pdf` → `output/report_pages_1-3_7.pdf`.

How to write the pages:

| You type | Pages copied |
|---|---|
| `3` | page 3 |
| `1-3` | pages 1, 2 and 3 |
| `1-3,7,10-12` | pages 1, 2, 3, 7, 10, 11 and 12 |
| `5-` | page 5 to the last page |

Pages past the end of a PDF are left out (with a note).

### compress
Makes PDFs smaller, mostly by shrinking the pictures and scans inside them. Text and drawings stay sharp.
The compressed copy has the same name as the original: `input/scan.pdf` → `output/scan.pdf`.

| Option | Default | Meaning |
|---|---|---|
| `-l`, `--level` | `medium` | `low`: barely visible change, smaller savings. `medium`: good balance. `high`: smallest files, pictures look softer |

PDFs that are mostly text are usually already small, so they won't shrink much. If a PDF can't be made smaller,
it's copied as-is.

### images
Turns every image in `input` into one PDF, one image per page, in alphabetical order (like merge).
Accepts `.jpg .jpeg .jfif .png .webp .bmp .gif .tif .tiff .heic .heif`.

| Option | Default | Meaning |
|---|---|---|
| `-n`, `--name` | `images` | Name of the new PDF |
| `--page-size` | `a4` | `a4` or `letter`: images are centered on the page with a small margin, and wide images get landscape pages. `fit`: each page is exactly the size of its image, with no margins |

## Options for every tool

| Option | Default | Meaning |
|---|---|---|
| `-i`, `--input` | `input` folder | Folder to read files from |
| `-o`, `--output` | `output` folder | Folder to save results to |

## Good to know

- **Original files are never changed or deleted.** The script only reads from `input`.
- **Running a tool again overwrites earlier results** with the same name in `output`.
- **Password-protected PDFs** (ones that ask for a password to open) are skipped. PDFs that open without a password
  but have editing restrictions work fine, and the results don't have the restrictions.
- **The tools only look at files directly inside `input`.** Subfolders are not scanned.
- **Merge, split and extract don't lower quality.** Pages are copied exactly. Only compress and images re-save pictures.

## Troubleshooting

**`Error: the required packages are not installed`**
Run `pip install -r requirements.txt` from inside the `pdf_toolkit` folder.

**`it is password protected`**
The PDF needs a password to open. Open it in a PDF viewer with the password, use "Print to PDF" to save an unlocked
copy, and put that copy in `input`.

**`it could not be read, the file may be damaged`**
The file is damaged or isn't really a PDF. Try opening it in a PDF viewer. If it opens, use "Print to PDF" to save a
clean copy and use that.

**The merged pages are in the wrong order**
Rename the files so they sort in the order you want, for example `01 ...`, `02 ...`, `03 ...`.

**`'python' is not recognized`**
Python isn't on your PATH. On Windows, try `py pdf_tool.py` instead, or reinstall Python with "Add Python to PATH" ticked.
