# Nebraska Statute Popular Name Index

A free, open-source tool for searching and browsing the popular names of
Nebraska Revised Statutes. Data is scraped from the official
[Nebraska Legislature website](https://nebraskalegislature.gov/laws/browse-statutes.php).

## Features

- **Search** — find statutes by popular name or statute number
- **Browse** — alphabetical listing of all 900+ popular names
- **Links** — every entry links directly to the official statute text
- **Fast** — lightweight Flask app backed by SQLite

## Quick Start

```bash
# Clone the repo
git clone https://github.com/whaijf851/Nebraska-Popular-Name-Tool.git
cd Nebraska-Popular-Name-Tool

# Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the web app
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

On first launch the app automatically imports `nebraska_popular_names.csv`
into a local SQLite database (`popular_names.db`). The database file is
excluded from version control and will be rebuilt if deleted.

## Refreshing the Data

To re-scrape the statutes from the Nebraska Legislature site:

```bash
python scraper.py
```

Then delete `popular_names.db` and restart the app to rebuild the database
from the new CSV.

## Project Structure

```
app.py                        Flask application
templates/
  base.html                   Shared layout (Bootstrap 5)
  home.html                   Search page
  browse.html                 Alphabetical browse page
  about.html                  About page
scraper.py                    Statute scraper
nebraska_popular_names.csv    Scraped data
requirements.txt              Python dependencies
```

## Disclaimer

This is an independent community project. It is **not** affiliated with or
endorsed by the Nebraska Legislature or any government agency. Always verify
statute text on the [official site](https://nebraskalegislature.gov).

## License

This project is open source. Contributions and corrections are welcome.
