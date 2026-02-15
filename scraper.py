#!/usr/bin/env python3
"""
Nebraska Revised Statutes — Popular Name / Short Title Scraper

Crawls the Nebraska Legislature website (or official GitHub XML repo) and
extracts every instance where a statute section includes a "popular name" or
"short title" — phrases like "This act shall be known as the ___," "may be
cited as," etc.

Two modes of operation:
  web  — Scrapes the live website at nebraskalegislature.gov using
         requests + BeautifulSoup (slower, rate-limited).
  xml  — Clones the official nelegislature/LegalDocs GitHub repo and
         parses the XML statute files directly (faster, more reliable).

Usage:
    python scraper.py                  # default: xml mode
    python scraper.py --mode web       # scrape the website
    python scraper.py --mode xml       # parse GitHub XML (default)
    python scraper.py -o results.csv   # custom output file
"""

import argparse
import csv
import logging
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://nebraskalegislature.gov"
BROWSE_STATUTES_URL = f"{BASE_URL}/laws/browse-statutes.php"
BROWSE_CHAPTERS_URL = f"{BASE_URL}/laws/browse-chapters.php"
STATUTE_URL = f"{BASE_URL}/laws/statutes.php"

GITHUB_REPO = "https://github.com/nelegislature/LegalDocs.git"
XML_CLONE_DIR = Path("LegalDocs")

REQUEST_DELAY = 1.5          # seconds between web requests
MAX_RETRIES = 3               # retry failed requests
RETRY_BACKOFF = 2.0           # exponential backoff multiplier

CSV_COLUMNS = [
    "statute_number",
    "section_title",
    "popular_name",
    "full_text_of_naming_clause",
    "url",
]

# ---------------------------------------------------------------------------
# Regex patterns for popular-name / short-title language
# ---------------------------------------------------------------------------

# The patterns are tried in order.  The first capture group should contain
# the full naming clause sentence, and the second (inner) group the act name.
# We compile a single combined pattern for efficiency.

_NAMING_PHRASES = [
    # "shall be known and may be cited as the <Name>"
    r"shall be known and may be cited as the\s+",
    # "shall be known as the <Name>"
    r"shall be known as the\s+",
    # "may be cited as the <Name>"
    r"may be cited as the\s+",
    # "known and cited as the <Name>"
    r"known and cited as the\s+",
    # "shall be cited as the <Name>"
    r"shall be cited as the\s+",
    # "This act shall be known as the <Name>"  (already covered above
    #  but list explicitly for clarity)
]

