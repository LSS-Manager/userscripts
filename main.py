from time import sleep
from typing import List, Tuple, Set
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests
import json

from utils.Scripts import Scripts

FORUM_URL = 'https://forum.leitstellenspiel.de/'

current_post_id: int = 0
visited_posts: Set[int] = set()
scripts = Scripts()

visited_posts_file = '.visited_posts.json'
scripts_file = 'scripts.json'

AttributeList = List[Tuple[str, str | None]]
TagTuple = Tuple[str, AttributeList, str]


def log(content: str):
    print(f"[{datetime.now()}] {content}")


def post_url(post_id: int) -> str:
    return f"{FORUM_URL}/index.php?thread/19176&postID={post_id}"


class DOMInterface(HTMLParser):
    def __init__(self, url: str):
        super().__init__()
        self.url = url

        self._links: List[TagTuple] = []
        self._is_thread = urlparse(self.url).query.startswith('thread')
        self._in_post = False
        self._in_post_articles = 0
        self._ready_for_post_link = False
        self._current_post_link = ''

    def handle_starttag(self, tag: str, attrs: AttributeList) -> None:
        if tag == 'a':
            self._links.append((tag, attrs, self._current_post_link))
            if self._ready_for_post_link:
                for attr, value in attrs:
                    if attr == 'href':
                        self._current_post_link = value
                        query = parse_qs(urlparse(value).query)
                        # this is because otherwise I get a warning because dict keys should be bytes according to types
                        # noinspection PyTypeChecker
                        for link in query['postID']:
                            visited_posts.add(int(link))
                        break
        if self._is_thread:
            if tag == 'article':
                if self._in_post:
                    self._in_post_articles += 1
                else:
                    for attr, value in attrs:
                        if attr == 'class' and 'wbbPost' in value.split(' '):
                            self._in_post = True
                            break
            if self._in_post and tag == 'ul':
                for attr, value in attrs:
                    if attr == 'class' and 'messageQuickOptions' in value.split(' '):
                        self._ready_for_post_link = True
                        break

    def handle_endtag(self, tag: str) -> None:
        if self._ready_for_post_link and tag == 'ul':
            self._ready_for_post_link = False
        if self._in_post and tag == 'article':
            if self._in_post_articles:
                self._in_post_articles -= 1
            else:
                self._current_post_link = ''
                self._in_post = False
                self._in_post_articles = 0

    def check_for_scripts(self):
        self.feed(requests.get(self.url).text)
        for tag, attrs, post in self._links:
            for attr, value in attrs:
                if attr == 'href' and value.endswith('.user.js'):
                    if value not in scripts:
                        scripts[value] = [post]
                        log(f"Found new script {value} at {post}")
                    elif post not in scripts[value]:
                        scripts[value].append(post)
                        log(f"Additional post for script {value}: {post}")


if __name__ == '__main__':
    try:
        with open(visited_posts_file, 'r') as file:
            stored_visited_posts = json.load(file)
            for visited_post in stored_visited_posts:
                visited_posts.add(visited_post)
    except FileNotFoundError:
        pass
    try:
        with open(scripts_file, 'r') as file:
            stored_scripts = json.load(file)
            for script in stored_scripts:
                scripts[script["url"]] = script["posts"]
    except FileNotFoundError:
        pass

    initial_scripts_len = len(scripts)
    initial_visited_len = len(visited_posts)
    current_url = ''

    log(f"Starting with {initial_visited_len} visited Posts and {initial_scripts_len} scripts.")

    try:
        while current_post_id <= 500_000:
            current_post_id += 1
            if current_post_id in visited_posts:
                continue
            log(f"Visiting: #{current_post_id}")
            DOMInterface(post_url(current_post_id)).check_for_scripts()
            visited_posts.add(current_post_id)
            log(f"Scripts: {len(scripts)}; Posts: {len(visited_posts)}")
            sleep(0.1)
            if datetime.now().minute >= 55:
                log("It is past 55 of the current hour. Aborting this script to be ready for the next scheduled run")
                break
    except ConnectionError:
        log("Ouch, a ConnectionError occurred! Aborting the crawler!")
    except KeyboardInterrupt:
        log("Hey, someone interrupted the crawler!")
    except Exception as e:
        print(e.with_traceback(e.__traceback__))
    finally:
        log(
            f"Ending with {len(visited_posts)} visited Posts. "
            f"This is {len(visited_posts) - initial_visited_len} more than before this run."
        )
        log(
            f"Ending with {len(scripts)} found Scripts. "
            f"This is {len(scripts) - initial_scripts_len} more than before this run."
        )

        log("Saving our work...")

        with open(visited_posts_file, 'w') as file:
            file.write(json.dumps(sorted(list(visited_posts))))
        with open(scripts_file, 'w') as file:
            file.write(json.dumps(scripts.json(), sort_keys=True, indent=2))

        log("Success! The progress has been saved!")
