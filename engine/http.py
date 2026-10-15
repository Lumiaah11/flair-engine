"""Session HTTP polie, avec reprises et délai entre les appels."""
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

AGENT = "FlairBot/1.0 (veille d'offres personnelle; contact via GitHub)"
DELAI = 0.35
_dernier = [0.0]


def _session():
    s = requests.Session()
    reprise = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "POST"]))
    s.mount("https://", HTTPAdapter(max_retries=reprise))
    s.headers.update({"User-Agent": AGENT, "Accept": "application/json, text/html;q=0.9"})
    return s


SESSION = _session()


def _attendre():
    ecart = time.time() - _dernier[0]
    if ecart < DELAI:
        time.sleep(DELAI - ecart)
    _dernier[0] = time.time()


def get_json(url, params=None, headers=None, timeout=25):
    _attendre()
    r = SESSION.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post_json(url, corps, headers=None, timeout=25):
    _attendre()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = SESSION.post(url, json=corps, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.json()
