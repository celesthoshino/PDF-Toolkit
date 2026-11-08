"""
PDF Toolkit
-----------
Put PDFs (or images) in the "input" folder, pick a tool, and the results show
up in the "output" folder. The original files are never changed.

    python pdf_tool.py                   # shows a menu
    python pdf_tool.py merge             # combine all PDFs into one
    python pdf_tool.py split             # every page becomes its own PDF
    python pdf_tool.py extract 1-3,7     # copy only some pages into a new PDF
    python pdf_tool.py compress          # make PDFs smaller
    python pdf_tool.py images            # turn all images into one PDF

See README.md for all the details.
"""

import argparse
import io
import logging
import re
import shutil
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter, Transformation
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Error: the required packages are not installed.\n"
             "Fix it by running:  pip install -r requirements.txt")

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_EXTENSIONS = {".heic", ".heif"}
except ImportError:
    HEIC_EXTENSIONS = set()

# pypdf prints technical warnings about damaged files; this script explains problems itself.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# The input/output folders live next to this script, so it works no matter
# which folder you run it from.
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"} | HEIC_EXTENSIONS

# Page sizes in points (1 point = 1/72 inch).
PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}
PAGE_MARGIN = 36  # half an inch around images

# compress level -> (JPEG quality, longest side in pixels for pictures inside the PDF)
COMPRESS_LEVELS = {
    "low":    (85, 3000),
    "medium": (70, 2000),
    "high":   (50, 1400),
}

MENU = [
    ("merge",    "Combine all PDFs in the input folder into one PDF"),
    ("split",    "Save every page as its own PDF"),
    ("extract",  "Copy only some pages into a new PDF (for example 1-3,7)"),
    ("compress", "Make PDFs smaller"),
    ("images",   "Turn all images in the input folder into one PDF"),
]


class PdfProblem(Exception):
    """A PDF that can't be used, with a message that explains why."""


# ---------------------------------------------------------------- helpers

def natural_key(path: Path):
    """Sort 'page2' before 'page10', like Windows Explorer does."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def list_files(folder: Path, extensions: set) -> list[Path]:
    files = [p for p in folder.iterdir()
             if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in extensions]
    return sorted(files, key=natural_key)


def open_pdf(path: Path) -> PdfReader:
    """Open a PDF, unlocking it if it only has editing restrictions."""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfProblem("it is password protected")
        if len(reader.pages) == 0:
            raise PdfProblem("it has no pages")
        return reader
    except PdfProblem:
        raise
    except Exception as error:
        if "cryptography" in str(error):
            raise PdfProblem("it is encrypted. Run  pip install -r requirements.txt  to read it") from None
        raise PdfProblem(f"it could not be read, the file may be damaged ({error})") from None


def kb(size: int) -> str:
    return f"{size / 1024:,.0f} KB"


def pages_text(count: int) -> str:
    return f"{count} page" if count == 1 else f"{count} pages"


def safe_name(text: str) -> str:
    """Remove characters Windows doesn't allow in file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", text).strip().rstrip(".") or "output"


def parse_ranges(spec: str) -> list[tuple[int, object]]:
    """'1-3,7,10-' -> [(1, 3), (7, 7), (10, None)]. None means 'until the last page'."""
    ranges = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        match = re.fullmatch(r"(\d+)(?:-(\d*))?", part)
        if not match:
            raise ValueError(f"'{part}' is not a page number or range")
        start = int(match[1])
        end = start if match[2] is None else (int(match[2]) if match[2] else None)
        if start < 1 or (end is not None and end < start):
            raise ValueError(f"'{part}' is not a valid range")
        ranges.append((start, end))
    if not ranges:
        raise ValueError("no pages given")
    return ranges


def require_pdfs(args) -> list[Path]:
    pdfs = list_files(args.input, {".pdf"})
    if not pdfs:
        print("No PDFs found. Put the PDFs in that folder, then run this again.")
    return pdfs


# ---------------------------------------------------------------- tools

def cmd_merge(args) -> int:
    pdfs = require_pdfs(args)
    if not pdfs:
        return 0
    if len(pdfs) == 1:
        print("Only one PDF found. Put at least two PDFs in the input folder to merge them.")
        return 0

    print(f"Merging {len(pdfs)} PDFs in this order:")
    writer = PdfWriter()
    total_pages = 0
    for pdf in pdfs:
        try:
            reader = open_pdf(pdf)
        except PdfProblem as problem:
            print(f"  [fail] {pdf.name}: {problem}")
            print("\nNothing was merged. Remove or fix that file and try again.")
            return 1
        writer.append(reader, outline_item=pdf.stem)  # also adds a bookmark per file
        total_pages += len(reader.pages)
        print(f"  [added] {pdf.name} ({pages_text(len(reader.pages))})")

    out_path = args.output / f"{safe_name(args.name)}.pdf"
    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"\nDone: {pages_text(total_pages)} saved to {out_path}  ({kb(out_path.stat().st_size)})")
    return 0


