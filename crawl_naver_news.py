#!/usr/bin/env python3
"""네이버 뉴스 랭킹 크롤러 - 매일 오전 7시 자동 실행"""

import re
import json
import urllib.request
from datetime import datetime
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

STOPWORDS = {
    # 조사/접속사
    '이', '가', '을', '를', '은', '는', '의', '에', '에서', '으로', '로', '와', '과',
    '한', '하는', '있는', '있다', '했다', '했습니다', '한다', '하고', '되는', '되어',
    '이다', '수', '등', '및', '더', '이번', '지난', '오늘', '내일', '올해', '지금',
    '관련', '대한', '위한', '그', '이', '저', '것', '들', '이후', '통해', '대해',
    '위해', '따라', '속보', '단독', '종합', '오후', '오전', '지난해', '올해',
    # 뉴스 클리셰 (토픽 키워드로 부적합)
    '결렬', '손상', '의한', '추락에', '사후조정', '발표', '확인', '진행', '예정',
    '진술', '조사', '결과', '입장', '상황', '최종', '이후', '관련자', '당국',
    '전망', '계획', '방침', '대응', '조치', '처리', '논의', '검토', '부분',
    '나머지', '이번에', '이날', '당시', '사실', '문제', '경우', '내용', '일부',
    '이유', '이미', '아직', '다시', '만약', '결국', '하지만', '그러나', '또한',
}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.read().decode('euc-kr', errors='replace')


def extract_titles(html: str) -> list[dict]:
    """언론사명과 기사 제목/링크를 함께 추출"""
    section_pattern = r'class="rankingnews_box[^"]*"(.*?)(?=class="rankingnews_box|</section>)'
    press_pattern = r'class="rankingnews_name">([^<]+)<'
    # <a> 태그 전체를 캡처해서 href와 텍스트 동시에 추출
    full_a_pattern = r'(<a\b[^>]*\bclass="list_title[^"]*"[^>]*>)([^<]+)<'

    results = []
    for sec in re.findall(section_pattern, html, re.DOTALL):
        press_match = re.findall(press_pattern, sec)
        press = press_match[0].strip() if press_match else "기타"

        for rank, m in enumerate(re.finditer(full_a_pattern, sec), 1):
            if rank > 5:
                break
            tag, title = m.group(1), m.group(2).strip()
            href = re.search(r'\bhref="([^"]+)"', tag)
            link = href.group(1) if href else ""
            if link and link.startswith("/"):
                link = "https://news.naver.com" + link
            results.append({
                "press": press,
                "title": title,
                "rank_in_press": rank,
                "link": link,
            })
    return results


def cluster_topics(articles: list[dict], top_n: int = 5) -> list[dict]:
    """키워드 빈도 기반으로 핫토픽 클러스터링"""
    keyword_to_articles: dict[str, list] = {}

    for art in articles:
        words = re.findall(r'[가-힣]{2,}', art['title'])
        for w in words:
            if w not in STOPWORDS:
                keyword_to_articles.setdefault(w, [])
                keyword_to_articles[w].append(art)

    # 등장 횟수로 정렬, 중복 기사 제거
    keyword_counts = {k: len({a['title'] for a in v}) for k, v in keyword_to_articles.items()}
    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

    seen_titles: set[str] = set()
    topics = []

    for keyword, count in top_keywords:
        if len(topics) >= top_n:
            break
        if count < 3:
            break

        related = [
            a for a in keyword_to_articles[keyword]
            if a['title'] not in seen_titles
        ]
        if not related:
            continue

        # 대표 기사 선정 (가장 짧고 명확한 제목)
        related_sorted = sorted(related, key=lambda a: len(a['title']))
        representative = related_sorted[0]

        for a in related:
            seen_titles.add(a['title'])

        topics.append({
            "rank": len(topics) + 1,
            "keyword": keyword,
            "count": count,
            "representative_title": representative['title'],
            "representative_link": representative['link'],
            "press": representative['press'],
            "related_articles": [{"title": a['title'], "link": a['link'], "press": a['press']} for a in related[:5]],
            "related_titles": [a['title'] for a in related[:5]],
        })

    return topics


def categorize(keyword: str, titles: list[str]) -> str:
    all_text = keyword + " " + " ".join(titles)
    if any(w in all_text for w in ['주식', '코스피', '코스닥', '투자', '상장', '증시', '펀드', '채권']):
        return "경제/투자"
    if any(w in all_text for w in ['삼성', '하이닉스', '반도체', 'AI', '기술', '스마트폰', '전자']):
        return "산업/테크"
    if any(w in all_text for w in ['파업', '노조', '노사', '임금', '성과급', '직장', '근로']):
        return "노동/파업"
    if any(w in all_text for w in ['사망', '추락', '사고', '실종', '구조', '경찰', '검시', '부검']):
        return "사건/사고"
    if any(w in all_text for w in ['미국', '중국', '이란', '러시아', '전쟁', '핵', '외교', '국제']):
        return "국제"
    if any(w in all_text for w in ['대통령', '정부', '국회', '장관', '여당', '야당', '선거', '정치']):
        return "정치"
    if any(w in all_text for w in ['드라마', '영화', '연예', '가수', 'BTS', '아이돌', '배우', '예능']):
        return "연예/문화"
    if any(w in all_text for w in ['건강', '병원', '의사', '간호사', '의료', '치료', '질병']):
        return "건강/의료"
    return "사회/일반"


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 크롤링 시작: {today}")

    url = "https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=111"
    html = fetch_html(url)

    articles = extract_titles(html)
    print(f"  → 총 {len(articles)}개 기사 수집")

    topics = cluster_topics(articles, top_n=5)

    # 카테고리 추가
    for t in topics:
        t['category'] = categorize(t['keyword'], t['related_titles'])

    result = {
        "date": today,
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_articles": len(articles),
        "topics": topics,
    }

    # 날짜별 파일 저장
    daily_path = DATA_DIR / f"{today}.json"
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # latest.json 업데이트
    latest_path = DATA_DIR / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # index.json (전체 날짜 목록) 업데이트
    index_path = DATA_DIR / "index.json"
    existing = []
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            existing = json.load(f)
    dates = sorted(set(existing + [today]), reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False)

    print(f"  → 저장 완료: {daily_path}")
    print()
    print("=== 오늘의 핫토픽 TOP 5 ===")
    for t in topics:
        print(f"{t['rank']}위 [{t['category']}] #{t['keyword']} ({t['count']}건)")
        print(f"   → {t['representative_title']}")
    print()


if __name__ == "__main__":
    main()
