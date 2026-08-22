import urllib.request
from html.parser import HTMLParser

class HNParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_titleline = False
        self.in_title_link = False
        self.title_text = []
        self.top_story_title = None

    def handle_starttag(self, tag, attrs):
        if self.top_story_title is not None:
            return
        attrs_dict = dict(attrs)
        if tag == 'span' and attrs_dict.get('class') == 'titleline':
            self.in_titleline = True
        elif self.in_titleline and tag == 'a':
            self.in_title_link = True

    def handle_endtag(self, tag):
        if self.top_story_title is not None:
            return
        if tag == 'a' and self.in_title_link:
            self.in_title_link = False
            self.in_titleline = False
            self.top_story_title = "".join(self.title_text).strip()
        elif tag == 'span' and self.in_titleline:
            self.in_titleline = False

    def handle_data(self, data):
        if self.in_title_link:
            self.title_text.append(data)

def main():
    url = 'https://news.ycombinator.com/'
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    parser = HNParser()
    parser.feed(html)
    if parser.top_story_title:
        print(f"Top Story: {parser.top_story_title}")
    else:
        print("Could not find the top story. Maybe the HTML structure changed.")

if __name__ == '__main__':
    main()
