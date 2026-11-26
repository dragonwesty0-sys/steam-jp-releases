const get = id => document.getElementById(id);
const filters = ['query', 'genre', 'sort'].map(get);
const money = new Intl.NumberFormat('ja-JP', {style: 'currency', currency: 'JPY'});
const pageSize = 24;
let limit = pageSize;
let catalog;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function gameCard(game) {
  const card = node('article', '', 'game');
  const cover = game.image && /^https:\/\/[^/]+\.steamstatic\.com\//.test(game.image)
    ? node('img') : node('div', '', 'cover');
  if (cover.tagName === 'IMG') {
    cover.src = game.image;
    cover.alt = '';
    cover.loading = 'lazy';
  }
  const content = node('div', '', 'game-content');
  const tags = node('div', '', 'tags');
  tags.append(...(game.genres.length ? game.genres : ['その他']).map(genre => node('span', genre, 'tag')));
  const link = node('a', 'Steamで詳細を見る ↗');
  link.href = 'https://store.steampowered.com/app/' + game.id + '/?l=japanese';
  link.setAttribute('aria-label', game.title + 'をSteamで見る');
  const price = game.price === null ? '価格未確認' : game.price === 0 ? '無料' : money.format(game.price);
  content.append(node('h3', game.title), tags, node('p', '発売 ' + game.date, 'meta'),
    node('p', price, 'price'), node('p', '価格確認日 ' + game.checked, 'meta'), link);
  card.append(cover, content);
  return card;
}

function render() {
  const [query, genre, sort] = filters.map(control => control.value);
  const needle = query.normalize('NFKC').trim().toLocaleLowerCase('ja');
  const games = catalog.games.filter(game =>
    (!genre || (genre === 'その他' ? !game.genres.length : game.genres.includes(genre))) &&
    game.title.normalize('NFKC').toLocaleLowerCase('ja').includes(needle));
  if (sort !== 'latest') {
    const direction = sort === 'price-up' ? 1 : -1;
    games.sort((a, b) => (a.price === null) - (b.price === null) ||
      (a.price === null ? 0 : direction * (a.price - b.price)));
  }
  get('summary').textContent = games.length + '件 · データ更新 ' + catalog.updated +
    (games.length ? ' · ' + Math.min(limit, games.length) + '件表示' : ' · 該当するゲームはありません');
  get('games').replaceChildren(...games.slice(0, limit).map(gameCard));
  get('more').hidden = games.length <= limit;
}

try {
  const response = await fetch('./games.json');
  if (!response.ok) throw Error('catalog unavailable');
  catalog = await response.json();
  const genres = [...new Set(catalog.games.flatMap(game => game.genres.length ? game.genres : ['その他']))]
    .sort((a, b) => a.localeCompare(b, 'ja'));
  filters[1].append(...genres.map(genre => new Option(genre, genre)));
  filters.forEach(control => control.addEventListener('input', () => { limit = pageSize; render(); }));
  get('more').addEventListener('click', () => {
    const firstNew = limit;
    limit += pageSize;
    render();
    get('games').children[firstNew]?.querySelector('a')?.focus();
  });
  render();
} catch {
  get('summary').textContent = 'ゲーム一覧の取得に失敗しました。ページを再読み込みしてください。';
}
