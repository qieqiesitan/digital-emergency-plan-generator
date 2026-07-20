"""数据迁移脚本: 对现有法规回填 article 子节点 + 更新向量索引 + 重建 index.yaml。

用法:
  cd backend
  python scripts/migrate_to_article_level.py
"""

import os, re, sys, logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('migrate')

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.regulations.graph import RegulationGraph
from app.regulations.article_index import ArticleIndexManager


def main():
    graph = RegulationGraph()
    graph.load()
    logger.info('Graph loaded: %d nodes, %d edges',
                graph._g.number_of_nodes(), graph._g.number_of_edges())

    texts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'app', 'regulations', 'data', 'texts'
    )

    if not os.path.isdir(texts_dir):
        logger.error('texts dir not found: %s', texts_dir)
        return

    stats = {'processed': 0, 'articles_created': 0, 'already_exist': 0, 'errors': 0}

    for fname in sorted(os.listdir(texts_dir)):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(texts_dir, fname)
        reg_id = fname.replace('.md', '')

        # Load .md content
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error('Read error %s: %s', fname, e)
            stats['errors'] += 1
            continue

        # Parse articles by ## headings
        blocks = re.split(r'\n(?=##\s)', content)
        count = 0
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            title = lines[0].lstrip('#').strip() if lines else ''
            text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
            if not text or len(text) < 10:
                continue
            try:
                aid = graph.add_article_node(reg_id, {'number': title, 'text': text})
                count += 1
                stats['articles_created'] += 1
            except Exception:
                stats['already_exist'] += 1

        if count > 0:
            logger.info('  %s: %d articles backfilled', fname, count)
        stats['processed'] += 1

    graph.save()
    logger.info('Backfill done: %d regs, %d articles created, %d existed, %d errors',
                stats['processed'], stats['articles_created'],
                stats['already_exist'], stats['errors'])

    # Step 2: Rebuild index.yaml
    logger.info('Rebuilding index.yaml ...')
    idx_stats = ArticleIndexManager.rebuild_index()
    logger.info('Index rebuilt: %s', idx_stats)

    # Step 3: Vector index (requires chromadb installed)
    logger.info('Vector index: run POST /regulations/rebuild-index API after starting server')
    logger.info('  (requires AI config set up for embedding API)')

    # Step 4: BM25 index (NEW V2.0)
    logger.info('Rebuilding BM25 index ...')
    try:
        from app.regulations.bm25_index import BM25ArticleIndex
        bm25 = BM25ArticleIndex()
        bm25_result = bm25.rebuild_all()
        logger.info('BM25 rebuilt: %s', bm25_result)
    except Exception as e:
        logger.warning('BM25 rebuild skipped: %s', e)

    return stats


if __name__ == '__main__':
    main()
