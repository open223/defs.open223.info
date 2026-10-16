"""Record and verify the anchors the publication document links to.

The document's links and the site's anchors are blank-node labels
canonicalized over a whole graph, so they agree only when both sides use the
same graph.  Nothing about a wrong-but-valid graph makes the build fail, so
`make sync` records the set of anchors the document links (extract) and CI
asserts the built page defines every one of them (check).

Usage:
    python anchors.py extract 223p_publication.md publication-anchors.txt
    python anchors.py check publication-anchors.txt index.html
"""

import re
import sys
from pathlib import Path

# Markdown inline links, e.g. [Equipment](https://host/defs#s223:Equipment).
LINK = re.compile(r"\((https?://[^)\s]+#[^)\s]+)\)")

# Canonical blank-node anchors.  These exist only on this site, which is what
# makes them usable to identify the document's link base.
CANONICAL = re.compile(r"^b-c14n\d+$")


def sort_key(anchor: str):
    """Sort digit runs numerically so b-c14n9 precedes b-c14n10."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", anchor)]


def extract(markdown_file: str, manifest_file: str) -> None:
    """Write every anchor the document links on this site, one per line."""
    links = LINK.findall(open(markdown_file).read())
    targets = [link.rsplit("#", 1) for link in links]

    # The document's base URL is configurable upstream (S223_DOC_HOST), and has
    # already moved once, so derive it from the links rather than hardcoding a
    # host: whichever base carries the canonical anchors is this site.
    bases = {base for base, fragment in targets if CANONICAL.match(fragment)}
    if len(bases) != 1:
        sys.exit(
            f"{markdown_file}: expected one base URL carrying b-c14n anchors, "
            f"found {sorted(bases) or 'none'}"
        )
    base = bases.pop()

    anchors = sorted(
        {fragment for b, fragment in targets if b == base}, key=sort_key
    )
    with open(manifest_file, "w") as f:
        f.write(f"# anchors linked from {Path(markdown_file).name} at {base}\n")
        f.write("# regenerate with 'make sync'; checked by 'make check-anchors'\n")
        f.writelines(f"{anchor}\n" for anchor in anchors)
    print(f"Wrote {manifest_file} with {len(anchors)} anchors from {base}")


def check(manifest_file: str, html_file: str) -> None:
    """Fail if the built page is missing any anchor the document links."""
    wanted = [
        line.strip()
        for line in open(manifest_file)
        if line.strip() and not line.startswith("#")
    ]
    defined = set(re.findall(r'id="([^"]+)"', open(html_file).read()))

    missing = [anchor for anchor in wanted if anchor not in defined]
    if missing:
        shown = ", ".join(missing[:10])
        more = f", and {len(missing) - 10} more" if len(missing) > 10 else ""
        sys.exit(
            f"{html_file} is missing {len(missing)} of {len(wanted)} anchors "
            f"the publication links: {shown}{more}\n"
            f"ontologies/223p.ttl is probably not the graph the document was "
            f"built from; re-run 'make sync' against that build."
        )
    print(f"All {len(wanted)} publication anchors resolve in {html_file}")


if __name__ == "__main__":
    command, *args = sys.argv[1:] or [""]
    if command == "extract" and len(args) == 2:
        extract(*args)
    elif command == "check" and len(args) == 2:
        check(*args)
    else:
        sys.exit(__doc__)
