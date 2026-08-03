![TikTok RSS Logo](https://tiktokrss.conoroneill.com/favicon-32x32.png)
# TikTok RSS Using GitHub Actions

Generate usable RSS feeds from TikTok using GitHub Actions and GitHub Pages.


> **NOTE août 2026 (ce fork) : plus besoin de `MS_TOKEN`.**
> La librairie Python `TikTokApi` ne fonctionne plus : depuis mi-juillet 2026,
> l'endpoint de listing des vidéos d'un profil exige une signature qu'elle ne
> produit pas, et renvoie une réponse vide quel que soit le msToken.
> `postprocessing.py` utilise désormais [yt-dlp](https://github.com/yt-dlp/yt-dlp),
> maintenu en continu : plus de cookie, plus de Playwright, plus de secret.
> Le secret `MS_TOKEN` du dépôt peut être supprimé, il n'est plus lu.

## Setup for GitHub Actions
* To get your own instance running
    * Fork this repo
    * Make sure to enable Actions in the Actions tab
    * Enable GitHub Pages for your new repo
    * In Settings > Actions > General, set Workflow permissions to **Read and write**
      (l'Action commit les flux générés)
    * Edit config.py to change `ghPagesURL` and `ghRawURL` to your own repo URLs
    * Add the TikTok usernames that you like to subscriptions.csv

* It's set to run once every 4 hours and generates one RSS XML file per user in the rss output directory.
* Si l'Action passe au rouge, c'est que TikTok a encore changé quelque chose :
  la première chose à essayer est de relancer le workflow (yt-dlp est réinstallé
  à chaque exécution et récupère les correctifs upstream automatiquement).

## Running locally as an alternative
* You need Python installed
* Then setup with:

```bash
python -m venv venv
source venv/bin/activate     # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

* Then run each time with:

```bash
source venv/bin/activate
python postprocessing.py
git commit -a -m "latest RSS"
git push origin main
```

## Feed Reading
* You then subscribe to each feed in [Feedly](https://www.feedly.com) or another feed reader using a GitHub Pages URL. Those URLs are constructed like so. E.g.:

    * TikTok User = iamtabithabrown
    * XML File = rss/iamtabithabrown.xml
    * Feedly Subscription URL = https://conoro.github.io/tiktok-rss-flat/rss/iamtabithabrown.xml
    * (Or in my case where I've set a custom domain for the GitHub Pages project called tiktokrss.conoroneill.com, the URL is https://tiktokrss.conoroneill.com/rss/iamtabithabrown.xml)

## Acknowledgements
This fork uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to extract user video
metadata from TikTok and generate RSS feeds for each user you are interested in.
The original version used the unofficial
[TikTokPy library](https://github.com/davidteather/TikTok-Api), which no longer
returns profile video lists.

Logo was created using the TikTok and RSS [Font Awesome](https://fontawesome.com/license/free) icons via CC BY 4.0 License

Copyright Conor O'Neill, 2021-2024 (conor@conoroneill.com)

License Apache 2.0

