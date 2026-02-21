#!/usr/bin/env python3
"""Build a static HTML site from the Nebraska popular names CSV.

Usage:
    python3 build_static.py

Reads nebraska_popular_names.csv and generates a docs/ folder with:
    - index.html   (search page)
    - browse.html  (alphabetical / chapter browse)
    - about.html   (about page)
    - favicon.svg

The docs/ folder can be deployed to GitHub Pages or any static host.
"""

import csv
import html
import json
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "nebraska_popular_names.csv")
DOCS_DIR = os.path.join(SCRIPT_DIR, "docs")

FAVICON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="8" y="38" width="48" height="22" rx="2" fill="#1a3a5c"/>
  <rect x="14" y="30" width="36" height="10" rx="1" fill="#1a3a5c"/>
  <rect x="24" y="14" width="16" height="18" rx="1" fill="#1a3a5c"/>
  <rect x="29" y="6" width="6" height="10" fill="#1a3a5c"/>
  <circle cx="32" cy="5" r="3" fill="#c5a44e"/>
  <rect x="27" y="18" width="3" height="5" rx="0.5" fill="#fafaf8"/>
  <rect x="34" y="18" width="3" height="5" rx="0.5" fill="#fafaf8"/>
  <rect x="17" y="33" width="3" height="4" rx="0.5" fill="#fafaf8"/>
  <rect x="24" y="33" width="3" height="4" rx="0.5" fill="#fafaf8"/>
  <rect x="37" y="33" width="3" height="4" rx="0.5" fill="#fafaf8"/>
  <rect x="44" y="33" width="3" height="4" rx="0.5" fill="#fafaf8"/>
</svg>
"""


def load_data():
    """Read the CSV and return a list of statute dicts sorted by popular_name."""
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    rows.sort(key=lambda r: r["popular_name"].upper())
    return rows


def esc(text):
    """HTML-escape a string."""
    return html.escape(text, quote=True)


# ---------------------------------------------------------------------------
# Shared HTML pieces
# ---------------------------------------------------------------------------

HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
        rel="stylesheet"
        integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YcnS/1p8EfIMR+EVB2sFNyp9a3z0Bw7IARz"
        crossorigin="anonymous">
  <style>
    body {{
      background-color: #fafaf8;
      color: #2c2c2c;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .navbar {{
      background-color: #1a3a5c;
    }}
    .navbar-brand, .nav-link {{
      color: #e8e4dc !important;
    }}
    .nav-link:hover {{
      color: #fff !important;
    }}
    .nav-link.active {{
      font-weight: bold;
      color: #fff !important;
    }}
    h1, h2, h3 {{
      font-family: Georgia, "Times New Roman", serif;
    }}
    .search-box {{
      max-width: 640px;
      margin: 0 auto;
    }}
    .hero {{
      background: linear-gradient(rgba(26, 58, 92, 0.72), rgba(26, 58, 92, 0.85)),
                  url('https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Nebraska_State_Capitol_from_W_1.JPG/1200px-Nebraska_State_Capitol_from_W_1.JPG');
      background-size: cover;
      background-position: center top;
      color: #fff;
      padding: 3rem 1rem 2.5rem;
    }}
    .hero h1 {{
      font-size: 2.2rem;
      font-weight: 700;
      text-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }}
    .hero p {{
      color: #ddd;
    }}
    .quick-jump {{
      max-width: 480px;
      margin: 0 auto;
    }}
    .quick-jump select {{
      font-family: Georgia, "Times New Roman", serif;
      border: 2px solid #1a3a5c;
      cursor: pointer;
    }}
    .popular-tags a {{
      display: inline-block;
      padding: 0.3rem 0.75rem;
      margin: 0.25rem;
      border: 1px solid #1a3a5c;
      border-radius: 999px;
      font-size: 0.85rem;
      text-decoration: none;
      color: #1a3a5c;
      transition: all 0.15s;
    }}
    .popular-tags a:hover {{
      background-color: #1a3a5c;
      color: #fff;
    }}
    .view-toggle .btn {{
      font-size: 0.85rem;
    }}
    .view-toggle .btn.active {{
      background-color: #1a3a5c;
      border-color: #1a3a5c;
      color: #fff;
    }}
    .browse-layout {{
      display: flex;
      gap: 1rem;
    }}
    .browse-main {{
      flex: 1;
      min-width: 0;
    }}
    .jump-to-sidebar {{
      position: sticky;
      top: 1rem;
      align-self: flex-start;
      text-align: center;
      padding: 0.5rem 0.25rem;
      line-height: 1.1;
    }}
    .jump-to-sidebar .jump-label {{
      font-weight: bold;
      font-size: 0.8rem;
      color: #555;
      margin-bottom: 0.25rem;
    }}
    .jump-to-sidebar a {{
      display: block;
      padding: 1px 0.4rem;
      font-size: 0.85rem;
      font-weight: bold;
      color: #5a1a1a;
      text-decoration: none;
    }}
    .jump-to-sidebar a:hover {{
      text-decoration: underline;
      color: #1a3a5c;
    }}
    .statute-entry {{
      margin-bottom: 0.6rem;
    }}
    .statute-entry .entry-name {{
      font-weight: bold;
      color: #2c2c2c;
    }}
    .statute-entry .entry-name a {{
      color: #2c2c2c;
      text-decoration: none;
    }}
    .statute-entry .entry-name a:hover {{
      text-decoration: underline;
      color: #1a3a5c;
    }}
    .statute-entry .entry-details {{
      padding-left: 2rem;
      color: #555;
      font-size: 0.92rem;
    }}
    footer {{
      border-top: 1px solid #ddd;
      color: #777;
      font-size: 0.85rem;
    }}
    a {{
      color: #1a3a5c;
    }}
  </style>
</head>
<body>
"""


