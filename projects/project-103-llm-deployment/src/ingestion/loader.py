"""
Document loaders for various file formats

Supports: PDF, TXT, MD, HTML, DOCX, CSV, JSON
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import mimetypes

logger = logging.getLogger(__name__)


class Document:
    """Document container"""

    def __init__(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ):
        self.text = text
        self.metadata = metadata or {}
        self.doc_id = doc_id or metadata.get("id", "")


class DocumentLoader:
    """
    Base document loader
    """

    def load(self, file_path: str) -> List[Document]:
        """Load documents from file"""
        raise NotImplementedError

    def load_batch(self, file_paths: List[str]) -> List[Document]:
        """Load multiple files"""
        documents = []
        for file_path in file_paths:
            try:
                docs = self.load(file_path)
                documents.extend(docs)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        return documents


class TextLoader(DocumentLoader):
    """Load plain text files"""

    def load(self, file_path: str) -> List[Document]:
        """Load text file"""
        path = Path(file_path)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        metadata = {
            "source": str(path),
            "filename": path.name,
            "file_type": "txt",
        }

        return [Document(text=text, metadata=metadata, doc_id=path.stem)]


class PDFLoader(DocumentLoader):
    """Load PDF files"""

    def __init__(self, extract_images: bool = False):
        self.extract_images = extract_images

        try:
            import pypdf
            self.pypdf = pypdf
        except ImportError:
            logger.warning("pypdf not available. Install with: pip install pypdf")
            self.pypdf = None

    def load(self, file_path: str) -> List[Document]:
        """Load PDF file"""
        if self.pypdf is None:
            raise ImportError("pypdf required for PDF loading")

        path = Path(file_path)
        documents = []

        with open(path, "rb") as f:
            pdf_reader = self.pypdf.PdfReader(f)

            # Extract text from all pages
            full_text = []
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    full_text.append(page_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {i}: {e}")

            text = "\n\n".join(full_text)

            # Get metadata
            metadata = {
                "source": str(path),
                "filename": path.name,
                "file_type": "pdf",
                "num_pages": len(pdf_reader.pages),
            }

            # Add PDF metadata if available
            if pdf_reader.metadata:
                for key, value in pdf_reader.metadata.items():
                    if key.startswith("/"):
                        key = key[1:]
                    metadata[f"pdf_{key}"] = str(value)

            documents.append(Document(text=text, metadata=metadata, doc_id=path.stem))

        return documents


class HTMLLoader(DocumentLoader):
    """Load HTML files"""

    def __init__(self):
        try:
            from bs4 import BeautifulSoup
            self.BeautifulSoup = BeautifulSoup
        except ImportError:
            logger.warning(
                "BeautifulSoup not available. Install with: pip install beautifulsoup4"
            )
            self.BeautifulSoup = None

    def load(self, file_path: str) -> List[Document]:
        """Load HTML file"""
        if self.BeautifulSoup is None:
            raise ImportError("beautifulsoup4 required for HTML loading")

        path = Path(file_path)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        # Parse HTML
        soup = self.BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Get title if available
        title = soup.title.string if soup.title else path.name

        metadata = {
            "source": str(path),
            "filename": path.name,
            "file_type": "html",
            "title": title,
        }

        return [Document(text=text, metadata=metadata, doc_id=path.stem)]


class MarkdownLoader(DocumentLoader):
    """Load Markdown files"""

    def load(self, file_path: str) -> List[Document]:
        """Load Markdown file"""
        path = Path(file_path)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Extract title from first heading if present
        lines = text.split("\n")
        title = path.name
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        metadata = {
            "source": str(path),
            "filename": path.name,
            "file_type": "markdown",
            "title": title,
        }

        return [Document(text=text, metadata=metadata, doc_id=path.stem)]


class CSVLoader(DocumentLoader):
    """Load CSV files"""

    def __init__(self, text_column: Optional[str] = None):
        self.text_column = text_column

    def load(self, file_path: str) -> List[Document]:
        """Load CSV file"""
        import csv

        path = Path(file_path)
        documents = []

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):
                # Determine text content
                if self.text_column and self.text_column in row:
                    text = row[self.text_column]
                else:
                    # Concatenate all columns
                    text = " | ".join(f"{k}: {v}" for k, v in row.items())

                metadata = {
                    "source": str(path),
                    "filename": path.name,
                    "file_type": "csv",
                    "row_number": i,
                    **row,
                }

                documents.append(
                    Document(text=text, metadata=metadata, doc_id=f"{path.stem}_{i}")
                )

        return documents


class JSONLoader(DocumentLoader):
    """Load JSON files"""

    def __init__(self, text_key: str = "text"):
        self.text_key = text_key

    def load(self, file_path: str) -> List[Document]:
        """Load JSON file"""
        import json

        path = Path(file_path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        documents = []

        # Handle different JSON structures
        if isinstance(data, list):
            # List of documents
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    text = item.get(self.text_key, str(item))
                    metadata = {
                        "source": str(path),
                        "filename": path.name,
                        "file_type": "json",
                        "index": i,
                        **{k: v for k, v in item.items() if k != self.text_key},
                    }
                else:
                    text = str(item)
                    metadata = {
                        "source": str(path),
                        "filename": path.name,
                        "file_type": "json",
                        "index": i,
                    }

                documents.append(
                    Document(text=text, metadata=metadata, doc_id=f"{path.stem}_{i}")
                )

        elif isinstance(data, dict):
            # Single document
            text = data.get(self.text_key, str(data))
            metadata = {
                "source": str(path),
                "filename": path.name,
                "file_type": "json",
                **{k: v for k, v in data.items() if k != self.text_key},
            }
            documents.append(Document(text=text, metadata=metadata, doc_id=path.stem))

        return documents


class DirectoryLoader(DocumentLoader):
    """Load all documents from a directory"""

    def __init__(
        self,
        glob_pattern: str = "**/*",
        exclude_patterns: Optional[List[str]] = None,
        loader_map: Optional[Dict[str, DocumentLoader]] = None,
    ):
        """
        Initialize directory loader

        Args:
            glob_pattern: Glob pattern for file matching
            exclude_patterns: Patterns to exclude
            loader_map: Map of file extensions to loaders
        """
        self.glob_pattern = glob_pattern
        self.exclude_patterns = exclude_patterns or []

        # Default loader map
        self.loader_map = loader_map or {
            ".txt": TextLoader(),
            ".md": MarkdownLoader(),
            ".pdf": PDFLoader(),
            ".html": HTMLLoader(),
            ".htm": HTMLLoader(),
            ".csv": CSVLoader(),
            ".json": JSONLoader(),
        }

    def load(self, directory_path: str) -> List[Document]:
        """Load all documents from directory"""
        path = Path(directory_path)

        if not path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")

        documents = []
        file_paths = list(path.glob(self.glob_pattern))

        logger.info(f"Found {len(file_paths)} files in {directory_path}")

        for file_path in file_paths:
            # Skip directories
            if file_path.is_dir():
                continue

            # Check exclude patterns
            if any(pattern in str(file_path) for pattern in self.exclude_patterns):
                continue

            # Get appropriate loader
            extension = file_path.suffix.lower()
            loader = self.loader_map.get(extension)

            if loader is None:
                logger.debug(f"No loader for {extension}, skipping {file_path}")
                continue

            try:
                docs = loader.load(str(file_path))
                documents.extend(docs)
                logger.debug(f"Loaded {len(docs)} documents from {file_path}")
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(documents)} documents total")
        return documents


def get_loader(file_path: str) -> DocumentLoader:
    """
    Get appropriate loader for file

    Args:
        file_path: Path to file

    Returns:
        Document loader instance
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    loader_map = {
        ".txt": TextLoader(),
        ".md": MarkdownLoader(),
        ".pdf": PDFLoader(),
        ".html": HTMLLoader(),
        ".htm": HTMLLoader(),
        ".csv": CSVLoader(),
        ".json": JSONLoader(),
    }

    loader = loader_map.get(extension)

    if loader is None:
        # Try to guess from mimetype
        mimetype, _ = mimetypes.guess_type(str(path))
        if mimetype and mimetype.startswith("text"):
            loader = TextLoader()
        else:
            raise ValueError(f"No loader available for {extension}")

    return loader
