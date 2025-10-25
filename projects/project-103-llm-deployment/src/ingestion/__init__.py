"""Document ingestion module"""

from .loader import (
    Document,
    DocumentLoader,
    TextLoader,
    PDFLoader,
    HTMLLoader,
    MarkdownLoader,
    CSVLoader,
    JSONLoader,
    DirectoryLoader,
    get_loader,
)
from .processor import (
    DocumentProcessor,
    TextNormalizer,
    DocumentDeduplicator,
)

__all__ = [
    "Document",
    "DocumentLoader",
    "TextLoader",
    "PDFLoader",
    "HTMLLoader",
    "MarkdownLoader",
    "CSVLoader",
    "JSONLoader",
    "DirectoryLoader",
    "get_loader",
    "DocumentProcessor",
    "TextNormalizer",
    "DocumentDeduplicator",
]