def navbar(active):
    """Return the navbar HTML. *active* is 'search', 'browse', or 'about'."""
    def cls(name):
        return "nav-link active" if name == active else "nav-link"

    return f"""\
<nav class="navbar navbar-expand-md mb-4">
  <div class="container">
    <a class="navbar-brand" href="index.html">NE Statute Names</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
            data-bs-target="#navContent" aria-controls="navContent"
            aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navContent">
      <ul class="navbar-nav ms-auto">
        <li class="nav-item">
          <a class="{cls('search')}" href="index.html">Search</a>
        </li>
        <li class="nav-item">
          <a class="{cls('browse')}" href="browse.html">Browse</a>
        </li>
        <li class="nav-item">
          <a class="{cls('about')}" href="about.html">About</a>
        </li>
      </ul>
    </div>
  </div>
</nav>
"""


FOOTER = """\
<footer class="container text-center py-3">
  <p>Nebraska Statute Popular Name Index &middot; Built from public data &middot;
     <a href="about.html">About this project</a></p>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
        crossorigin="anonymous"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_index(rows):
    """Build index.html (search page)."""
    total = len(rows)

    # Build the quick-jump options
    options = ['<option value="" selected>Jump to a statute&hellip; ({} titles)</option>'.format(total)]
    for r in rows:
        options.append(
            '<option value="{}">{}</option>'.format(esc(r["url"]), esc(r["popular_name"]))
        )
    options_html = "\n      ".join(options)

    # Embed statute data as JSON for client-side search
    search_data = json.dumps(
        [
            {
                "popular_name": r["popular_name"],
                "statute_number": r["statute_number"],
                "start_section": r["start_section"],
                "end_section": r["end_section"],
                "url": r["url"],
            }
            for r in rows
        ],
        ensure_ascii=False,
    )

    popular_searches = [
        ("Uniform Commercial Code", "Uniform+Commercial+Code"),
        ("Insurance", "Insurance"),
        ("Consumer Protection", "Consumer+Protection"),
        ("Employment", "Employment"),
        ("Tort Claims", "Tort+Claims"),
        ("Community Development", "Community+Development"),
        ("Water", "Water"),
        ("Education", "Education"),
    ]
    tags_html = "\n      ".join(
        f'<a href="#" onclick="doSearch(\'{q}\'); return false;">{label}</a>'
        for label, q in popular_searches
    )

    page = HEAD.format(title="Nebraska Statute Popular Name Tool")
    page += navbar("search")
    page += f"""\
