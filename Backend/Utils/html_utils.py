"""Extração de texto de HTML sem dependências dos services."""
from html.parser import HTMLParser
import re


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.ignored += 1
        elif tag in {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr', 'section'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'template'} and self.ignored:
            self.ignored -= 1
        elif not self.ignored:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def html_text(html):
    parser = TextExtractor()
    parser.feed((html or '')[:120000])
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()[:10000]
