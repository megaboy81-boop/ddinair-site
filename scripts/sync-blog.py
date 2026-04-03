#!/usr/bin/env python3
"""
DD에어컨 블로그 시공사례 자동 동기화 스크립트
RSS → 파싱 → 썸네일 다운로드 → blog-cases.json 생성

실행: python3 scripts/sync-blog.py
"""
import json, re, os, sys, time
import urllib.request
from xml.etree import ElementTree as ET
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RSS_URL     = 'https://rss.blog.naver.com/ddinair.xml'
OUTPUT_JSON = os.path.join(SCRIPT_DIR, '../src/data/blog-cases.json')
IMG_DIR     = os.path.join(SCRIPT_DIR, '../public/images/blog-cases')

BRANDS = ['LG', '삼성', '캐리어', '위니아', '파세코', '신일', '롯데']
TYPES  = ['4WAY', '스탠드', '벽걸이', '멀티', '1WAY']

HEADERS_BROWSER = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}


def parse_title(raw_title):
    """[시공사례] 제목 → (place, spec, type) 파싱"""
    title = re.sub(r'^\[시공사례\]\s*', '', raw_title).strip()
    title = re.sub(r'\s*[|｜].*$', '', title).strip()

    place, spec = title, ''
    for brand in BRANDS:
        idx = title.find(brand)
        if idx > 0:
            place = title[:idx].strip().rstrip(' -·,')
            spec  = title[idx:].strip()
            break

    type_ = '기타'
    for t in TYPES:
        if t in spec or t in title:
            type_ = t
            break

    return place, spec, type_


def get_og_image(blog_url):
    """모바일 블로그 페이지에서 OG 이미지 URL 추출"""
    mobile = blog_url.replace('blog.naver.com', 'm.blog.naver.com')
    try:
        req = urllib.request.Request(mobile, headers={
            **HEADERS_BROWSER,
            'Referer': 'https://blog.naver.com/',
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode('utf-8', errors='ignore')
        for pattern in [
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                return m.group(1).split('?')[0]   # strip query string
    except Exception as e:
        print(f'    OG image error: {e}')
    return None


def get_excerpt(description, blog_url, max_len=280):
    """RSS description 또는 모바일 페이지에서 excerpt 추출"""
    text = re.sub(r'<[^>]+>', '', description)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;', "'")
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) >= 50:
        return text[:max_len]

    # RSS 내용이 짧으면 모바일 페이지 본문 가져오기
    try:
        mobile = blog_url.replace('blog.naver.com', 'm.blog.naver.com')
        req = urllib.request.Request(mobile, headers={**HEADERS_BROWSER, 'Referer': 'https://blog.naver.com/'})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode('utf-8', errors='ignore')
        # 본문 p 태그 추출
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        combined = ''
        for p in paragraphs:
            clean = re.sub(r'<[^>]+>', '', p).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if len(clean) > 20:
                combined += clean + ' '
            if len(combined) >= max_len:
                break
        return combined.strip()[:max_len]
    except:
        pass
    return text[:max_len]


def download_image(og_url, filepath):
    """썸네일 다운로드 — Referer 헤더 필수"""
    for suffix in ['?type=w2', '?type=w800', '']:
        try:
            req = urllib.request.Request(og_url + suffix, headers={
                **HEADERS_BROWSER,
                'Referer': 'https://blog.naver.com/',
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            if len(data) < 2000:
                continue
            with open(filepath, 'wb') as f:
                f.write(data)
            print(f'    {len(data):,} bytes → {os.path.basename(filepath)}')
            return True
        except Exception as e:
            print(f'    suffix={suffix!r} error: {e}')
    return False


def parse_date(pub_date_str):
    """RSS pubDate → YYYY.MM"""
    for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S +0900']:
        try:
            dt = datetime.strptime(pub_date_str.strip(), fmt)
            return dt.strftime('%Y.%m')
        except:
            pass
    m = re.search(r'(\d{4})\s+(\d{2}:\d{2})', pub_date_str)
    if m:
        return m.group(1) + '.01'
    m = re.search(r'(\d{4})', pub_date_str)
    return (m.group(1) + '.01') if m else '2025.01'


def main():
    os.makedirs(IMG_DIR, exist_ok=True)

    print(f'[sync-blog] RSS 로드 중: {RSS_URL}')
    req = urllib.request.Request(RSS_URL, headers={'User-Agent': HEADERS_BROWSER['User-Agent']})
    with urllib.request.urlopen(req, timeout=15) as r:
        rss_data = r.read()

    root    = ET.fromstring(rss_data)
    channel = root.find('channel')
    items   = channel.findall('item')
    print(f'[sync-blog] 전체 {len(items)}개 중 [시공사례] 필터...')

    cases = []
    for item in items:
        title    = item.findtext('title', '')
        if '[시공사례]' not in title:
            continue

        link     = item.findtext('link', '').strip()
        desc     = item.findtext('description', '')
        pub_date = item.findtext('pubDate', '')

        m = re.search(r'/(\d+)\s*$', link)
        post_id = m.group(1) if m else str(abs(hash(link)) % 10**10)

        print(f'\n[{len(cases)+1}] {title[:70]}')

        place, spec, type_ = parse_title(title)
        date    = parse_date(pub_date)
        excerpt = get_excerpt(desc, link)

        img_filename = f'blog_{post_id}.jpg'
        img_path     = os.path.join(IMG_DIR, img_filename)
        img_web      = f'/images/blog-cases/{img_filename}'

        has_img = os.path.exists(img_path) and os.path.getsize(img_path) > 2000
        if has_img:
            print(f'    이미지 캐시됨: {img_filename}')
        else:
            og_url = get_og_image(link)
            if og_url:
                print(f'    OG: {og_url[:90]}')
                has_img = download_image(og_url, img_path)
            time.sleep(0.4)

        cases.append({
            'img':      img_filename,
            'date':     date,
            'place':    place,
            'spec':     spec,
            'type':     type_,
            'blogImg':  img_web if has_img else '',
            'excerpt':  excerpt,
            'blogLink': link,
        })
        print(f'    → {place} | {spec} | {type_} | {date}')

    print(f'\n[sync-blog] 완료: {len(cases)}개 시공사례')

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f'[sync-blog] JSON 저장: {OUTPUT_JSON}')


if __name__ == '__main__':
    main()