<main class="container mb-5">
<div class="hero text-center rounded mb-4">
  <h1 class="mb-2">Nebraska Popular Name Tool</h1>
  <p>Find Nebraska laws by their commonly known names</p>

  <div class="search-box mt-4 mb-3">
    <div class="input-group input-group-lg">
      <input type="text" class="form-control" id="searchInput"
             placeholder="e.g. Uniform Commercial Code, Consumer Protection&hellip;"
             aria-label="Search statutes"
             autofocus>
      <button class="btn btn-light" type="button" id="searchBtn"
              style="color: #1a3a5c; font-weight: 600;">
        Search
      </button>
    </div>
  </div>

  <div class="quick-jump mt-3">
    <select class="form-select" id="quickJump"
            aria-label="Jump to a statute by popular name"
            onchange="if(this.value) window.location.href=this.value">
      {options_html}
    </select>
  </div>
</div>

<p class="text-center text-muted mb-4" style="max-width: 700px; margin: 0 auto;">
  Search or browse <strong>{total}</strong> Nebraska Revised Statutes by popular name.
  Each entry links directly to the full text on the
  <a href="https://nebraskalegislature.gov" target="_blank" rel="noopener">official Nebraska Legislature website</a>.
</p>

<div id="resultsArea">
  <div class="text-center mt-3" id="defaultContent">
    <p class="text-muted mb-2">Try a search:</p>
    <div class="popular-tags">
      {tags_html}
    </div>
    <p class="mt-3 text-muted">Or <a href="browse.html">browse all {total} popular names</a> alphabetically.</p>
  </div>
</div>
</main>

<script>
var STATUTES = {search_data};

function doSearch(query) {{
  document.getElementById('searchInput').value = query.replace(/\\+/g, ' ');
  runSearch();
}}

function runSearch() {{
  var q = document.getElementById('searchInput').value.trim().toLowerCase();
  var area = document.getElementById('resultsArea');
  var defContent = document.getElementById('defaultContent');

  if (!q) {{
    defContent.style.display = '';
    area.querySelectorAll('.search-result').forEach(function(el) {{ el.remove(); }});
    return;
  }}

  defContent.style.display = 'none';
  area.querySelectorAll('.search-result').forEach(function(el) {{ el.remove(); }});

  var results = STATUTES.filter(function(s) {{
    return s.popular_name.toLowerCase().indexOf(q) !== -1 ||
           s.statute_number.toLowerCase().indexOf(q) !== -1;
  }});

  var countP = document.createElement('p');
  countP.className = 'text-muted mb-3 search-result';
  if (results.length > 0) {{
    countP.innerHTML = results.length + ' result' + (results.length !== 1 ? 's' : '') +
      ' for <strong>&ldquo;' + q.replace(/</g,'&lt;') + '&rdquo;</strong>';
    area.appendChild(countP);

    results.forEach(function(s) {{
      var div = document.createElement('div');
      div.className = 'statute-entry search-result';
      div.innerHTML = '<div class="entry-name"><a href="' + s.url + '">' +
        s.popular_name.replace(/</g,'&lt;') + '</a></div>' +
        '<div class="entry-details">&sect;&nbsp;' + s.start_section +
        '&ndash;' + s.end_section + ' (' + s.statute_number + ')</div>';
      area.appendChild(div);
    }});
  }} else {{
    countP.className = 'text-center text-muted mt-4 search-result';
    countP.innerHTML = 'No results found for <strong>&ldquo;' +
      q.replace(/</g,'&lt;') + '&rdquo;</strong>. Try a different search term.';
    area.appendChild(countP);
  }}
}}

