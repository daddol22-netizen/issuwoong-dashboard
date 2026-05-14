#!/bin/bash
# 크롤링 후 GitHub 자동 push

cd /Users/daddol/클로드/news_dashboard

/usr/bin/python3 crawl_naver_news.py

/usr/bin/git add data/
/usr/bin/git diff --cached --quiet || /usr/bin/git commit -m "data: auto crawl $(date +'%Y-%m-%d %H:%M')"
/usr/bin/git push origin main
