# Nebraska Popular Name Tool

A free, open-source tool for searching and browsing the popular names of
Nebraska Revised Statutes. Data is scraped from the official
[Nebraska Legislature website](https://nebraskalegislature.gov/laws/browse-statutes.php).

## Features

- **Search** — find statutes by popular name or statute number
- **Browse** — alphabetical listing of all 900+ popular names
- **Links** — every entry links directly to the official statute text
- **Static site** — no server needed, just HTML/CSS/JS

## View the Site

Open `docs/index.html` in your browser, or visit the live site on GitHub Pages.

## Refreshing the Data

To re-scrape the statutes from the Nebraska Legislature site:

```bash
pip install -r requirements.txt
python scraper.py
```

Then rebuild the static site:

```bash
python build_static.py
```

The updated HTML files will be in `docs/`.

## Development Setup

To enable the pre-commit secret scanner (blocks accidental commits of API keys, passwords, etc.):

```bash
git config core.hooksPath .githooks
```

## Project Structure

```
scraper.py                    Statute scraper
nebraska_popular_names.csv    Scraped data (944 statutes)
build_static.py               Generates static HTML site from CSV
docs/                         The website (deploy this folder)
  index.html                  Search page
  browse.html                 Browse page
  about.html                  About page
  favicon.svg                 Site icon
requirements.txt              Python dependencies (for scraper only)
```

## Disclaimer

This is an independent community project. It is **not** affiliated with or
endorsed by the Nebraska Legislature or any government agency. Always verify
statute text on the [official site](https://nebraskalegislature.gov).

## License

This project is open source. Contributions and corrections are welcome.