document.getElementById('searchBtn').addEventListener('click', runSearch);
document.getElementById('searchInput').addEventListener('keydown', function(e) {{
  if (e.key === 'Enter') runSearch();
}});
</script>
"""
    page += FOOTER
    return page


def build_browse(rows):
    """Build browse.html."""
    # Group alphabetically
    letters = sorted(set(r["popular_name"][0].upper() for r in rows))

    # Group by chapter
    chapters = {}
    for r in sorted(rows, key=lambda r: (
        int(r["statute_number"].split("-")[0]) if r["statute_number"].split("-")[0].isdigit() else 9999,
        r["statute_number"],
    )):
        chap = r["statute_number"].split("-")[0] if "-" in r["statute_number"] else "Other"
        chapters.setdefault(chap, []).append(r)
    sorted_chapters = sorted(chapters.keys(), key=lambda c: int(c) if c.isdigit() else 9999)

    # Build alphabetical entries
    alpha_entries = []
    current_letter = ""
    for r in rows:
        first = r["popular_name"][0].upper()
        if first != current_letter:
            current_letter = first
            alpha_entries.append(
                f'<h3 id="letter-{first}" class="mt-4 mb-2 border-bottom pb-1" '
                f'style="color: #5a1a1a;">{first}</h3>'
            )
        alpha_entries.append(
            f'<div class="statute-entry">'
            f'<div class="entry-name"><a href="{esc(r["url"])}">{esc(r["popular_name"])}</a></div>'
            f'<div class="entry-details">&sect;&nbsp;{esc(r["start_section"])}&ndash;'
            f'{esc(r["end_section"])} ({esc(r["statute_number"])})</div></div>'
        )

    # Build chapter entries
    chapter_entries = []
    for chap in sorted_chapters:
        chapter_entries.append(
            f'<h3 id="chapter-{chap}" class="mt-4 mb-2 border-bottom pb-1" '
            f'style="color: #5a1a1a;">Chapter {esc(chap)}</h3>'
        )
        for r in chapters[chap]:
            chapter_entries.append(
                f'<div class="statute-entry">'
                f'<div class="entry-name"><a href="{esc(r["url"])}">{esc(r["popular_name"])}</a></div>'
                f'<div class="entry-details">&sect;&nbsp;{esc(r["start_section"])}&ndash;'
                f'{esc(r["end_section"])} ({esc(r["statute_number"])})</div></div>'
            )

    alpha_sidebar = "\n".join(f'<a href="#letter-{l}">{l}</a>' for l in letters)
    chapter_sidebar = "\n".join(f'<a href="#chapter-{c}">{c}</a>' for c in sorted_chapters)

    page = HEAD.format(title="Browse &mdash; Nebraska Statute Popular Names")
    page += navbar("browse")
    page += f"""\
<main class="container mb-5">
<h1 class="mb-3" style="color: #5a1a1a; font-size: 1.6rem; text-transform: uppercase; letter-spacing: 0.5px;">Popular Name Tool</h1>

<p class="mb-4">
  The Popular Name Tool enables you to search or browse the Nebraska Revised Statutes
  Table of Acts Cited by Popular Name. {len(rows)} statutes with popular names
  are currently indexed. You may also <a href="index.html">search by keyword</a>.
</p>

<div class="view-toggle btn-group mb-4" role="group" aria-label="View mode">
  <button class="btn btn-outline-secondary active" id="btnAlpha"
          onclick="showView('alpha')">A&ndash;Z</button>
  <button class="btn btn-outline-secondary" id="btnChapter"
          onclick="showView('chapter')">By Chapter</button>
</div>

