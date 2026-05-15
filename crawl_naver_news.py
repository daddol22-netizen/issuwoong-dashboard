#!/usr/bin/env python3
"""네이버 뉴스 랭킹 크롤러 - 매일 오전 7시 자동 실행"""

import re
import json
import time
import urllib.request
import urllib.parse
from html import unescape as html_unescape
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


STOCK_KEYWORDS = {
    '주식', '코스피', '코스닥', '증권', '코인', '비트코인', '이더리움', '가상자산', '암호화폐',
    '투자', '펀드', 'ETF', 'ETF', '상장', '종목', '주가', '배당', '공모', '채권', '금리',
    '환율', '달러', '원화', '나스닥', 'S&P', '다우', '선물', '옵션', '매수', '매도',
    '급등', '급락', '반등', '조정', '강세', '약세', '시총', '외인', '기관', '개인투자',
    '하이닉스', '삼성전자', '카카오', '네이버', '엔비디아', '테슬라', '애플',
}

def is_stock_article(title: str) -> bool:
    words = re.findall(r'[가-힣A-Za-z&]+', title)
    return any(w in STOCK_KEYWORDS for w in words)


def crawl_stock_topics() -> list[dict]:
    """네이버 증권(102) + 경제(101) 랭킹에서 주식/코인 토픽 추출"""
    all_articles = []
    for sid in ['102', '101']:
        try:
            url = f"https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1={sid}"
            html = fetch_html(url)
            articles = extract_titles(html)
            # 주식/코인 관련 기사만 필터
            filtered = [a for a in articles if is_stock_article(a['title'])]
            all_articles.extend(filtered)
        except Exception as e:
            print(f"  ⚠ sid1={sid} 크롤링 실패: {e}")

    # 전체 랭킹에서도 주식/코인 기사 보완
    try:
        url = "https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=111"
        html = fetch_html(url)
        articles = extract_titles(html)
        filtered = [a for a in articles if is_stock_article(a['title'])]
        all_articles.extend(filtered)
    except Exception as e:
        print(f"  ⚠ 전체 랭킹 주식 보완 실패: {e}")

    if not all_articles:
        return []

    print(f"  → 주식/코인 관련 기사 {len(all_articles)}개 수집")
    topics = cluster_topics(all_articles, top_n=5)
    for t in topics:
        t['category'] = '주식/코인'
    return topics


def fetch_google_news_rss(query: str, days: int = 7) -> list[dict]:
    """Google News RSS로 최근 N일 기사 수집 (Naver 검색이 SPA라 대체)"""
    from datetime import timedelta
    try:
        from email.utils import parsedate_to_datetime
    except ImportError:
        parsedate_to_datetime = None

    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            xml = res.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  ⚠ Google News RSS 실패: {e}")
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    results = []

    for item in re.findall(r'<item>(.*?)</item>', xml, re.DOTALL):
        title_m = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
        link_m = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
        date_m = re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL)
        if not (title_m and link_m):
            continue

        raw_title = re.sub(r'<!\[CDATA\[|\]\]>', '', title_m.group(1)).strip()
        # "제목 - 언론사" 형식에서 언론사 제거
        title = re.sub(r'\s*-\s*[^\-]+$', '', raw_title).strip()
        link = link_m.group(1).strip()

        # 날짜 필터
        if date_m and parsedate_to_datetime:
            try:
                pub = parsedate_to_datetime(date_m.group(1).strip()).replace(tzinfo=None)
                if pub < cutoff:
                    continue
            except Exception:
                pass

        results.append({"title": title, "link": link, "press": ""})

    return results


def extract_moljak_subject(title: str) -> str:
    """제목에서 '몰락'의 주체 추출 — 'X의 몰락', 'X 몰락', '몰락한 X' 패턴"""
    # 1. "X의 몰락" — X가 2~12자
    m = re.search(r'([가-힣A-Za-z0-9·\s]{2,12})의\s*몰락', title)
    if m:
        subject = m.group(1).strip()
        # 마지막 의미 단어 추출 (앞의 수식어 날리기)
        words = re.findall(r'[가-힣A-Za-z0-9·]{2,}', subject)
        if words:
            return words[-1]

    # 2. "X 몰락" — X가 조사 없이 붙는 경우
    m = re.search(r"'?([가-힣A-Za-z0-9·]{2,10})'?\s+몰락", title)
    if m:
        return m.group(1)

    # 3. "몰락한 X"
    m = re.search(r'몰락한\s+([가-힣A-Za-z0-9·]{2,10})', title)
    if m:
        return m.group(1)

    return ""


