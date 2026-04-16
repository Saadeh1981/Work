from backend.services.evidence_builder import build_evidence


def main() -> None:
    result = build_evidence(
        file_name="sample.docx",
        snippet="Plant Name: Bromptonville Hydro Station",
        method="docx_paragraph",
        block_index=0,
        file_type="docx",
        page=None,
        confidence=0.8,
    )

    print(result)


if __name__ == "__main__":
    main()