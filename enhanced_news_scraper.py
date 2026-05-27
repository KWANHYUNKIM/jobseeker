#!/usr/bin/env python3
"""
향상된 뉴스 스크래퍼 - 더 많은 사이트에서 더 많은 기사 수집
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime
import os
from typing import List, Dict
import random
import re
import json

class EnhancedNewsScraper:
    def __init__(self):
        self.session = requests.Session()
        # 더 다양한 User-Agent 사용
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_article_content(self, url: str, source: str) -> str:
        """뉴스 URL에서 실제 내용을 가져옵니다."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 소스별로 다른 선택자 사용
            content_selectors = {
                'cnbc': [
                    'div[data-module="ArticleBody"]',
                    'div.ArticleBody-articleBody',
                    'div.article-content',
                    'div[class*="content"]',
                    'article p'
                ],
                'yahoo': [
                    'div.caas-body',
                    'div[data-test-id="caas-body"]',
                    'div.article-content',
                    'article p'
                ],
                'marketwatch': [
                    'div.article__content',
                    'div[class*="content"]',
                    'article p'
                ],
                'reuters': [
                    'div[data-testid="ArticleBody"]',
                    'div.article-body',
                    'div[class*="content"]',
                    'article p'
                ],
                'bloomberg': [
                    'div[data-module="ArticleBody"]',
                    'div.article-content',
                    'div[class*="content"]',
                    'article p'
                ],
                'ft': [
                    'div.article__content',
                    'div[class*="content"]',
                    'article p'
                ],
                'wsj': [
                    'div[data-module="ArticleBody"]',
                    'div.article-content',
                    'div[class*="content"]',
                    'article p'
                ]
            }
            
            selectors = content_selectors.get(source.lower(), content_selectors['cnbc'])
            
            content = ""
            for selector in selectors:
                content_elements = soup.select(selector)
                if content_elements:
                    for element in content_elements:
                        text = element.get_text().strip()
                        if len(text) > 50:  # 의미있는 텍스트만
                            content += text + "\n\n"
                    break
            
            # 내용이 없으면 다른 방법 시도
            if not content:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text().strip()
                    if len(text) > 30:  # 짧은 텍스트 제외
                        content += text + "\n\n"
            
            # 내용 정리
            content = re.sub(r'\n\s*\n', '\n\n', content)  # 빈 줄 정리
            content = re.sub(r'\s+', ' ', content)  # 연속 공백 정리
            content = content.strip()
            
            return content[:8000]  # 더 긴 내용 허용
            
        except Exception as e:
            print(f"내용 추출 오류 ({url}): {e}")
            return ""
    
    def get_news_from_cnbc(self, max_articles: int = 10) -> List[Dict]:
        """CNBC에서 뉴스를 가져옵니다."""
        articles = []
        
        try:
            print(f"CNBC에서 {max_articles}개의 뉴스를 수집 중...")
            
            # 여러 CNBC 섹션에서 뉴스 수집
            sections = [
                "https://www.cnbc.com/markets/",
                "https://www.cnbc.com/economy/",
                "https://www.cnbc.com/technology/",
                "https://www.cnbc.com/politics/"
            ]
            
            for section_url in sections:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    response = self.session.get(section_url, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 다양한 링크 패턴 찾기
                    news_links = soup.find_all('a', href=lambda x: x and (
                        '/2024/' in x or '/2025/' in x or 
                        x.endswith('.html') or 
                        '/news/' in x
                    ))
                    
                    for link in news_links:
                        if len(articles) >= max_articles:
                            break
                            
                        title = link.get_text().strip()
                        article_url = link.get('href', '')
                        
                        if title and len(title) > 15 and article_url:
                            if article_url.startswith('/'):
                                article_url = 'https://www.cnbc.com' + article_url
                            
                            # 중복 체크
                            if any(article['url'] == article_url for article in articles):
                                continue
                            
                            print(f"  - {title[:60]}...")
                            
                            # 실제 내용 가져오기
                            content = self.get_article_content(article_url, 'CNBC')
                            
                            if content:  # 내용이 있는 경우만 추가
                                article = {
                                    'source': 'CNBC',
                                    'title': title,
                                    'url': article_url,
                                    'content': content,
                                    'published': datetime.now().strftime('%Y-%m-%d'),
                                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'category': 'markets'
                                }
                                articles.append(article)
                                
                                # 요청 간 딜레이
                                time.sleep(random.uniform(1, 2))
                
                except Exception as e:
                    print(f"CNBC 섹션 오류 ({section_url}): {e}")
                    continue
            
            print(f"CNBC: {len(articles)}개의 뉴스 발견")
            
        except Exception as e:
            print(f"CNBC 스크래핑 오류: {e}")
        
        return articles
    
    def get_news_from_yahoo_finance(self, max_articles: int = 10) -> List[Dict]:
        """Yahoo Finance에서 뉴스를 가져옵니다."""
        articles = []
        
        try:
            print(f"Yahoo Finance에서 {max_articles}개의 뉴스를 수집 중...")
            
            # 여러 Yahoo Finance 섹션
            sections = [
                "https://finance.yahoo.com/news/",
                "https://finance.yahoo.com/markets/",
                "https://finance.yahoo.com/tech/"
            ]
            
            for section_url in sections:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    response = self.session.get(section_url, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 다양한 링크 패턴 찾기
                    news_links = soup.find_all('a', href=lambda x: x and (
                        '/news/' in x or 
                        x.endswith('.html') or
                        '/story/' in x
                    ))
                    
                    for link in news_links:
                        if len(articles) >= max_articles:
                            break
                            
                        title = link.get_text().strip()
                        article_url = link.get('href', '')
                        
                        if title and len(title) > 15 and article_url:
                            if article_url.startswith('/'):
                                article_url = 'https://finance.yahoo.com' + article_url
                            
                            # 중복 체크
                            if any(article['url'] == article_url for article in articles):
                                continue
                            
                            print(f"  - {title[:60]}...")
                            
                            # 실제 내용 가져오기
                            content = self.get_article_content(article_url, 'Yahoo')
                            
                            if content:  # 내용이 있는 경우만 추가
                                article = {
                                    'source': 'Yahoo_Finance',
                                    'title': title,
                                    'url': article_url,
                                    'content': content,
                                    'published': datetime.now().strftime('%Y-%m-%d'),
                                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'category': 'finance'
                                }
                                articles.append(article)
                                
                                # 요청 간 딜레이
                                time.sleep(random.uniform(1, 2))
                
                except Exception as e:
                    print(f"Yahoo Finance 섹션 오류 ({section_url}): {e}")
                    continue
            
            print(f"Yahoo Finance: {len(articles)}개의 뉴스 발견")
            
        except Exception as e:
            print(f"Yahoo Finance 스크래핑 오류: {e}")
        
        return articles
    
    def get_news_from_marketwatch(self, max_articles: int = 10) -> List[Dict]:
        """MarketWatch에서 뉴스를 가져옵니다."""
        articles = []
        
        try:
            print(f"MarketWatch에서 {max_articles}개의 뉴스를 수집 중...")
            
            # 여러 MarketWatch 섹션
            sections = [
                "https://www.marketwatch.com/latest-news",
                "https://www.marketwatch.com/markets",
                "https://www.marketwatch.com/economy-politics"
            ]
            
            for section_url in sections:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    response = self.session.get(section_url, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 다양한 링크 패턴 찾기
                    news_links = soup.find_all('a', href=lambda x: x and (
                        '/story/' in x or
                        '/news/' in x or
                        x.endswith('.html')
                    ))
                    
                    for link in news_links:
                        if len(articles) >= max_articles:
                            break
                            
                        title = link.get_text().strip()
                        article_url = link.get('href', '')
                        
                        if title and len(title) > 15 and article_url:
                            if article_url.startswith('/'):
                                article_url = 'https://www.marketwatch.com' + article_url
                            
                            # 중복 체크
                            if any(article['url'] == article_url for article in articles):
                                continue
                            
                            print(f"  - {title[:60]}...")
                            
                            # 실제 내용 가져오기
                            content = self.get_article_content(article_url, 'MarketWatch')
                            
                            if content:  # 내용이 있는 경우만 추가
                                article = {
                                    'source': 'MarketWatch',
                                    'title': title,
                                    'url': article_url,
                                    'content': content,
                                    'published': datetime.now().strftime('%Y-%m-%d'),
                                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'category': 'markets'
                                }
                                articles.append(article)
                                
                                # 요청 간 딜레이
                                time.sleep(random.uniform(1, 2))
                
                except Exception as e:
                    print(f"MarketWatch 섹션 오류 ({section_url}): {e}")
                    continue
            
            print(f"MarketWatch: {len(articles)}개의 뉴스 발견")
            
        except Exception as e:
            print(f"MarketWatch 스크래핑 오류: {e}")
        
        return articles
    
    def get_news_from_investing(self, max_articles: int = 10) -> List[Dict]:
        """Investing.com에서 뉴스를 가져옵니다."""
        articles = []
        
        try:
            print(f"Investing.com에서 {max_articles}개의 뉴스를 수집 중...")
            
            # Investing.com 뉴스 섹션
            sections = [
                "https://www.investing.com/news/",
                "https://www.investing.com/news/economic-indicators",
                "https://www.investing.com/news/stock-market-news"
            ]
            
            for section_url in sections:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    response = self.session.get(section_url, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Investing.com 뉴스 링크 찾기
                    news_links = soup.find_all('a', href=lambda x: x and '/news/' in x)
                    
                    for link in news_links:
                        if len(articles) >= max_articles:
                            break
                            
                        title = link.get_text().strip()
                        article_url = link.get('href', '')
                        
                        if title and len(title) > 15 and article_url:
                            if article_url.startswith('/'):
                                article_url = 'https://www.investing.com' + article_url
                            
                            # 중복 체크
                            if any(article['url'] == article_url for article in articles):
                                continue
                            
                            print(f"  - {title[:60]}...")
                            
                            # 실제 내용 가져오기
                            content = self.get_article_content(article_url, 'Investing')
                            
                            if content:  # 내용이 있는 경우만 추가
                                article = {
                                    'source': 'Investing.com',
                                    'title': title,
                                    'url': article_url,
                                    'content': content,
                                    'published': datetime.now().strftime('%Y-%m-%d'),
                                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'category': 'markets'
                                }
                                articles.append(article)
                                
                                # 요청 간 딜레이
                                time.sleep(random.uniform(1, 2))
                
                except Exception as e:
                    print(f"Investing.com 섹션 오류 ({section_url}): {e}")
                    continue
            
            print(f"Investing.com: {len(articles)}개의 뉴스 발견")
            
        except Exception as e:
            print(f"Investing.com 스크래핑 오류: {e}")
        
        return articles
    
    def get_news_from_fxstreet(self, max_articles: int = 10) -> List[Dict]:
        """FXStreet에서 뉴스를 가져옵니다."""
        articles = []
        
        try:
            print(f"FXStreet에서 {max_articles}개의 뉴스를 수집 중...")
            
            # FXStreet 뉴스 섹션
            sections = [
                "https://www.fxstreet.com/news",
                "https://www.fxstreet.com/economic-indicators"
            ]
            
            for section_url in sections:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    response = self.session.get(section_url, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # FXStreet 뉴스 링크 찾기
                    news_links = soup.find_all('a', href=lambda x: x and '/news/' in x)
                    
                    for link in news_links:
                        if len(articles) >= max_articles:
                            break
                            
                        title = link.get_text().strip()
                        article_url = link.get('href', '')
                        
                        if title and len(title) > 15 and article_url:
                            if article_url.startswith('/'):
                                article_url = 'https://www.fxstreet.com' + article_url
                            
                            # 중복 체크
                            if any(article['url'] == article_url for article in articles):
                                continue
                            
                            print(f"  - {title[:60]}...")
                            
                            # 실제 내용 가져오기
                            content = self.get_article_content(article_url, 'FXStreet')
                            
                            if content:  # 내용이 있는 경우만 추가
                                article = {
                                    'source': 'FXStreet',
                                    'title': title,
                                    'url': article_url,
                                    'content': content,
                                    'published': datetime.now().strftime('%Y-%m-%d'),
                                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'category': 'forex'
                                }
                                articles.append(article)
                                
                                # 요청 간 딜레이
                                time.sleep(random.uniform(1, 2))
                
                except Exception as e:
                    print(f"FXStreet 섹션 오류 ({section_url}): {e}")
                    continue
            
            print(f"FXStreet: {len(articles)}개의 뉴스 발견")
            
        except Exception as e:
            print(f"FXStreet 스크래핑 오류: {e}")
        
        return articles
    
    def collect_all_news(self, max_per_source: int = 10) -> List[Dict]:
        """모든 뉴스 소스에서 뉴스를 수집합니다."""
        all_articles = []
        
        # CNBC 뉴스 수집
        cnbc_articles = self.get_news_from_cnbc(max_per_source)
        all_articles.extend(cnbc_articles)
        time.sleep(random.uniform(3, 5))
        
        # Yahoo Finance 뉴스 수집
        yahoo_articles = self.get_news_from_yahoo_finance(max_per_source)
        all_articles.extend(yahoo_articles)
        time.sleep(random.uniform(3, 5))
        
        # MarketWatch 뉴스 수집
        marketwatch_articles = self.get_news_from_marketwatch(max_per_source)
        all_articles.extend(marketwatch_articles)
        time.sleep(random.uniform(3, 5))
        
        # Investing.com 뉴스 수집
        investing_articles = self.get_news_from_investing(max_per_source)
        all_articles.extend(investing_articles)
        time.sleep(random.uniform(3, 5))
        
        # FXStreet 뉴스 수집
        fxstreet_articles = self.get_news_from_fxstreet(max_per_source)
        all_articles.extend(fxstreet_articles)
        
        return all_articles
    
    def save_to_csv(self, articles: List[Dict], filename: str = None) -> str:
        """뉴스를 CSV 파일로 저장합니다."""
        if not filename:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"enhanced_news_{today}.csv"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        if articles:
            fieldnames = ['source', 'title', 'url', 'content', 'published', 'collected_at', 'category']
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(articles)
            
            print(f"\n📁 향상된 뉴스 데이터가 {filepath}에 저장되었습니다.")
            print(f"📊 총 {len(articles)}개의 기사가 저장되었습니다.")
        else:
            print("❌ 저장할 뉴스가 없습니다.")
        
        return filepath
    
    def save_to_json(self, articles: List[Dict], filename: str = None) -> str:
        """뉴스를 JSON 파일로 저장합니다."""
        if not filename:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"enhanced_news_{today}.json"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        if articles:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(articles, jsonfile, ensure_ascii=False, indent=2)
            
            print(f"📁 JSON 파일: {filepath}")
        else:
            print("❌ 저장할 뉴스가 없습니다.")
        
        return filepath
    
    def save_to_txt(self, articles: List[Dict], filename: str = None) -> str:
        """뉴스를 읽기 쉬운 TXT 파일로 저장합니다."""
        if not filename:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"enhanced_news_for_gpt_{today}.txt"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        if articles:
            with open(filepath, 'w', encoding='utf-8') as txtfile:
                txtfile.write("=== 해외 경제 뉴스 모음 (향상된 버전) ===\n\n")
                
                for i, article in enumerate(articles, 1):
                    txtfile.write(f"【기사 {i}】\n")
                    txtfile.write(f"출처: {article['source']}\n")
                    txtfile.write(f"제목: {article['title']}\n")
                    txtfile.write(f"URL: {article['url']}\n")
                    txtfile.write(f"수집시간: {article['collected_at']}\n")
                    txtfile.write(f"카테고리: {article['category']}\n")
                    txtfile.write("-" * 50 + "\n")
                    txtfile.write("내용:\n")
                    txtfile.write(article['content'])
                    txtfile.write("\n\n" + "=" * 80 + "\n\n")
            
            print(f"📁 GPT용 TXT 파일: {filepath}")
        else:
            print("❌ 저장할 뉴스가 없습니다.")
        
        return filepath
    
    def get_daily_summary(self, articles: List[Dict]) -> Dict:
        """일일 수집 요약을 생성합니다."""
        summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_articles': len(articles),
            'sources': {},
            'total_content_length': 0
        }
        
        # 소스별 통계
        for article in articles:
            source = article['source']
            summary['sources'][source] = summary['sources'].get(source, 0) + 1
            summary['total_content_length'] += len(article.get('content', ''))
        
        return summary
    
    def print_summary(self, summary: Dict):
        """수집 요약을 출력합니다."""
        print("\n" + "="*60)
        print("📊 향상된 뉴스 수집 요약")
        print("="*60)
        print(f"📅 날짜: {summary['date']}")
        print(f"📰 총 기사 수: {summary['total_articles']}개")
        print(f"📝 총 내용 길이: {summary['total_content_length']:,}자")
        
        print("\n📋 소스별 기사 수:")
        for source, count in summary['sources'].items():
            print(f"  - {source}: {count}개")
        print("="*60)

def main():
    """메인 함수"""
    print("🌍 향상된 뉴스 스크래핑 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    scraper = EnhancedNewsScraper()
    
    # 각 소스당 최대 10개씩 뉴스 수집
    print("\n📡 다양한 뉴스 사이트에서 뉴스 수집 중...")
    articles = scraper.collect_all_news(max_per_source=10)
    
    if not articles:
        print("❌ 수집된 뉴스가 없습니다.")
        return
    
    # 요약 생성
    summary = scraper.get_daily_summary(articles)
    scraper.print_summary(summary)
    
    # CSV 파일로 저장
    csv_file = scraper.save_to_csv(articles)
    
    # JSON 파일로도 저장
    json_file = scraper.save_to_json(articles)
    
    # GPT용 TXT 파일로 저장
    txt_file = scraper.save_to_txt(articles)
    
    print(f"\n✅ 향상된 뉴스 수집 완료!")
    print(f"📊 CSV 파일: {csv_file}")
    print(f"📁 JSON 파일: {json_file}")
    print(f"🤖 GPT용 TXT 파일: {txt_file}")
    print(f"\n💡 이제 더 많은 뉴스를 GPT에 번역 요청할 수 있습니다!")

if __name__ == "__main__":
    main() 