# Build a compiled pattern that captures:
#   group(0) — full match  (the naming clause)
#   group(1) — the popular name itself
_PHRASE_ALT = "|".join(_NAMING_PHRASES)
POPULAR_NAME_RE = re.compile(
    # Capture the whole sentence that contains the naming phrase.  We look
    # backwards for the start of the sentence (capital letter after period /
    # start of text) and forwards until the period.
    rf"([^.]*?(?:{_PHRASE_ALT})"       # everything up to & including the phrase
    rf"([A-Z][^.]+?))"                 # the popular name (ends at period)
    rf"\s*\.",                          # trailing period
    re.IGNORECASE | re.DOTALL,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ne-statutes")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def _clean_popular_name(name: str) -> str:
    """
    Post-process a captured popular name to trim trailing clause fragments.

    E.g. "Nebraska National Guard, which includes the Army National Guard
    and the Air National Guard" → "Nebraska National Guard"
    """
    # Cut at punctuation + continuation words, or "and shall/by/may" mid-name
    name = re.split(
        r"[,;:]\s*(?:which\b|shall\b|and\b|hereinafter\b|\()"
        r"|(?<!\bknown)\s+and\s+(?:by|shall|may|is|its|it|such)\b",
        name,
        maxsplit=1,
    )[0]
    return name.strip().rstrip(".,;:")


def _is_likely_act_name(name: str, clause: str) -> bool:
    """
    Heuristic: return True if the match looks like a genuine act / short-title
    naming rather than an incidental use of "shall be known as" (e.g. naming
    an office, tax, or fund without a legal designation).
    """
    # Strong signal: clause uses "cited as" — always a short-title provision
    if "cited as" in clause.lower():
        return True

    # The name ends with a recognised legal-designation suffix
    _SUFFIXES = re.compile(
        r"(?:Act|Code|Law|Compact|Commission|Program|Plan|System|Fund|"
        r"Initiative|Authority|Standards|Amendment|Bill of Rights|Charter|"
        r"Guard|Statutes|Amendments|Clause|Rule|Regulation|Trust|Order)\b",
        re.IGNORECASE,
    )
    if _SUFFIXES.search(name):
        return True

    # Context starts with "Sections" or "This act/section" — likely a naming
    # provision
    if re.match(
        r"(?:Sections?\s|This\s+(?:act|section))", clause, re.IGNORECASE
    ):
        return True

    # Very long captured names are almost certainly false positives
    if len(name) > 120:
        return False

    # Default: include it (err on the side of recall)
    return True


def extract_popular_names(text: str):
    """
    Return a list of (popular_name, full_clause) tuples found in *text*.
    """
    results = []
    for m in POPULAR_NAME_RE.finditer(text):
        full_clause = _clean_text(m.group(1)) + "."
        popular_name = _clean_text(m.group(2))
        popular_name = _clean_popular_name(popular_name)
        # Skip very short or clearly non-name matches
        if len(popular_name) < 3:
            continue
        if not _is_likely_act_name(popular_name, full_clause):
            continue
        results.append((popular_name, full_clause))
    return results


# ===================================================================
# WEB SCRAPER (requests + BeautifulSoup)
# ===================================================================


class WebScraper:
    """Crawls nebraskalegislature.gov to find popular-name statutes."""

    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._last_request_time = 0.0

    # -- rate limiting --------------------------------------------------

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    # -- HTTP with retries ----------------------------------------------

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                wait = RETRY_BACKOFF ** attempt
                log.warning(
                    "Request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    # -- parsing --------------------------------------------------------

    def get_chapter_numbers(self) -> list[str]:
        """Return all chapter numbers listed on the browse-statutes page."""
        log.info("Fetching chapter index …")
        resp = self._get(BROWSE_STATUTES_URL)
        soup = BeautifulSoup(resp.text, "lxml")

        chapters = []
        # Links point to browse-chapters.php?chapter=NN
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "browse-chapters.php" in href and "chapter=" in href:
                ch = href.split("chapter=")[-1].split("&")[0]
                if ch and ch not in chapters:
                    chapters.append(ch)

        log.info("Found %d chapters", len(chapters))
        return chapters

    def get_section_numbers(self, chapter: str) -> list[str]:
        """Return all statute section identifiers for a chapter."""
        log.info("Fetching sections for chapter %s …", chapter)
        resp = self._get(BROWSE_CHAPTERS_URL, params={"chapter": chapter})
        soup = BeautifulSoup(resp.text, "lxml")

        sections = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "statutes.php" in href and "statute=" in href:
                sec = href.split("statute=")[-1].split("&")[0]
                if sec and sec not in sections:
                    sections.append(sec)

        log.info("  chapter %s → %d sections", chapter, len(sections))
        return sections

    def get_statute(self, statute_id: str) -> dict | None:
        """
        Fetch a single statute page and return a dict with its metadata
        and text, or None on failure.
        """
        url = f"{STATUTE_URL}?statute={statute_id}"
        try:
            resp = self._get(STATUTE_URL, params={"statute": statute_id})
        except RuntimeError:
            log.error("Giving up on statute %s", statute_id)
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract the statute text — the site wraps the main content in a
        # <div> whose id or class varies, so we look for common containers.
        # Strategy: find the largest text block that looks like statute text.
        text_block = ""
        title = ""

        # Try common selectors the NE legislature site has used:
        for selector in [
            "div.mb-3",            # current layout
            "div#content",
            "div.col-sm-9",
            "div.content-text",
            "div#statute-text",
            "article",
            "div.card-body",
        ]:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) > 50:
                text_block = el.get_text(" ", strip=True)
                break

        # Fallback: grab the <body> text minus nav/footer
        if not text_block:
            body = soup.find("body")
            if body:
                # Remove nav and footer elements
                for tag in body.find_all(["nav", "footer", "header", "script", "style"]):
                    tag.decompose()
                text_block = body.get_text(" ", strip=True)

        # Try to get the page <title> or <h> heading for the section title
        h_tag = soup.find(["h1", "h2", "h3"])
        if h_tag:
            title = _clean_text(h_tag.get_text())
        elif soup.title:
            title = _clean_text(soup.title.get_text())

        return {
            "statute_number": statute_id,
            "section_title": title,
            "text": _clean_text(text_block),
            "url": url,
        }

    # -- main crawl -----------------------------------------------------

    def scrape(self, output_file: str = "nebraska_popular_names.csv"):
        """Crawl all statutes and write matches to *output_file*."""
        chapters = self.get_chapter_numbers()
        results = []

        for ch_idx, chapter in enumerate(chapters, 1):
            sections = self.get_section_numbers(chapter)
            for sec_idx, section_id in enumerate(sections, 1):
                log.info(
                    "[ch %s  %d/%d | sec %d/%d]  %s",
                    chapter,
                    ch_idx,
                    len(chapters),
                    sec_idx,
                    len(sections),
                    section_id,
                )
                statute = self.get_statute(section_id)
                if statute is None:
                    continue

                matches = extract_popular_names(statute["text"])
                for popular_name, clause in matches:
                    results.append(
                        {
                            "statute_number": statute["statute_number"],
                            "section_title": statute["section_title"],
                            "popular_name": popular_name,
                            "full_text_of_naming_clause": clause,
                            "url": statute["url"],
                        }
                    )
                    log.info("  ✓ FOUND: %s → %s", section_id, popular_name)

        _write_csv(results, output_file)
        return results


# ===================================================================
# XML PARSER  (GitHub nelegislature/LegalDocs)
# ===================================================================


class XMLScraper:
    """
    Parses the official Nebraska Legislature XML statutes from the
    nelegislature/LegalDocs GitHub repository.
    """

    def __init__(self, clone_dir: Path = XML_CLONE_DIR):
        self.clone_dir = clone_dir
        self.statutes_dir = clone_dir / "Statutes"

    # -- repository management ------------------------------------------

    def ensure_repo(self):
        """Clone the repo (shallow) if it doesn't already exist locally."""
        if self.statutes_dir.exists():
            log.info("XML repo already present at %s", self.clone_dir)
            return

        log.info("Cloning %s (shallow) …", GITHUB_REPO)
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                GITHUB_REPO,
                str(self.clone_dir),
            ],
            check=True,
        )
        # Only check out the Statutes directory to save bandwidth.
        subprocess.run(
            ["git", "sparse-checkout", "set", "Statutes"],
            cwd=str(self.clone_dir),
            check=True,
        )
        log.info("Repository cloned successfully")

    # -- XML parsing ----------------------------------------------------

    @staticmethod
    def _xml_text(element) -> str:
        """Recursively extract all text from an XML element."""
        return "".join(element.itertext())

    def parse_file(self, xml_path: Path) -> dict | None:
        """
        Parse a single statute XML file.  Returns a dict with
        statute_number, section_title, text, url — or None if the file
        cannot be parsed.
        """
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as exc:
            log.warning("XML parse error in %s: %s", xml_path, exc)
            return None

        root = tree.getroot()
        amend = root.find(".//amendatorysection")
        if amend is None:
            return None

        statute_no_el = root.find(".//statuteno")
        catchline_el = root.find(".//catchline")
        statute_number = (
            statute_no_el.text.strip() if statute_no_el is not None and statute_no_el.text else ""
        )
        section_title = (
            _clean_text(self._xml_text(catchline_el))
            if catchline_el is not None
            else ""
        )

        # Fallback: get statute number from the amendatorysection attribute
        if not statute_number:
            statute_number = amend.get("statutenumber", "")

        # Collect all <para> text (the actual statute body).
        paras = root.findall(".//amendatorysection/para")
        # Also look for <para> inside nested <section> if not found
        if not paras:
            paras = root.findall(".//para")
        full_text = " ".join(_clean_text(self._xml_text(p)) for p in paras)

        url = f"{STATUTE_URL}?statute={statute_number}" if statute_number else ""

        return {
            "statute_number": statute_number,
            "section_title": section_title,
            "text": full_text,
            "url": url,
        }

    # -- main crawl -----------------------------------------------------

    def scrape(self, output_file: str = "nebraska_popular_names.csv"):
        """Parse all XML statute files and write matches to *output_file*."""
        self.ensure_repo()

        xml_files = sorted(self.statutes_dir.rglob("*.xml"))
        log.info("Found %d XML statute files", len(xml_files))

        results = []
        files_processed = 0

        for xml_path in xml_files:
            files_processed += 1
            if files_processed % 500 == 0:
                log.info(
                    "Progress: %d / %d files  (%d matches so far)",
                    files_processed,
                    len(xml_files),
                    len(results),
                )

            statute = self.parse_file(xml_path)
            if statute is None or not statute["text"]:
                continue

            matches = extract_popular_names(statute["text"])
            for popular_name, clause in matches:
                results.append(
                    {
                        "statute_number": statute["statute_number"],
                        "section_title": statute["section_title"],
                        "popular_name": popular_name,
                        "full_text_of_naming_clause": clause,
                        "url": statute["url"],
                    }
                )
                log.info(
                    "  FOUND: %s — %s", statute["statute_number"], popular_name
                )

        log.info(
            "Done.  Processed %d files, found %d popular names.",
            files_processed,
            len(results),
        )
        _write_csv(results, output_file)
        return results


