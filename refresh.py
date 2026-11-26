"""Refresh the catalog from the public Japanese-language Steam search."""
import json
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

URL = 'https://store.steampowered.com/search/?sort_by=Released_DESC&category1=998&supportedlang=japanese&ndl=1&cc=jp&l=japanese'
CATALOG = Path(__file__).parent / 'games.json'
JST = timezone(timedelta(hours=9))
GENRES = {19:'アクション', 21:'アドベンチャー', 122:'RPG', 599:'シミュレーション',
          9:'ストラテジー', 701:'スポーツ', 699:'レース', 597:'カジュアル',
          1664:'パズル', 1667:'ホラー', 492:'インディー'}
FIELDS = {'title': 'title', 'search_released': 'date', 'discount_final_price': 'price'}
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class SteamSearch(HTMLParser):
    def __init__(self):
        super().__init__()
        self.row = None
        self.stack = []
        self.games = []

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        classes = attrs.get('class', '').split()
        if tag == 'a' and 'search_result_row' in classes:
            appid = attrs.get('data-ds-appid', '')
            if not appid.isascii() or not appid.isdecimal() or attrs.get('data-ds-itemkey') != f'App_{appid}':
                return
            ids = json.loads(attrs.get('data-ds-tagids', '[]'))
            self.row = {'id': appid, 'genres': [name for key, name in GENRES.items() if key in ids]}
            self.stack = [('a', None)]
            return
        if self.row is None:
            return
        field = next((FIELDS[c] for c in classes if c in FIELDS), None)
        if tag not in VOID:
            self.stack.append((tag, field))
        if tag == 'img' and any('capsule' in (src := attrs.get(key, '')) and src.startswith('https://') for key in ('src', 'data-src')):
            self.row.setdefault('image', src)

    def handle_data(self, text):
        if self.row is None:
            return
        field = next((f for _, f in reversed(self.stack) if f), None)
        if field:
            self.row[field] = self.row.get(field, '') + text

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if tag == 'a':
            self.games.append(self.row)
            self.row = None
            self.stack = []
        else:
            match = next((i for i in range(len(self.stack) - 1, 0, -1) if self.stack[i][0] == tag), None)
            if match is not None:
                del self.stack[match:]


def parse(html, now):
    parser = SteamSearch()
    parser.feed(html)
    for row in parser.games:
        date = re.fullmatch(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', row.get('date', '').strip())
        title = row.get('title', '').strip()
        if not title or not date:
            continue
        try:
            released = datetime(*map(int, date.groups()), tzinfo=JST).date()
        except ValueError:
            continue
        if released > now.astimezone(JST).date():
            continue
        price = row.get('price', '').strip()
        yen = re.fullmatch(r'[¥￥]\s*([\d,]+)', price)
        amount = int(yen[1].replace(',', '')) if yen else (0 if price in {'無料', '無料プレイ', 'Free', 'Free To Play'} else None)
        yield {**row, 'title': title, 'date': released.isoformat(), 'price': amount,
               'checked': now.astimezone(JST).date().isoformat()}


def refresh(html):
    now = datetime.now(timezone.utc)
    fresh = list(parse(html, now))
    if not fresh or not any(game['price'] is not None for game in fresh):
        raise RuntimeError('Unexpected Steam response; catalog unchanged.')
    saved = json.loads(CATALOG.read_text()) if CATALOG.exists() else {'games': []}
    games = {game['id']: game for game in saved['games']}
    games.update((game['id'], game) for game in fresh)
    result = sorted(games.values(), key=lambda game: (game['date'], int(game['id'])), reverse=True)
    payload = {'updated': now.astimezone(JST).date().isoformat(), 'games': result}
    temp = CATALOG.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(CATALOG)
    print(f'{len(fresh)} refreshed, {len(result)} total')


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 2:
        refresh(Path(sys.argv[1]).read_text(encoding='utf-8'))
    else:
        with urlopen(Request(URL, headers={'Accept-Language': 'ja'}), timeout=30) as response:
            refresh(response.read().decode('utf-8'))