<div id="viewAlpha">
  <div class="browse-layout">
    <div class="browse-main">
      {"".join(alpha_entries)}
    </div>
    <div class="jump-to-sidebar">
      <div class="jump-label">Jump to:</div>
      {alpha_sidebar}
    </div>
  </div>
</div>

<div id="viewChapter" style="display: none;">
  <div class="browse-layout">
    <div class="browse-main">
      {"".join(chapter_entries)}
    </div>
    <div class="jump-to-sidebar">
      <div class="jump-label">Jump to:</div>
      {chapter_sidebar}
    </div>
  </div>
</div>

<p class="text-center mt-4"><a href="#">Back to top</a></p>

<script>
function showView(view) {{
  document.getElementById('viewAlpha').style.display = view === 'alpha' ? '' : 'none';
  document.getElementById('viewChapter').style.display = view === 'chapter' ? '' : 'none';
  document.getElementById('btnAlpha').classList.toggle('active', view === 'alpha');
  document.getElementById('btnChapter').classList.toggle('active', view === 'chapter');
}}
</script>
</main>
"""
    page += FOOTER
    return page


def build_about():
    """Build about.html."""
    page = HEAD.format(title="About &mdash; Nebraska Statute Popular Names")
    page += navbar("about")
    page += """\
<main class="container mb-5">
<div class="row justify-content-center">
  <div class="col-lg-8">
    <h1 class="mb-4">About This Project</h1>

    <p>
      The <strong>Nebraska Statute Popular Name Index</strong> is a free,
      open-source reference tool that helps you find Nebraska statutes by
      their commonly known names.
    </p>

    <h5 class="mt-4">What are "popular names"?</h5>
    <p>
      Many Nebraska statutes include a section that gives the act a short,
      easy-to-remember name &mdash; for example, the <em>Uniform Commercial
      Code</em> or the <em>Nebraska Potato Development Act</em>. These
      popular names are how lawyers, legislators, and the public typically
      refer to the law, but there has not always been a single, searchable
      index of them.
    </p>

    <h5 class="mt-4">Where does the data come from?</h5>
    <p>
      The data is scraped directly from the
      <a href="https://nebraskalegislature.gov/laws/browse-statutes.php"
         target="_blank" rel="noopener">Nebraska Legislature&rsquo;s official
      statute website</a>. Each entry links back to the authoritative text on
      that site. The scraper source code is included in the repository.
    </p>

    <h5 class="mt-4">Is this an official government resource?</h5>
    <p>
      <strong>No.</strong> This is an independent, community project. It is
      not affiliated with, endorsed by, or maintained by the Nebraska
      Legislature or any government agency. Always verify the current text of
      a statute on the
      <a href="https://nebraskalegislature.gov" target="_blank"
         rel="noopener">official Nebraska Legislature website</a>.
    </p>

    <h5 class="mt-4">Open source</h5>
    <p>
      The entire project &mdash; scraper, data, and this web application
      &mdash; is open source and available on
      <a href="https://github.com/whaijf851/Nebraska-Popular-Name-Tool"
         target="_blank" rel="noopener">GitHub</a>.
      Contributions, corrections, and suggestions are welcome.
    </p>
  </div>
</div>
</main>
"""
    page += FOOTER
    return page


def main():
    rows = load_data()
    print(f"Loaded {len(rows)} statutes from CSV")

    # Create docs/ directory
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    os.makedirs(DOCS_DIR)

    # Write favicon
    with open(os.path.join(DOCS_DIR, "favicon.svg"), "w") as f:
        f.write(FAVICON_SVG)

    # Generate pages
    for filename, content in [
        ("index.html", build_index(rows)),
        ("browse.html", build_browse(rows)),
        ("about.html", build_about()),
    ]:
        path = os.path.join(DOCS_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Built {filename}")

    print(f"\nDone! Static site is in docs/")
    print("You can open docs/index.html directly in your browser,")
    print("or deploy the docs/ folder to GitHub Pages or any web host.")


if __name__ == "__main__":
    main()
