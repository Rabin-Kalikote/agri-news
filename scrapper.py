import json
import re
import os
from bs4 import BeautifulSoup
import requests
import datetime
from flask import Flask
from nlp import Tokenizer
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, String

app = Flask('agrinews')
app.app_context().push()

#db connection
if db_link := os.environ.get('DATABASE_URL'):
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = db_link #production
else:
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3' #for postgres -- 'postgresql://postgres:123456@localhost/agrinews'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

replace_dict = {"1": "१", "2": "२", "3": "३", "4": "४",
                "5": "५", "6": "६", "7": "७", "8": "८", "9": "९", "0": "०"}

#db models
class Article(db.Model):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    headline = Column(String(500), unique=True)
    description = Column(Text)
    image_url = Column(Text)
    article_url = Column(Text)
    date = Column(String(100))
    source = Column(String(50))
    content = Column(Text)

    def __init__(self, headline, description, image_url, article_url, date, source, content):
        self.headline = headline
        self.description = description
        self.image_url = image_url
        self.article_url = article_url
        self.date = date
        self.source = source
        self.content = content

#db functions
def add_to_db(data_dict):
    headline = data_dict.get('headline')
    description = data_dict.get('description')
    image_url = data_dict.get('image_url')
    article_url = data_dict.get('article_url')
    date = data_dict.get('date')
    source = data_dict.get('source')
    content = data_dict.get('content')

    if db.session.query(Article).filter(Article.headline == headline).count() == 0:
        data = Article(headline, description, image_url,
                       article_url, date, source, content)
        db.session.add(data)
        db.session.commit()
        return 0
    return 1


def read_from_db(query=''):
    if query:
        search = "%{}%".format(query)
        articles = Article.query.filter(Article.headline.like(search)).all()[-75:]
        print(articles)
    else:
        articles = Article.query.all()[-75:]
    collection = []
    for article in articles:
        d = dict()
        d['id'] = article.id
        d['source'] = article.source
        d['image_url'] = article.image_url

        d['article_url'] = article.article_url
        d['headline'] = article.headline
        d['description'] = article.description
        d['date'] = article.date
        d['content'] = article.content
        collection.append(d)
    return collection

def find_by_id(id):
    article = Article.query.filter_by(id=id).first()
    if article:
        d = dict()
        d['id'] = article.id
        d['source'] = article.source
        d['image_url'] = article.image_url
        d['article_url'] = article.article_url
        d['headline'] = article.headline
        d['description'] = article.description
        d['date'] = article.date
        d['content'] = article.content
        return d
    return None

