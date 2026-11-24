"""Single source of truth for the xlsx schema and shared corpus constants."""

SCHEMA_VERSION = 3

COLUMNS = [
    "No",
    "Publisher",
    "Publisher_Domain",
    "Source_Type",
    "Query_Group",
    "Found_In_Groups",
    "Title",
    "Snippet",
    "URL",
    "Date",
    "Keyword_Found",
    "Also_Found_In",
    "Source_Lang",
    "Microsoft_Signal",
    "Microsoft_Mention",
    "Analysis_Ready",
    "Government_Body",
    "Fulltext_Status",
    "Docx_File",
]

MICROSOFT_SIGNALS = ("yes", "no")
MICROSOFT_MENTIONS = ("yes", "no", "unknown")
ANALYSIS_STATES = ("yes", "no", "review")

FULLTEXT_STATUSES = (
    "pending",
    "ok",
    "paywall",
    "blocked",
    "removed",
    "thin",
    "fetch_error",
    "decode_failed",
    "internal_error",
)

FAILED_COLUMNS = ["No", "URL", "Resolved_URL", "Publisher", "Keyword_Found", "reason", "stage"]


class SchemaError(ValueError):
    """Raised when an xlsx does not match the current schema."""


def validate_headers(headers):
    """Raise SchemaError listing every missing v3 column."""
    present = set(headers)
    missing = [column for column in COLUMNS if column not in present]
    if missing:
        raise SchemaError(
            "xlsx is missing required schema v3 columns: "
            + ", ".join(missing)
            + "; rebuild it with `uv run python -m src.scrape` or `make legacy`"
        )
