"""CLI entrypoint for RAG retrieval pipeline."""

from __future__ import annotations

import argparse

from analyzers.query_analyzer import QueryDrivenAnalyzer
from pipelines.rag_pipeline import RAGPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Retrieval Pipeline")
    parser.add_argument("repo", help="Path to repository")
    parser.add_argument("--query", required=True, help="Question to search")
    parser.add_argument("--queries-file", help="File with queries (one per line)")
    parser.add_argument("--top-k", type=int, default=10, help="Top K results")
    parser.add_argument("--session-dir", help="Session directory for persistence")
    parser.add_argument("--export", help="Export results to JSON")
    parser.add_argument("--no-freshness-boost", action="store_true")
    parser.add_argument("--no-embeddings", action="store_true")
    parser.add_argument("--detailed-output", action="store_true", help="Show detailed per-result output")
    parser.add_argument("--show-evidence", action="store_true", help="Also print commit-level evidence")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    analyzer = QueryDrivenAnalyzer(
        args.repo,
        use_embeddings=not args.no_embeddings,
        session_dir=args.session_dir,
    )

    if args.session_dir:
        if not analyzer.load_session():
            analyzer.index_repository()
    else:
        analyzer.index_repository()

    rag = RAGPipeline(analyzer, verbose=True)

    if args.query:
        results = rag.retrieve(
            args.query,
            top_k=args.top_k,
            boost_freshness=not args.no_freshness_boost,
        )

        final_answer = rag.synthesize_answer(args.query, results)

        print("\n" + "=" * 80)
        print("Final Answer")
        print("=" * 80)
        print(final_answer)

        if args.show_evidence:
            print("\n" + "=" * 80)
            print("Evidence Commits")
            print("=" * 80)
            for index, result in enumerate(results, 1):
                print(f"\n{index}. {rag.explain_result(result, detailed=args.detailed_output)}")
            print("=" * 80)

        if args.export:
            rag.export_results(results, args.export)

    elif args.queries_file:
        with open(args.queries_file, "r") as handle:
            queries = [line.strip() for line in handle if line.strip()]

        batch_results = rag.batch_retrieve(queries, top_k=args.top_k)

        for query, query_results in batch_results.items():
            print(f"\nQuery: {query}")
            print(f"Results: {len(query_results)}")
            for result in query_results[:3]:
                print(f"  - {result.short_hash}: {result.message[:40]}")

        if args.export:
            rag.export_results(
                [item for query_results in batch_results.values() for item in query_results],
                args.export,
                include_history=True,
            )


if __name__ == "__main__":
    main()
