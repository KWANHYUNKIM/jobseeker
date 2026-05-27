#!/usr/bin/env python3
"""
OpenAI API를 사용한 뉴스 번역기
"""

import openai
import json
import csv
import os
from datetime import datetime
from typing import List, Dict
import time

class NewsTranslator:
    def __init__(self, api_key: str = None):
        """번역기 초기화"""
        if api_key:
            openai.api_key = api_key
        else:
            # 환경변수에서 API 키 가져오기
            openai.api_key = os.getenv('OPENAI_API_KEY')
        
        if not openai.api_key:
            raise ValueError("OpenAI API 키가 필요합니다. 환경변수 OPENAI_API_KEY를 설정하거나 api_key 매개변수를 전달하세요.")
    
    def translate_article(self, article: Dict) -> Dict:
        """단일 기사를 번역합니다."""
        try:
            # 번역 프롬프트 생성 (기사 스타일)
            prompt = f"""
다음 영어 경제 뉴스를 한국어 경제 기사 스타일로 번역해주세요. 

번역 요구사항:
1. 한국 경제신문 기사처럼 자연스럽고 전문적인 톤으로 번역
2. 경제 전문 용어는 정확한 한국어 용어 사용
3. 문장은 기사다운 띄어쓰기와 문체로 작성
4. 핵심 내용을 강조하고 읽기 쉽게 구성
5. 인용문이나 통계는 정확히 번역

원문:
제목: {article['title']}
출처: {article['source']}
내용:
{article['content']}

다음 형식으로 응답해주세요:
제목: [한국어 기사 제목]
요약: [2-3줄 핵심 내용 요약 - 기사 스타일]
내용: [한국어 기사 내용 - 자연스러운 기사 문체로]
"""
            
            # OpenAI API 호출
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 한국 경제신문의 전문 번역기자입니다. 영어 경제 뉴스를 자연스럽고 전문적인 한국어 경제 기사로 번역합니다. 기사다운 문체와 띄어쓰기를 사용하고, 경제 전문 용어를 정확히 번역합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2500,
                temperature=0.3
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            # 번역 결과 파싱
            translated_article = {
                'original_source': article['source'],
                'original_title': article['title'],
                'original_content': article['content'],
                'original_url': article['url'],
                'translated_title': '',
                'summary': '',
                'translated_content': '',
                'translated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': article.get('category', '')
            }
            
            # 번역 결과에서 제목, 요약, 내용 추출
            lines = translated_text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('제목:'):
                    translated_article['translated_title'] = line.replace('제목:', '').strip()
                elif line.startswith('요약:'):
                    translated_article['summary'] = line.replace('요약:', '').strip()
                elif line.startswith('내용:'):
                    current_section = 'content'
                elif current_section == 'content' and line:
                    translated_article['translated_content'] += line + '\n'
            
            # 내용 정리
            translated_article['translated_content'] = translated_article['translated_content'].strip()
            
            return translated_article
            
        except Exception as e:
            print(f"번역 오류 ({article['title'][:30]}...): {e}")
            return None
    
    def translate_from_csv(self, csv_file: str, output_file: str = None) -> str:
        """CSV 파일에서 뉴스를 읽어서 번역합니다."""
        if not output_file:
            today = datetime.now().strftime('%Y%m%d')
            output_file = f"translated_news_{today}.json"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        output_path = os.path.join('data', output_file)
        
        articles = []
        translated_articles = []
        
        # CSV 파일 읽기
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            articles = list(reader)
        
        print(f"📖 {len(articles)}개의 기사를 번역합니다...")
        
        # 각 기사 번역
        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] 번역 중: {article['title'][:50]}...")
            
            translated = self.translate_article(article)
            if translated:
                translated_articles.append(translated)
            
            # API 호출 간격 조절
            time.sleep(1)
        
        # 번역 결과 저장
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(translated_articles, file, ensure_ascii=False, indent=2)
        
        print(f"✅ 번역 완료! {len(translated_articles)}개 기사가 {output_path}에 저장되었습니다.")
        return output_path
    
    def translate_from_json(self, json_file: str, output_file: str = None) -> str:
        """JSON 파일에서 뉴스를 읽어서 번역합니다."""
        if not output_file:
            today = datetime.now().strftime('%Y%m%d')
            output_file = f"translated_news_{today}.json"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        output_path = os.path.join('data', output_file)
        
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as file:
            articles = json.load(file)
        
        print(f"📖 {len(articles)}개의 기사를 번역합니다...")
        
        translated_articles = []
        
        # 각 기사 번역
        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] 번역 중: {article['title'][:50]}...")
            
            translated = self.translate_article(article)
            if translated:
                translated_articles.append(translated)
            
            # API 호출 간격 조절
            time.sleep(1)
        
        # 번역 결과 저장
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(translated_articles, file, ensure_ascii=False, indent=2)
        
        print(f"✅ 번역 완료! {len(translated_articles)}개 기사가 {output_path}에 저장되었습니다.")
        return output_path
    
    def save_translated_to_txt(self, translated_articles: List[Dict], output_file: str = None) -> str:
        """번역된 뉴스를 읽기 쉬운 TXT 파일로 저장합니다."""
        if not output_file:
            today = datetime.now().strftime('%Y%m%d')
            output_file = f"translated_news_{today}.txt"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        output_path = os.path.join('data', output_file)
        
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write("=== 번역된 해외 경제 뉴스 ===\n\n")
            
            for i, article in enumerate(translated_articles, 1):
                file.write(f"【기사 {i}】\n")
                file.write(f"원출처: {article['original_source']}\n")
                file.write(f"원제목: {article['original_title']}\n")
                file.write(f"번역제목: {article['translated_title']}\n")
                file.write(f"요약: {article['summary']}\n")
                file.write(f"번역시간: {article['translated_at']}\n")
                file.write(f"카테고리: {article['category']}\n")
                file.write("-" * 50 + "\n")
                file.write("번역내용:\n")
                file.write(article['translated_content'])
                file.write("\n\n" + "=" * 80 + "\n\n")
        
        print(f"📁 번역된 TXT 파일: {output_path}")
        return output_path
    
    def save_translated_to_csv(self, translated_articles: List[Dict], output_file: str = None) -> str:
        """번역된 뉴스를 CSV 파일로 저장합니다."""
        if not output_file:
            today = datetime.now().strftime('%Y%m%d')
            output_file = f"translated_news_{today}.csv"
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        output_path = os.path.join('data', output_file)
        
        fieldnames = [
            'original_source', 'original_title', 'translated_title', 
            'summary', 'translated_content', 'translated_at', 'category'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for article in translated_articles:
                writer.writerow({
                    'original_source': article['original_source'],
                    'original_title': article['original_title'],
                    'translated_title': article['translated_title'],
                    'summary': article['summary'],
                    'translated_content': article['translated_content'],
                    'translated_at': article['translated_at'],
                    'category': article['category']
                })
        
        print(f"📊 번역된 CSV 파일: {output_path}")
        return output_path

def main():
    """메인 함수"""
    print("🌍 OpenAI 뉴스 번역기 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("다음 명령어로 설정하세요:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return
    
    # 번역기 초기화
    translator = NewsTranslator()
    
    # 최신 뉴스 파일 찾기
    data_dir = 'data'
    if not os.path.exists(data_dir):
        print("❌ data 디렉토리가 없습니다. 먼저 뉴스를 수집해주세요.")
        return
    
    # 가장 최근 JSON 파일 찾기
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json') and 'enhanced_news' in f]
    if not json_files:
        print("❌ 번역할 뉴스 파일이 없습니다. 먼저 enhanced_news_scraper.py를 실행해주세요.")
        return
    
    latest_json = sorted(json_files)[-1]
    json_path = os.path.join(data_dir, latest_json)
    
    print(f"📖 번역할 파일: {json_path}")
    
    # 번역 실행
    translated_file = translator.translate_from_json(json_path)
    
    # 번역된 결과 읽기
    with open(translated_file, 'r', encoding='utf-8') as file:
        translated_articles = json.load(file)
    
    # 다양한 형식으로 저장
    txt_file = translator.save_translated_to_txt(translated_articles)
    csv_file = translator.save_translated_to_csv(translated_articles)
    
    print(f"\n✅ 번역 완료!")
    print(f"📁 JSON 파일: {translated_file}")
    print(f"📄 TXT 파일: {txt_file}")
    print(f"📊 CSV 파일: {csv_file}")
    print(f"📰 총 {len(translated_articles)}개 기사 번역 완료")

if __name__ == "__main__":
    main() 