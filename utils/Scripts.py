from typing import List, Union, Tuple, Set


class Script:
    def __init__(self, url: str, posts: Union[List[str], Tuple[str, ...], Set[str], None] = None):
        self.url: str = url
        self.posts: Set[str] = set()
        if posts is not None:
            for post in posts:
                self.posts.add(post)

    def json(self):
        return {
            "url": self.url,
            "posts": sorted(list(self.posts))
        }

    def append(self, url: str):
        self.posts.add(url)

    def __contains__(self, url: str):
        return url in self.posts


class Scripts:
    def __init__(self):
        self._scripts: List[Script] = []

    def __getitem__(self, url: str):
        for script in self._scripts:
            if script.url == url:
                return script

    def __setitem__(self, url: str, posts: List[str]):
        if url in self:
            pass
        self._scripts.append(Script(url, posts))

    def __contains__(self, url: str) -> bool:
        for script in self._scripts:
            if script.url == url:
                return True
        return False

    def __iter__(self):
        for script in self._scripts:
            yield script

    def __len__(self):
        return len(self._scripts)

    def json(self):
        scripts = []
        for script in sorted(self._scripts, key=lambda s: s.url):
            scripts.append(script.json())
        return scripts
