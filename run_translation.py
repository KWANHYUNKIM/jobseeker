#!/usr/bin/env python3
"""
뉴스 번역 실행 스크립트
"""

import os
import sys
from translator import NewsTranslator

def main():
    print("🌍 뉴스 번역기 실행")
    print("=" * 50)
    
    # API 키 입력 받기
    api_key = input("OpenAI API 키를 입력하세요 (sk-로 시작): ").strip()
    
    if not api_key:
        print("❌ API 키가 입력되지 않았습니다.")
        return
    
    if not api_key.startswith('sk-'):
        print("❌ 올바른 OpenAI API 키 형식이 아닙니다. (sk-로 시작해야 합니다)")
        return
    
    # 환경변수 설정
    os.environ['OPENAI_API_KEY'] = api_key
    
    try:
        # 번역기 초기화
        translator = NewsTranslator(api_key)
        
        # 최신 뉴스 파일 찾기
        data_dir = 'data'
        if not os.path.exists(data_dir):
            print("❌ data 디렉토리가 없습니다. 먼저 enhanced_news_scraper.py를 실행해주세요.")
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
        print("\n🚀 번역을 시작합니다...")
        translated_file = translator.translate_from_json(json_path)
        
        # 번역된 결과 읽기
        import json
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
        
        # 번역된 내용 미리보기
        if translated_articles:
            print(f"\n📰 번역 미리보기:")
            print(f"제목: {translated_articles[0]['translated_title']}")
            print(f"요약: {translated_articles[0]['summary']}")
            print(f"내용 일부: {translated_articles[0]['translated_content'][:200]}...")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("API 키가 올바른지 확인해주세요.")

if __name__ == "__main__":
    main() 