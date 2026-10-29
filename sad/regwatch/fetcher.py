import requests


class Fetcher:

    def __init__(self, timeout: int = 30):

        self.timeout = timeout

    def get(self, url: str) -> str:

        response = requests.get(
            url,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response.text