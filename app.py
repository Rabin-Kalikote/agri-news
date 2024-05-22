from scrapper import *
from apscheduler.schedulers.background import BackgroundScheduler
from flask import render_template, request

scheduler = BackgroundScheduler()
scheduler.daemonic = True
scheduler.add_job(scrape_websites, 'interval', minutes=3, id='cornjob')
scheduler.start()

print(scheduler)

@app.route("/")
def home():
  query = request.args.get('query')
  news_articles = read_from_db(query)
  return render_template('index.html', news_articles = news_articles)

@app.route("/articles/<int:id>")
def show(id):
  article = find_by_id(id)
  return render_template('show.html', article = article)


@app.route('/scrape_manually')
def scrape_manually():
    scrape_websites()
    return "<br><br><h1 align='center'>Scrapped manually.</h1>"


if __name__ == '__main__':
    app.run(debug=True)
