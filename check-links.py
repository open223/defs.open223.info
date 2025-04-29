import re
import sys

def extract_links_from_markdown(markdown_text):
    # Regular expression pattern for Markdown links
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'

    # Find all matches in the provided markdown text
    links = re.findall(link_pattern, markdown_text)

    # Extract and return the URLs (the second group from the pattern)
    return list(set([(text,url) for text, url in links if url.startswith('http')]))

def main():
    md_filename = sys.argv[1]
    html_filename = sys.argv[2]

    links = extract_links_from_markdown(open(md_filename).read())
    # ensure that all links are present in the HTML file
    print(links)
    for text,link in links:
        anchor = link.split('#', 1)[1] if '#' in link else None
        print(f"Checking link {text} - {anchor} in {html_filename}")
        if not anchor:
            print(f"ERROR: Link {link} does not contain an anchor")
        if anchor and anchor not in open(html_filename).read():
            print(f"ERROR: Link {link} not found in {html_filename}")
            sys.exit(1)

if __name__ == '__main__':
    main()
