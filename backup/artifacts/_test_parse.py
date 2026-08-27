import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/emergency_plan")

from app.regulations.sync import _extract_articles_from_text

# Test with a sample legal text
sample = """中华人民共和国安全生产法

第一章 总则

第一条 为了加强安全生产工作，防止和减少生产安全事故，保障人民群众生命和财产安全，促进经济社会持续健康发展，制定本法。

第二条 在中华人民共和国领域内从事生产经营活动的单位（以下统称生产经营单位）的安全生产，适用本法。

第三条 安全生产工作坚持中国共产党的领导。

第四条 生产经营单位必须遵守本法和其他有关安全生产的法律、法规。

第五条 生产经营单位的主要负责人对本单位的安全生产工作全面负责。

第二十一条 生产经营单位的主要负责人对本单位安全生产工作负有下列职责：
（一）建立健全并落实本单位全员安全生产责任制；
（二）组织制定并实施本单位安全生产规章制度和操作规程；
（三）保证本单位安全生产投入的有效实施；
（四）组织建立并落实安全风险分级管控和隐患排查治理双重预防工作机制；

第九十六条 本法自2002年11月1日起施行。"""

articles = _extract_articles_from_text(sample)
print(f"Articles extracted: {len(articles)}")
for a in articles:
    print(f"  {a['number']}: {a['text'][:40]}...")
assert len(articles) == 6, f"Expected 6 articles, got {len(articles)}"
print("\n=== Test PASSED ===")