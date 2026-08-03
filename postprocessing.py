"""
Genere un flux RSS par compte TikTok listé dans subscriptions.csv.

Pourquoi ce script a été réécrit (aout 2026) :
  L'ancienne version utilisait la librairie Python `TikTokApi` + un cookie
  `msToken` + Playwright. Depuis mi-juillet 2026, l'endpoint web de listing des
  videos d'un profil (`/api/post/item_list/`) exige une signature que cette
  librairie ne produit plus : la reponse revient vide, quel que soit le msToken.
  On passe donc par `yt-dlp`, qui est maintenu en continu et suit les
  changements de TikTok. Plus de msToken, plus de navigateur, plus de secret.

Sortie : un fichier `rss/<user>.xml` par compte, au MEME format qu'avant, pour
que le bot Discord qui lit ces flux n'ait rien a changer :
  - <link>https://tiktok.com/@user/video/<id>  (le bot en extrait l'ID stable)
  - <description> contient <img src="..."> = la miniature (vignette 9:16)
  - <pubDate> = date de publication de la video

Les miniatures servies par le CDN TikTok sont signees et expirent en ~3 jours.
On les telecharge donc dans `thumbnails/<user>/` et on les commit, comme avant,
pour que l'URL dans le flux reste valable indefiniment.

En cas d'echec (0 video recuperee), le script sort en code 1 SANS ecraser le
flux existant : l'Action GitHub echoue et devient visiblement rouge.
"""

import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from feedgen.feed import FeedGenerator
from yt_dlp import YoutubeDL

import config

ROOT = Path(__file__).resolve().parent
RSS_DIR = ROOT / "rss"
THUMBS_DIR = ROOT / "thumbnails"

# Editer config.py pour changer ces valeurs.
GH_RAW_URL = config.ghRawURL.rstrip("/") + "/"
VIDEO_COUNT = getattr(config, "videoCount", 10)
FEED_AUTHOR = getattr(config, "feedAuthor", {"name": "tiktok-rss"})

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def fetch_videos(user, count, attempts=3):
    """Derniere(s) video(s) d'un profil via yt-dlp, en mode 'flat' (1 requete).

    Le mode flat suffit : il renvoie deja id, titre, description, timestamp et
    les miniatures. Pas besoin d'ouvrir chaque video.
    """
    opts = {
        "extract_flat": True,
        "playlistend": count,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Une extraction en echec doit remonter, pas etre ignoree en silence.
        "ignoreerrors": False,
    }
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.tiktok.com/@{user}", download=False)
            entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
            if entries:
                return entries
            last_err = "aucune video dans la reponse"
        except Exception as err:  # noqa: BLE001 - on reessaie puis on remonte
            last_err = str(err)
        print(f"  tentative {attempt}/{attempts} echouee : {last_err}")
        if attempt < attempts:
            time.sleep(5 * attempt)
    raise RuntimeError(last_err or "extraction impossible")


def cover_url(entry):
    """URL de la miniature verticale (cover) d'une video."""
    thumbs = entry.get("thumbnails") or []
    for wanted in ("cover", "originCover", "dynamicCover"):
        for t in thumbs:
            if t.get("id") == wanted and t.get("url"):
                return t["url"]
    for t in thumbs:
        if t.get("url"):
            return t["url"]
    return entry.get("thumbnail") or ""


def local_thumbnail(user, url):
    """Telecharge la miniature une seule fois et renvoie son URL GitHub raw.

    Renvoie l'URL CDN d'origine si le telechargement echoue (mieux qu'aucune
    image, meme si le lien signe expirera au bout de quelques jours).
    """
    if not url:
        return ""
    segments = [s for s in urlparse(url).path.split("/") if s]
    if not segments:
        return url
    subpath = f"thumbnails/{user}/screenshot_{segments[-1]}.jpg"
    dest = ROOT / subpath
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.tiktok.com/"})
            with urlopen(req, timeout=30) as res:
                data = res.read()
            if not data:
                raise RuntimeError("image vide")
            dest.write_bytes(data)
        except Exception as err:  # noqa: BLE001 - repli sur l'URL CDN
            print(f"  miniature non recuperee ({err}) : on garde l'URL TikTok")
            return url
    return GH_RAW_URL + subpath


def build_feed(user, entries):
    fg = FeedGenerator()
    fg.id(f"https://www.tiktok.com/@{user}")
    fg.title(f"{user} TikTok")
    fg.author(FEED_AUTHOR)
    fg.link(href=f"https://www.tiktok.com/@{user}", rel="alternate")
    fg.logo(GH_RAW_URL + "tiktok-rss.png")
    fg.subtitle(f"Dernieres videos TikTok de {user}")
    fg.link(href=f"{GH_RAW_URL}rss/{user}.xml", rel="self")
    fg.language("fr")

    updated = None
    # Du plus recent au plus ancien : le bot retrie de son cote, mais un flux
    # ordonne reste plus lisible pour un lecteur RSS classique.
    for entry in sorted(entries, key=lambda e: e.get("timestamp") or 0, reverse=True):
        link = f"https://tiktok.com/@{user}/video/{entry['id']}"
        desc = (entry.get("title") or entry.get("description") or "").strip()

        fe = fg.add_entry(order="append")
        fe.id(link)
        fe.link(href=link)
        fe.title(desc[:255] if desc else "Sans titre")

        ts = entry.get("timestamp")
        if ts:
            published = datetime.fromtimestamp(int(ts), timezone.utc)
            fe.published(published)
            fe.updated(published)
            updated = max(published, updated) if updated else published

        content = desc[:255] if desc else "Sans description"
        thumb = local_thumbnail(user, cover_url(entry))
        if thumb:
            content = f'<img src="{thumb}" / > {content}'
        fe.description(content)

    fg.updated(updated or datetime.now(timezone.utc))
    return fg


def main():
    RSS_DIR.mkdir(exist_ok=True)
    THUMBS_DIR.mkdir(exist_ok=True)

    with open(ROOT / "subscriptions.csv", newline="") as f:
        users = [row["username"].strip() for row in csv.DictReader(f, fieldnames=["username"]) if row["username"].strip()]

    if not users:
        print("subscriptions.csv est vide : rien a faire.")
        return 1

    failed = []
    for user in users:
        print(f"Compte '{user}'")
        try:
            entries = fetch_videos(user, VIDEO_COUNT)
        except Exception as err:  # noqa: BLE001
            print(f"  ECHEC : {err}")
            print("  le flux existant est conserve tel quel.")
            failed.append(user)
            continue
        build_feed(user, entries).rss_file(str(RSS_DIR / f"{user}.xml"), pretty=True)
        newest = max((e.get("timestamp") or 0) for e in entries)
        newest_txt = datetime.fromtimestamp(newest, timezone.utc).isoformat() if newest else "date inconnue"
        print(f"  OK : {len(entries)} video(s), la plus recente du {newest_txt}")

    if failed:
        print(f"\nEchec pour : {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
