"""사용: python blogs/drone/check_cli.py blogs/drone/posts/pending/파일.md → 통과 0, 실패 1"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from seo import is_new, seo_errors, seo_warnings  # noqa: E402
from sitewide import format_errors, overlap_errors, skeleton_errors  # noqa: E402

bad = 0
for a in sys.argv[1:]:
    p = Path(a)
    meta, body = blog.split_post(p.read_text("utf-8"))
    meta["_file"] = p.name
    recent = [r for r in blog.recent_posts() if r.get("file") != p.name]
    if p.parent.name == "published":
        recent = []  # 이미 올린 글을 다시 검사할 때는 발행 순서 규칙을 빼고 본다
    errs = blog.check_text(meta, body, recent) + seo_errors(meta, body, "drone", new=p.parent.name != "published" and is_new(p.name))
    errs += (overlap_errors("drone", meta, body, p.name) if p.parent.name != "published" and is_new(p.name) else [])
    errs += skeleton_errors("drone", meta, body, p.name) + (format_errors("drone", meta, p.name) if p.parent.name != "published" else [])
    print(f"{p.name}: {'통과' if not errs else '실패'}")
    for e in errs:
        print("  -", e)
    for w in seo_warnings(meta, body):
        print("  · 검색 권장:", w)
    bad += bool(errs)
sys.exit(1 if bad else 0)
