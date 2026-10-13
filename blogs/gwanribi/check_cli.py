"""사용: python blogs/gwanribi/check_cli.py blogs/gwanribi/posts/pending/파일.md → 통과 0, 실패 1"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog  # noqa: E402

bad = 0
for a in sys.argv[1:]:
    p = Path(a)
    meta, body = blog.split_post(p.read_text("utf-8"))
    meta["_file"] = p.name
    errs = blog.check_text(meta, body, blog.recent_posts())
    print(f"{p.name}: {'통과' if not errs else '실패'}")
    for e in errs:
        print("  -", e)
    bad += bool(errs)
sys.exit(1 if bad else 0)
