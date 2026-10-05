# 청약 블로그 자동화

- GitHub Actions `fetch-data`: 청약홈 데이터를 받아 data/에 저장 (한국 시간 07:20, 18:20)
- Claude 예약 작업: WRITER.md 순서대로 글을 써서 posts/pending/에 올림 (07:35, 18:35)
- GitHub Actions `publish-posts`: src/check.py로 검수 후 Blogger에 올림 (config.json mode=draft면 임시저장)
- 규칙: rules/ 폴더 (SEO, 상위노출, 글쓰기, 키워드)

비밀값(Settings → Secrets → Actions): DATA_GO_KR_KEY, BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET,
BLOGGER_REFRESH_TOKEN, BLOGGER_BLOG_ID

테스트: `python -m pytest tests` (pytest 필요)
