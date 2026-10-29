import re

from bs4 import BeautifulSoup
from dateutil.parser import parse


class HtmlParser:

    def extract_text(self, html):

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for tag in soup([
            "script",
            "style",
            "noscript"
        ]):
            tag.decompose()

        return soup.get_text(
            separator=" ",
            strip=True
        )

    def extract_title(self, html):

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        if soup.title:
            return soup.title.get_text(
                strip=True
            )

        h1 = soup.find("h1")

        if h1:
            return h1.get_text(
                strip=True
            )

        return "Unknown Title"

    def extract_date(self, html):

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # 1. Meta tags

        meta_candidates = [

            "article:published_time",
            "publication_date",
            "publish-date",
            "date",
            "dc.date"

        ]

        for meta in soup.find_all("meta"):

            value = (
                meta.get("content")
                or ""
            )

            prop = (
                meta.get("property")
                or meta.get("name")
                or ""
            )

            if prop.lower() in [
                c.lower()
                for c in meta_candidates
            ]:

                try:
                    return parse(value)
                except:
                    pass

        # 2. time tag

        time_tag = soup.find("time")

        if time_tag:

            value = (
                time_tag.get("datetime")
                or time_tag.get_text()
            )

            try:
                return parse(value)
            except:
                pass

        # 3. fallback regex

        text = soup.get_text(
            " ",
            strip=True
        )

        patterns = [

            r"\d{4}-\d{2}-\d{2}",

            r"\d{1,2}/\d{1,2}/\d{4}",

            r"[A-Z][a-z]+ \d{1,2}, \d{4}"

        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                text
            )

            for match in matches:

                try:
                    return parse(match)
                except:
                    pass

        return None