# ===================================================================
# CSV output
# ===================================================================


def _write_csv(rows: list[dict], output_file: str):
    """Write results to a CSV file."""
    # Sort by statute number for readability
    def _sort_key(row):
        parts = row["statute_number"].split("-", 1)
        try:
            return (int(parts[0]), parts[1] if len(parts) > 1 else "")
        except ValueError:
            return (9999, row["statute_number"])

    rows.sort(key=_sort_key)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Wrote %d rows to %s", len(rows), output_file)


# ===================================================================
# CLI
# ===================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Nebraska Revised Statutes for popular names / short titles.",
    )
    parser.add_argument(
        "--mode",
        choices=["web", "xml"],
        default="xml",
        help=(
            "Scraping mode.  'xml' (default) clones the official GitHub XML "
            "repo — faster and more reliable.  'web' crawls the live website "
            "using requests + BeautifulSoup."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="nebraska_popular_names.csv",
        help="Output CSV file (default: nebraska_popular_names.csv)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=REQUEST_DELAY,
        help=f"Seconds between web requests in web mode (default: {REQUEST_DELAY})",
    )
    parser.add_argument(
        "--clone-dir",
        type=str,
        default=str(XML_CLONE_DIR),
        help=f"Directory for the cloned XML repo (default: {XML_CLONE_DIR})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.mode == "web":
        scraper = WebScraper(delay=args.delay)
    else:
        scraper = XMLScraper(clone_dir=Path(args.clone_dir))

    results = scraper.scrape(output_file=args.output)

    print(f"\nDone — found {len(results)} popular name(s).")
    print(f"Results written to: {args.output}")

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