#scrapper object to scrape data from different news sites
class Scrapper:
    def __init__(self, site_url, article_identifier: list, img_identifier: list = ['img'],
                 img_get_identifier='src', url_identifier: list = ['a'],
                 headline_identifier: list = ['h4'], description_identifier: list = ['p'], base_url='', source='',
                 content_identifier: list = [], content_identifier_pos=0):
        self.base_url = base_url
        self.source = source
        url_parser = re.search(r'^(https?://(.*?)\.\w*)/?', site_url)
        if url_parser:
            self.base_url = self.base_url or url_parser.group(1)
            self.source = self.source or url_parser.group(2)
        self.site_url = site_url
        self.article_identifier = article_identifier
        self.img_identifier = img_identifier
        self.img_get_identifier = img_get_identifier
        self.url_identifier = url_identifier
        self.headline_identifier = headline_identifier
        self.description_identifier = description_identifier
        self.content_identifier = content_identifier
        self.content_identifier_pos = content_identifier_pos

    def scrape(self, till_date=''):
        response = requests.get(self.site_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            self.soup = soup
            articles = soup.find_all(*self.article_identifier)

            for article in articles:
                d = dict()
                try:
                    d['source'] = self.source
                    d['image_url'] = self.img_url_scraper(article)
                    print(d['source'])
                    print(d['image_url'])

                    #article url are relative or absolute
                    if (url := self.article_url_scraper(article)).startswith('/'):
                        d['article_url'] = self.base_url + url
                    else:
                        d['article_url'] = url

                    d['headline'] = self.headline_scraper(article)

                    #scrapping description if available
                    if self.description_identifier:
                        d['description'] = self.description_scraper(article)
                    else:
                        d['description'] = ""

                    #checking if the article is related to agriculture
                    if not Tokenizer().is_krishi(d['description'] + d['headline']):
                        continue

                    #scrapping content if available
                    if self.content_identifier:
                        d['content'] = ContentScraper(
                            d['article_url'], self.content_identifier, self.content_identifier_pos, self).scrape()
                    else:
                        d['content'] = ""

                    #scrapping date if available
                    if date := self.date_scraper(article):
                        d['date'] = date
                    else:
                        d['date'] = ""

                except:
                    continue

                # add to db if not already present
                if d:
                    response_db = add_to_db(d)
                    if response_db:
                        break

    def img_url_scraper(self, article):
        return article.find(*self.img_identifier).get(self.img_get_identifier)

    def article_url_scraper(self, article):
        return article.find(*self.url_identifier).get('href')

    def headline_scraper(self, article):
        return article.find(*self.headline_identifier).text.strip()

    def description_scraper(self, article):
        return article.find(*self.description_identifier).text.strip()

    def date_scraper(self, article):
        pass

#scrapper object custom to specific news site
class RatopatiScrapper(Scrapper):
    def date_scraper(self, article):
        return (self.soup.find('span', {'class': 'date'})).text.strip()

class KrishiDailyScrapper(Scrapper):
    def date_scraper(self, article):
        return 'वि सं २०८१ जेष्ठ ९ बुधवार' #hardcoded date

class OnlineKhabarScrapper(Scrapper):
    def date_scraper(self, article):
        return self.content_soup.find('div', {'class': 'ok-news-post-hour'}).text.split('गते')[0].strip()

class SancharKendraScrapper(Scrapper):
    def date_scraper(self, article):
        date = str(datetime.date.today())
        for x,y in replace_dict.items():
            date = date.replace(x,y)
        return date

#scrapper object to scrape content from news article
class ContentScraper:
    def __init__(self, url, content_identifier, content_identifier_pos, parent):
        self.url = url
        self.content_identifier = content_identifier
        self.content_identifier_pos = content_identifier_pos
        self.parent = parent

    def scrape(self):
        response = requests.get(self.url)

        content = ""
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            self.parent.content_soup = soup
            if self.content_identifier_pos:
                content_stuff = soup.find_all(*self.content_identifier)[self.content_identifier_pos - 1]
            else:
                content_stuff = soup.find(*self.content_identifier)
            for p in content_stuff.find_all('p'):
                content += p.text
                if not (content.endswith('\r\n\n') or content.endswith('\r\n\n ')):
                    content += '\r\n\n'
        return content.strip()


def clear_database():
    db.session.query(Article).delete()
    db.session.commit()


#cronjob to scrape data from different news sites
def scrape_websites():
    websites = [
        SancharKendraScrapper('https://sancharkendra.com/archives/category/news', ['div', {'class': 'flxi skcatpg'}],
                              description_identifier=False, content_identifier=['div', {'class': 'post-content'}],
                              content_identifier_pos=3),
        OnlineKhabarScrapper('http://onlinekhabar.com/content/news', ['div', {'class': 'span-4'}],
                             headline_identifier=['h2', {'class': 'ok-news-title-txt'}], description_identifier=False,
                             content_identifier=['div', {'class': 'ok18-single-post-content-wrap'}]),
        RatopatiScrapper('https://ratopati.com/category/news', ['div', {'class': 'columnnews'}],
                         headline_identifier = ['h3', {'class': 'news-title'}], description_identifier=False,
                         content_identifier=['div', {'class': 'the-content'}]),
        KrishiDailyScrapper("https://krishidaily.com/category/news", ['div', {'class': 'td_module_wrap'}],
                            headline_identifier=['h3', {'class': 'td-module-title'}], img_get_identifier='data-img-url',
                            description_identifier=['div', {'class': 'td-excerpt'}],
                            url_identifier=['a', {'class': 'td-image-wrap'}], content_identifier=['div', {'class': 'td-post-content'}])
    ]

    for website in websites:
        try:
            website.scrape()
        except:
            continue

    print('Scraped successfully!')
