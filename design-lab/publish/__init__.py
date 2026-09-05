"""발행 — 만든 포스터를 인스타/페이스북/링크드인으로 내보낸다.

세 플랫폼 모두 '이미지 + 글 + 링크' 로 같아 보이지만 실제로는 다르다.
  인스타: 공개 URL 로 컨테이너를 만들고 나서 게시(2단계). 본문 링크가 안 걸린다.
  페이스북: 페이지에 사진 한 방. 링크가 본문에 걸린다.
  링크드인: 이미지를 먼저 업로드해 URN 을 받고 그걸 글에 붙인다(3단계).
그래서 Publisher 를 공통 인터페이스로 두고 차이는 각 모듈 안에 가둔다.

기본은 언제나 dry-run 이다. 실제 계정에 올라가려면 config/accounts.json 과
--live 가 둘 다 있어야 한다 — 실수로 남의 피드에 올라가는 일은 없어야 한다.
"""
from .base import PublishResult, Publisher, load_config, publisher_for, PLATFORMS  # noqa: F401