def cmd_split(args) -> int:
    pdfs = require_pdfs(args)
    failed = 0
    for pdf in pdfs:
        try:
            reader = open_pdf(pdf)
        except PdfProblem as problem:
            print(f"  [fail] {pdf.name}: {problem}")
            failed += 1
            continue

        total = len(reader.pages)
        folder = args.output / pdf.stem
        folder.mkdir(parents=True, exist_ok=True)
        digits = len(str(total))
        count = 0
        for start in range(0, total, args.every):
            end = min(start + args.every, total)  # end is exclusive
            if end - start == 1:
                name = f"{pdf.stem}_page_{start + 1:0{digits}d}.pdf"
            else:
                name = f"{pdf.stem}_pages_{start + 1:0{digits}d}-{end:0{digits}d}.pdf"
            writer = PdfWriter()
            writer.append(reader, pages=(start, end), import_outline=False)
            with open(folder / name, "wb") as f:
                writer.write(f)
            count += 1
        files_text = "1 file" if count == 1 else f"{count} files"
        print(f"  [ok]   {pdf.name}: {pages_text(total)} -> {files_text} in {pdf.stem}/")

    if pdfs:
        print(f"\nDone: {len(pdfs) - failed} split, {failed} failed. Files are in: {args.output}")
    return 1 if failed else 0


def cmd_extract(args) -> int:
    try:
        ranges = parse_ranges(args.pages)
    except ValueError as error:
        print(f"Error: {error}. Use page numbers like  1-3,7  or  5-  (page 5 to the end).")
        return 1

    pdfs = require_pdfs(args)
    label = args.pages.replace(" ", "").replace(",", "_")
    failed = 0
    for pdf in pdfs:
        try:
            reader = open_pdf(pdf)
        except PdfProblem as problem:
            print(f"  [fail] {pdf.name}: {problem}")
            failed += 1
            continue

        total = len(reader.pages)
        pages = []
        for start, end in ranges:
            pages.extend(range(start, min(end or total, total) + 1))
        if not pages:
            print(f"  [skip] {pdf.name}: it only has {pages_text(total)}")
            continue

        writer = PdfWriter()
        for number in pages:
            writer.add_page(reader.pages[number - 1])
        out_path = args.output / f"{pdf.stem}_pages_{label}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        note = ""
        if any(start > total or (end or 0) > total for start, end in ranges):
            note = f"  (it only has {pages_text(total)}, so the rest were left out)"
        print(f"  [ok]   {pdf.name}: {pages_text(len(pages))} -> {out_path.name}{note}")

    if pdfs:
        print(f"\nDone. Files are in: {args.output}")
    return 1 if failed else 0


def shrink_pictures(writer: PdfWriter, quality: int, max_side: int) -> int:
    """Re-save big pictures inside the PDF at a lower quality/size. Returns how many changed."""
    changed = 0
    for page in writer.pages:
        for picture in page.images:
            try:
                image = picture.image
                if image.mode not in ("RGB", "L") or image.width * image.height < 100_000:
                    continue  # leave small images, transparent images and print (CMYK) colors alone
                stored = picture.indirect_reference.get_object()
                if "/SMask" in stored or "/Mask" in stored:
                    continue  # has transparency, which re-saving would lose
                if max(image.size) > max_side:
                    image = image.copy()
                    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                test = io.BytesIO()
                image.save(test, "JPEG", quality=quality)
                if len(test.getvalue()) >= len(picture.data) * 0.9:
                    continue  # wouldn't save much, so keep the original
                picture.replace(image, quality=quality)
                changed += 1
            except Exception:
                continue  # unusual picture types are left as they are
    return changed


def cmd_compress(args) -> int:
    pdfs = require_pdfs(args)
    quality, max_side = COMPRESS_LEVELS[args.level]
    if pdfs:
        print(f"Compression level: {args.level}\n")
    failed = 0
    for pdf in pdfs:
        try:
            reader = open_pdf(pdf)
            writer = PdfWriter(clone_from=reader)
            pictures = shrink_pictures(writer, quality, max_side)
            for page in writer.pages:
                page.compress_content_streams()  # lossless
            writer.compress_identical_objects()  # store repeated content only once
            buffer = io.BytesIO()
            writer.write(buffer)
        except PdfProblem as problem:
            print(f"  [fail] {pdf.name}: {problem}")
            failed += 1
            continue
        except Exception as error:
            print(f"  [fail] {pdf.name}: {error}")
            failed += 1
            continue

        out_path = args.output / pdf.name
        old_size, new_size = pdf.stat().st_size, len(buffer.getvalue())
        if new_size >= old_size * 0.99:
            shutil.copy2(pdf, out_path)
            print(f"  [ok]   {pdf.name}: already as small as it gets, copied as-is ({kb(old_size)})")
        else:
            out_path.write_bytes(buffer.getvalue())
            saved = 100 - new_size * 100 / old_size
            pictures_text = "1 picture" if pictures == 1 else f"{pictures} pictures"
            print(f"  [ok]   {pdf.name}: {kb(old_size)} -> {kb(new_size)}  ({saved:.0f}% smaller, "
                  f"{pictures_text} compressed)")

    if pdfs:
        print(f"\nDone: {len(pdfs) - failed} compressed, {failed} failed. Files are in: {args.output}")
    return 1 if failed else 0


