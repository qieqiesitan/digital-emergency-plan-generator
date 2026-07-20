import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/emergency_plan")

from app.regulations.retriever import _match_section_topics
from app.regulations import get_retriever

r = get_retriever()

# 1. Test _match_section_topics
for key, title in [("sec_1","编制依据"),("sec_2","风险评估")]:
    st = _match_section_topics(key, title)
    print(f"match_section({key},{title}) -> {st}")

# 2. Test article loading
art_count = len(r.graph.get_articles_by_regulation("std_gbt29639_2020"))
print(f"std_gbt29639_2020 articles: {art_count}")

# 3. Test _graph_article_recall directly
sec_topics = _match_section_topics("sec_2", "风险评估")
cands = r._graph_article_recall("comprehensive", sec_topics)
print(f"_graph_article_recall(comprehensive, sec_topics) -> {len(cands)} candidates")

cands2 = r._graph_article_recall("comprehensive", [])
print(f"_graph_article_recall(comprehensive, []) -> {len(cands2)} candidates")

# 4. Test retrieve_articles
result = r.retrieve_articles("comprehensive", section_key="sec_2", section_title="风险评估", enterprise_data={})
print(f"retrieve_articles(sec_2) -> {len(result.get('articles',[]))} articles")

result2 = r.retrieve_articles("comprehensive", section_key="sec_1", section_title="编制依据", enterprise_data={})
print(f"retrieve_articles(sec_1) -> {len(result2.get('articles',[]))} articles")

if result.get("articles"):
    print(f"SAMPLE: {result['articles'][0].candidate.article_number} | {result['articles'][0].candidate.article_text[:50]}")
    print(f"  score: {result['articles'][0].score}")