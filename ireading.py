#coding=utf-8
import functools
import json
import re
import tornado.ioloop
import tornado.web

import requests
from weibo import APIClient
from constant import APP_ID, APP_SECRET, VALID_POS_TAG


def pre_proc(text):
    try:
    # UCS-4
        high_points = re.compile(u'[\U00010000-\U0010ffff]')
    except re.error:
        # UCS-2
        high_points = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')
    link = re.compile(r'http://t\.cn/\w{7}')
    emotions = re.compile(r'\[.{1,8}\]')
    text = emotions.sub('', text)
    text = high_points.sub('', text)
    text = link.sub('', text)
    return text


def _create_client(oauth_token=None, expires=None):
    client = APIClient(APP_ID, APP_SECRET, 'http://anid.sinaapp.com/callback')
    if oauth_token and expires:
        client.set_access_token(oauth_token, expires)
    return client


def auth_check(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        signed_request = self.get_argument("signed_request", "null")
        client = _create_client()
        data = client.parse_signed_request(signed_request)
        if data is not None:
            uid = data.get('uid', '')
            auth_token = data.get('oauth_token', '')
            if uid and auth_token:
                expires = data.expires
                client.set_access_token(auth_token, expires)
                kwargs['client'] = client
                kwargs['uid'] = uid
                kwargs['signed_request'] = signed_request
                return func(self, *args, **kwargs)
        return self.write(APP_ID)

    return wrap


def get_pos(word, words):
    for i, _w in enumerate(words):
        if _w['word'] == word['word']:
            return i
    return -1


def get_sem(text):
    res = requests.post('http://anid.sinaapp.com/fenci',
                        {'context': text})
    res = json.loads(res.content)
    words = []
    for word in res:
        if word['word_tag'] in VALID_POS_TAG:
            p = get_pos(word, words)
            if p == -1:
                word['rate'] = 1
                words.append(word)
            else:
                words[p]['rate'] += 1
    return words


def get_books(q):
    books = []
    res = requests.get('https://api.douban.com/v2/book/search?q=%s&count=10' % q.encode('utf-8'))
    res = json.loads(res.content)
    for b in res['books']:
        books.append({
            'id': b.get('id', ''),
            'title': b.get('title', ''),
            'subtitle': b.get('subtitle', ''),
            'author': b.get('author', []),
            'url': b.get('url', ''),
            'image': b.get('images', {}).get('small', ''),
            'rate': b.get('rating', {}).get('average', '5')
        })
    return books


class MainHandler(tornado.web.RequestHandler):
    @auth_check
    def get(self, *args, **kwargs):
        client = kwargs['client']
        uid = kwargs['uid']

        data = client.statuses.home_timeline.get(count=30, page=1, feature=1, trim_user=1)

        till_id = data['next_cursor']

        context = []
        print len(data['statuses'])
        for status in data['statuses']:
            text = pre_proc(status['text'])
            print text
            context.append(text)

        # 分词
        words = get_sem("\n".join(context))

        #过滤
        # words = filter(lambda word: word['rate'] > 2, words)

        #排序
        words = sorted(words, key=lambda x: x['rate'], reverse=True)

        #搜索
        books = []
        for w in words[:10]:
            books.append(get_books(w['word']))
            # break

        self.write(json.dumps(books))


application = tornado.web.Application([
    (r"/", MainHandler),
])

if __name__ == "__main__":
    application.listen(13982)
    tornado.ioloop.IOLoop.instance().start()
    # print get_sem('这是测试')
    # pass