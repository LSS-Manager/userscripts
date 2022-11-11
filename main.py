from time import sleep
from typing import List, Tuple
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests

FORUM_URL = 'https://forum.leitstellenspiel.de/'
QUEUE_MAX_SIZE = 5000
VISITED_MAX_SIZE = 100_000

queue: set[str] = {f'{FORUM_URL}index.php?board/22-scripte-und-zusatzprogramme/'}
visited: set[str] = set()
scripts: set[Tuple[str, str]] = set()

visited_list_file = '.visited.txt'
scripts_list_file = 'scripts.txt'

AttributeList = List[Tuple[str, str | None]]
TagTuple = Tuple[str, AttributeList, str]


def log(content: str):
    print(f"[{datetime.now()}] {content}")


def check_add_url_to_queue(url: str) -> bool:
    if len(queue) > QUEUE_MAX_SIZE:
        return False
    if not url.startswith(FORUM_URL):
        return False
    parsed = urlparse(url)
    if not parsed.query.startswith('board') and not parsed.query.startswith('thread'):
        return False
    if parsed.fragment.startswith('codeLine'):
        return False
    query = parse_qs(parsed.query)
    if 'postID' in query:
        return False
    return True


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

    def __iter__(self):
        self.feed(requests.get(self.url).text)
        for tag, attrs, post in self._links:
            for attr, value in attrs:
                if attr == 'href' and check_add_url_to_queue(value):
                    yield value
                if attr == 'href' and value.endswith('.user.js'):
                    scripts.add((post, value))
                    log(f"Found script {value} at {post}")


if __name__ == '__main__':
    try:
        with open(visited_list_file, 'r') as file:
            for line in file.readlines():
                visited.add(line.strip())
    except FileNotFoundError:
        pass
    try:
        with open(scripts_list_file, 'r') as file:
            line = ''
            for line in file.readlines():
                post_link, script_link = line.strip().split(',')
                scripts.add((post_link, script_link))
    except FileNotFoundError:
        pass

    initial_scripts_len = len(scripts)
    initial_visited_len = len(visited)
    current_url = ''

    log(f"Starting with {len(visited)} visited URLs and {len(scripts)} scripts.")

    try:
        while len(queue):
            current_url = queue.pop()
            log(f"Visiting: #{len(visited) + 1} {current_url}")
            for link in DOMInterface(current_url):
                if link not in visited and link != current_url:
                    queue.add(link)
            visited.add(current_url)
            log(f"Queue: {len(queue)}, Scripts: {len(scripts)}")
            # abort when 100 scripts found or checked 1000 URLs to avoid too many requests per run
            if len(scripts) >= initial_scripts_len + 100 or len(visited) >= initial_visited_len + 1000:
                break
            sleep(0.1)
    except ConnectionError:
        log("Ouch, a ConnectionError occurred! Aborting the crawler!")
    except KeyboardInterrupt:
        log("Hey, someone interrupted the crawler!")
    finally:
        log(
            f"Ending with {len(visited)} visited URLs. "
            f"This is {len(visited) - initial_visited_len} more than before this run."
        )
        log(
            f"Ending with {len(scripts)} found Scripts. "
            f"This is {len(scripts) - initial_scripts_len} more than before this run."
        )

        log("Saving our work...")

        with open(visited_list_file, 'w') as file:
            visited_urls = []
            for visited_url in visited:
                if visited_url != current_url:
                    visited_urls.append(visited_url)
            file.write('\n'.join(visited_urls[-VISITED_MAX_SIZE:]) + '\n' + current_url)
        with open(scripts_list_file, 'w') as file:
            scripts_csv = []
            scripts_list = list(scripts)
            for post_link, script_link in sorted(list(scripts), key=lambda s: s[1]):
                scripts_csv.append(f"{post_link},{script_link}")
            file.write('\n'.join(scripts_csv))

        log("Success! The progress has been saved!")
