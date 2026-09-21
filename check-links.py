"""Verify that every defs.open223.info anchor linked from the publication
markdown exists in the generated HTML.

Links to other hosts are counted but not checked -- only our own anchors are
this repository's responsibility.

Usage: python check-links.py <publication.md> <index.html>
"""

import re
import sys

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SITE = "defs.open223.info"


def extract_links(markdown_text):
    """Return the unique (text, url) pairs for http(s) links in the markdown."""
    return sorted(
        {
            (text, url)
            for text, url in LINK_PATTERN.findall(markdown_text)
            if url.startswith("http")
        }
    )


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python check-links.py <publication.md> <index.html>")
    md_filename, html_filename = sys.argv[1], sys.argv[2]

    with open(md_filename) as f:
        links = extract_links(f.read())
    with open(html_filename) as f:
        html = f.read()

    site_links = [(text, url) for text, url in links if SITE in url]

    errors = []
    for text, url in site_links:
        _, _, anchor = url.partition("#")
        if not anchor:
            errors.append(f"{url} ({text}) has no anchor")
        elif f'id="{anchor}"' not in html:
            errors.append(f"{url} ({text}) -> #{anchor} missing from {html_filename}")

    print(
        f"Checked {len(site_links)} {SITE} links "
        f"({len(links) - len(site_links)} external links skipped)"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        sys.exit(f"{len(errors)} broken link(s)")
    print("All links resolve")


if __name__ == "__main__":
    main()