def cluster_moljak_topics(articles: list[dict], top_n: int = 5) -> list[dict]:
    """'몰락' 기사 클러스터링 — 제목에서 주체 직접 추출"""
    filtered = [a for a in articles if '몰락' in a['title']]
    if not filtered:
        return []

    subject_to_articles: dict[str, list] = {}

    for art in filtered:
        subject = extract_moljak_subject(art['title'])
        if not subject or len(subject) < 2:
            continue
        # '몰락' 자체가 포함된 단어 제외 (e.g. "몰락한", "몰락의")
        if '몰락' in subject:
            continue
        subject_to_articles.setdefault(subject, [])
        subject_to_articles[subject].append(art)

    subject_counts = {k: len({a['title'] for a in v}) for k, v in subject_to_articles.items()}
    top_subjects = sorted(subject_counts.items(), key=lambda x: x[1], reverse=True)

    seen_titles: set[str] = set()
    topics = []

    for subject, count in top_subjects:
        if len(topics) >= top_n:
            break

        related = [a for a in subject_to_articles[subject] if a['title'] not in seen_titles]
        if not related:
            continue

        related_sorted = sorted(related, key=lambda a: len(a['title']))
        representative = related_sorted[0]

        for a in related:
            seen_titles.add(a['title'])

        topics.append({
            "rank": len(topics) + 1,
            "keyword": subject,
            "series_title": f"{subject}의 몰락",
            "count": count,
            "representative_title": representative['title'],
            "representative_link": representative['link'],
            "press": representative.get('press', ''),
            "related_articles": [
                {"title": a['title'], "link": a['link'], "press": a.get('press', '')}
                for a in related[:5]
            ],
            "related_titles": [a['title'] for a in related[:5]],
            "category": "몰락",
        })

    return topics


def crawl_moljak() -> list[dict]:
    """몰락 주제 기사 크롤링 (Google News RSS 기반)"""
    print("  → 몰락 기사 검색 중...")
    articles = fetch_google_news_rss('몰락', days=7)
    title_count = sum(1 for a in articles if '몰락' in a['title'])
    print(f"  → 몰락 관련 기사 {len(articles)}개 수집 (제목 포함: {title_count}건)")
    topics = cluster_moljak_topics(articles, top_n=5)
    return topics


def main():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hour = now.strftime("%H")
    slot_key = f"{today}_{hour}"

    print(f"[{now.strftime('%H:%M:%S')}] 크롤링 시작: {slot_key}")

    # ── 전체 핫토픽 ──
    url = "https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=111"
    html = fetch_html(url)
    articles = extract_titles(html)
    print(f"  → 전체 기사 {len(articles)}개 수집")

    topics = cluster_topics(articles, top_n=5)
    for t in topics:
        t['category'] = categorize(t['keyword'], t['related_titles'])

    # ── 주식/코인 토픽 ──
    stock_topics = crawl_stock_topics()

    # ── 몰락 토픽 ──
    moljak_topics = crawl_moljak()

    result = {
        "date": today,
        "hour": hour,
        "slot": slot_key,
        "crawled_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_articles": len(articles),
        "topics": topics,
        "stock_topics": stock_topics,
        "moljak_topics": moljak_topics,
    }

    slot_path = DATA_DIR / f"{slot_key}.json"
    with open(slot_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    latest_path = DATA_DIR / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    index_path = DATA_DIR / "index.json"
    existing = []
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            existing = json.load(f)
    slots = sorted(set(existing + [slot_key]), reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(slots, f, ensure_ascii=False)

    print(f"  → 저장 완료: {slot_path}")
    print()
    print("=== 전체 핫토픽 TOP 5 ===")
    for t in topics:
        print(f"{t['rank']}위 [{t['category']}] #{t['keyword']} ({t['count']}건)")
        print(f"   → {t['representative_title']}")
    print()
    print("=== 주식/코인 TOP 5 ===")
    for t in stock_topics:
        print(f"{t['rank']}위 #{t['keyword']} ({t['count']}건)")
        print(f"   → {t['representative_title']}")
    print()
    print("=== 몰락 시리즈 TOP 5 ===")
    for t in moljak_topics:
        print(f"{t['rank']}위 [{t['series_title']}] ({t['count']}건)")
        print(f"   → {t['representative_title']}")
    print()


if __name__ == "__main__":
    main()