def image_to_pdf_page(path: Path):
    """Open an image and return it as a one-page PDF (a pypdf page)."""
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)  # phone photos are often stored sideways
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=72, quality=95)  # 1 pixel = 1 point
    return PdfReader(buffer).pages[0]


def cmd_images(args) -> int:
    images = list_files(args.input, IMAGE_EXTENSIONS)
    if not images:
        print("No images found. Put the images in that folder, then run this again.")
        return 0

    print(f"Adding {len(images)} image(s) in this order:")
    writer = PdfWriter()
    failed = 0
    for path in images:
        try:
            image_page = image_to_pdf_page(path)
        except Exception as error:
            print(f"  [fail] {path.name}: {error}")
            failed += 1
            continue

        if args.page_size == "fit":
            writer.add_page(image_page)  # page is exactly the size of the image
        else:
            width, height = float(image_page.mediabox.width), float(image_page.mediabox.height)
            page_w, page_h = PAGE_SIZES[args.page_size]
            if width > height:
                page_w, page_h = page_h, page_w  # landscape pictures get landscape pages
            scale = min(1.0, (page_w - 2 * PAGE_MARGIN) / width, (page_h - 2 * PAGE_MARGIN) / height)
            x = (page_w - width * scale) / 2
            y = (page_h - height * scale) / 2
            page = writer.add_blank_page(width=page_w, height=page_h)
            page.merge_transformed_page(image_page, Transformation().scale(scale).translate(x, y))
        print(f"  [added] {path.name}")

    if len(writer.pages) == 0:
        print("\nNo images could be added.")
        return 1
    out_path = args.output / f"{safe_name(args.name)}.pdf"
    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"\nDone: {pages_text(len(writer.pages))} saved to {out_path}  ({kb(out_path.stat().st_size)})")
    return 1 if failed else 0


# ---------------------------------------------------------------- command line

def add_folder_options(parser, input_default, output_default):
    parser.add_argument("-i", "--input", type=Path, default=input_default,
                        help="folder to read files from (default: the input folder)")
    parser.add_argument("-o", "--output", type=Path, default=output_default,
                        help="folder to save results to (default: the output folder)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge, split, extract, compress PDFs, or turn images into a PDF.",
                                     epilog="Run a tool with --help for its options, e.g.  python pdf_tool.py split --help")
    add_folder_options(parser, INPUT_DIR, OUTPUT_DIR)
    # -i/-o also work after the tool name. SUPPRESS stops them overwriting a value given before it.
    folders = argparse.ArgumentParser(add_help=False)
    add_folder_options(folders, argparse.SUPPRESS, argparse.SUPPRESS)

    tools = parser.add_subparsers(dest="command", metavar="tool")
    p = tools.add_parser("merge", parents=[folders], help=MENU[0][1])
    p.add_argument("-n", "--name", default="merged", help="name of the merged file (default: merged)")

    p = tools.add_parser("split", parents=[folders], help=MENU[1][1])
    p.add_argument("--every", type=int, default=1, metavar="N",
                   help="pages per file (default: 1, every page on its own)")

    p = tools.add_parser("extract", parents=[folders], help=MENU[2][1])
    p.add_argument("pages", help="pages to copy, e.g. 1-3,7 or 5- (page 5 to the end)")

    p = tools.add_parser("compress", parents=[folders], help=MENU[3][1])
    p.add_argument("-l", "--level", choices=COMPRESS_LEVELS, default="medium",
                   help="how hard to compress pictures inside the PDF (default: medium)")

    p = tools.add_parser("images", parents=[folders], help=MENU[4][1])
    p.add_argument("-n", "--name", default="images", help="name of the new PDF (default: images)")
    p.add_argument("--page-size", choices=["a4", "letter", "fit"], default="a4",
                   help="page size: a4, letter, or fit (page is the size of the image). Default: a4")
    return parser


def ask_tool() -> list[str]:
    """Show the menu and return the command line for the chosen tool."""
    print("What do you want to do?")
    for number, (name, description) in enumerate(MENU, start=1):
        print(f"  {number}) {name:<9} {description}")
    while True:
        choice = input(f"Choose 1-{len(MENU)}: ").strip().lstrip("﻿")
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            break
        print(f"  Please type a number from 1 to {len(MENU)}.")
    command = MENU[int(choice) - 1][0]
    if command != "extract":
        return [command]
    while True:
        pages = input("Which pages? (for example 1-3,7  or  5-  for page 5 to the end): ").strip()
        try:
            parse_ranges(pages)
            return [command, pages]
        except ValueError as error:
            print(f"  {error}. Try again.")


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        args = parser.parse_args(sys.argv[1:] + ask_tool())
        print()
    if getattr(args, "every", 1) < 1:
        sys.exit("Error: --every must be at least 1.")

    args.input.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Looking in: {args.input}")

    tools = {"merge": cmd_merge, "split": cmd_split, "extract": cmd_extract,
             "compress": cmd_compress, "images": cmd_images}
    sys.exit(tools[args.command](args))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
