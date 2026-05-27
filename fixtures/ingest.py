import os
import time
import argparse
import sys
from pathlib import Path

from db.database import Database
from tools.rag import RagTools

# Settings
os.environ["RAG_LOCAL_FILES_ONLY"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def cmd_import(args):
    db = Database()
    rag = RagTools(db)
    t0 = time.monotonic()

    def progress(stage, **kw):
        print(f"\n  [{stage.upper()}] ", end="", flush=True)

    try:
        result = rag.import_document(
            path=args.path,
            discipline_id=args.discipline_id,
            title=args.title,
            on_progress=progress,
        )
        print(f"  done — {result.chunks_count} chunks, {time.monotonic()-t0:.1f}s")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERR {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_list(args):
    """Показать загруженные документы."""
    db = Database()
    rag = RagTools(db)

    docs = rag.list_documents(discipline_id=args.discipline_id)
    if not docs:
        print("Документов нет.")
        return

    for doc in docs:
        print(f"  {doc.id}  {doc.title}  ({doc.mime_type})  {doc.source_path}")
    print(f"\nВсего: {len(docs)}")
    db.close()


def cmd_search(args):
    """Тестовый поиск по документам (без MCP-сервера)."""
    db = Database()
    rag = RagTools(db)

    results = rag.search_documents(
        query=args.query,
        discipline_id=args.discipline_id,
        limit=args.limit,
    )
    if not results:
        print("Ничего не найдено.")
        return

    for i, r in enumerate(results, 1):
        page_str = f"стр.{r.page}" if r.page is not None else "без стр."
        print(f"\n--- [{i}] score={r.score:.4f}  {r.document_title}  {page_str} ---")
        print(r.content[:500])
        if len(r.content) > 500:
            print("...")
    db.close()


def cmd_delete(args):
    """Удалить документ из индекса."""
    db = Database()
    cursor = db.conn.cursor()

    # По пути или по id
    if args.path:
        source_path = str(Path(args.path).resolve())
        row = cursor.execute(
            "SELECT id, title FROM documents WHERE source_path = ?",
            (source_path,),
        ).fetchone()
    elif args.document_id:
        row = cursor.execute(
            "SELECT id, title FROM documents WHERE id = ?",
            (args.document_id,),
        ).fetchone()
    else:
        print("ERR укажите --path или --document-id", file=sys.stderr)
        sys.exit(1)

    if not row:
        print("Документ не найден.")
        db.close()
        return

    doc_id = row["id"]
    title = row["title"]
    rag = RagTools(db)
    rag._delete_document_vectors(doc_id)
    cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    db.conn.commit()
    print(f"OK  удалён: {title} ({doc_id})")
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Управление документами RAG-системы agent-tutor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # import
    p_import = sub.add_parser("import", help="Загрузить документ в индекс")
    p_import.add_argument("path", help="Путь к файлу (PDF, DOCX, TXT, MD, HTML)")
    p_import.add_argument("--discipline-id", "-d", help="ID дисциплины для привязки")
    p_import.add_argument("--title", "-t", help="Название документа")
    p_import.set_defaults(func=cmd_import)

    # list
    p_list = sub.add_parser("list", help="Показать загруженные документы")
    p_list.add_argument("--discipline-id", "-d", help="Фильтр по дисциплине")
    p_list.set_defaults(func=cmd_list)

    # search
    p_search = sub.add_parser("search", help="Тестовый поиск по документам")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--discipline-id", "-d", help="Фильтр по дисциплине")
    p_search.add_argument("--limit", "-n", type=int, default=5, help="Кол-во результатов")
    p_search.set_defaults(func=cmd_search)

    # delete
    p_delete = sub.add_parser("delete", help="Удалить документ из индекса")
    p_delete.add_argument("--path", help="Путь к файлу документа")
    p_delete.add_argument("--document-id", help="ID документа")
    p_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    print("Ingest script started")
    main()
