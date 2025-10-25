"""
Document processing and cleaning

Text extraction, cleaning, and normalization
"""

import logging
import re
from typing import List, Optional
from .loader import Document

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Process and clean documents
    """

    def __init__(
        self,
        remove_extra_whitespace: bool = True,
        remove_urls: bool = False,
        remove_emails: bool = False,
        lowercase: bool = False,
        min_length: int = 10,
    ):
        """
        Initialize document processor

        Args:
            remove_extra_whitespace: Remove extra whitespace
            remove_urls: Remove URLs
            remove_emails: Remove email addresses
            lowercase: Convert to lowercase
            min_length: Minimum document length (characters)
        """
        self.remove_extra_whitespace = remove_extra_whitespace
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.lowercase = lowercase
        self.min_length = min_length

    def process(self, document: Document) -> Optional[Document]:
        """
        Process a single document

        Args:
            document: Document to process

        Returns:
            Processed document or None if filtered out
        """
        text = document.text

        # Clean text
        text = self.clean_text(text)

        # Check minimum length
        if len(text) < self.min_length:
            logger.debug(
                f"Document {document.doc_id} too short ({len(text)} chars), skipping"
            )
            return None

        # Update document
        document.text = text
        document.metadata["processed"] = True
        document.metadata["original_length"] = len(document.text)
        document.metadata["processed_length"] = len(text)

        return document

    def process_batch(self, documents: List[Document]) -> List[Document]:
        """
        Process multiple documents

        Args:
            documents: List of documents

        Returns:
            List of processed documents (filtered)
        """
        processed = []

        for doc in documents:
            processed_doc = self.process(doc)
            if processed_doc is not None:
                processed.append(processed_doc)

        logger.info(
            f"Processed {len(processed)}/{len(documents)} documents "
            f"({len(documents) - len(processed)} filtered out)"
        )

        return processed

    def clean_text(self, text: str) -> str:
        """
        Clean text

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Remove URLs
        if self.remove_urls:
            text = re.sub(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                '',
                text,
            )

        # Remove emails
        if self.remove_emails:
            text = re.sub(r'\S+@\S+', '', text)

        # Remove extra whitespace
        if self.remove_extra_whitespace:
            # Replace multiple spaces with single space
            text = re.sub(r' +', ' ', text)
            # Replace multiple newlines with double newline
            text = re.sub(r'\n\n+', '\n\n', text)
            # Remove leading/trailing whitespace
            text = text.strip()

        # Convert to lowercase
        if self.lowercase:
            text = text.lower()

        return text

    def extract_metadata(self, document: Document) -> dict:
        """
        Extract additional metadata from document

        Args:
            document: Document to analyze

        Returns:
            Extracted metadata
        """
        text = document.text

        metadata = {
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split("\n")),
        }

        # Count sentences (rough approximation)
        sentence_endings = re.findall(r'[.!?]+', text)
        metadata["sentence_count"] = len(sentence_endings)

        # Detect language (very basic)
        # Count common English words
        common_words = ["the", "a", "an", "and", "or", "but", "in", "on", "at"]
        word_list = text.lower().split()
        english_word_count = sum(1 for word in word_list if word in common_words)
        if len(word_list) > 0:
            english_ratio = english_word_count / len(word_list)
            metadata["likely_english"] = english_ratio > 0.05

        return metadata


class TextNormalizer:
    """
    Normalize text for better retrieval
    """

    def __init__(
        self,
        expand_contractions: bool = True,
        remove_accents: bool = False,
        normalize_unicode: bool = True,
    ):
        """
        Initialize text normalizer

        Args:
            expand_contractions: Expand contractions (don't -> do not)
            remove_accents: Remove accents from characters
            normalize_unicode: Normalize unicode characters
        """
        self.expand_contractions = expand_contractions
        self.remove_accents = remove_accents
        self.normalize_unicode = normalize_unicode

        # Contraction map
        self.contractions = {
            "don't": "do not",
            "doesn't": "does not",
            "didn't": "did not",
            "can't": "cannot",
            "won't": "will not",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "couldn't": "could not",
            "isn't": "is not",
            "aren't": "are not",
            "wasn't": "was not",
            "weren't": "were not",
            "haven't": "have not",
            "hasn't": "has not",
            "hadn't": "had not",
            "it's": "it is",
            "that's": "that is",
            "what's": "what is",
            "there's": "there is",
            "i'm": "i am",
            "you're": "you are",
            "we're": "we are",
            "they're": "they are",
            "i've": "i have",
            "you've": "you have",
            "we've": "we have",
            "they've": "they have",
            "i'll": "i will",
            "you'll": "you will",
            "we'll": "we will",
            "they'll": "they will",
        }

    def normalize(self, text: str) -> str:
        """
        Normalize text

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Normalize unicode
        if self.normalize_unicode:
            import unicodedata

            text = unicodedata.normalize("NFKC", text)

        # Remove accents
        if self.remove_accents:
            import unicodedata

            text = "".join(
                c
                for c in unicodedata.normalize("NFD", text)
                if unicodedata.category(c) != "Mn"
            )

        # Expand contractions
        if self.expand_contractions:
            for contraction, expansion in self.contractions.items():
                # Case insensitive replacement
                pattern = re.compile(re.escape(contraction), re.IGNORECASE)
                text = pattern.sub(expansion, text)

        return text


class DocumentDeduplicator:
    """
    Remove duplicate documents
    """

    def __init__(self, similarity_threshold: float = 0.95):
        """
        Initialize deduplicator

        Args:
            similarity_threshold: Threshold for considering documents duplicates
        """
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, documents: List[Document]) -> List[Document]:
        """
        Remove duplicate documents

        Args:
            documents: List of documents

        Returns:
            Deduplicated list
        """
        if not documents:
            return []

        # Use exact text matching for now (can be improved with fuzzy matching)
        seen_texts = set()
        unique_docs = []

        for doc in documents:
            text_normalized = doc.text.strip().lower()

            if text_normalized not in seen_texts:
                seen_texts.add(text_normalized)
                unique_docs.append(doc)
            else:
                logger.debug(f"Removing duplicate document: {doc.doc_id}")

        logger.info(
            f"Removed {len(documents) - len(unique_docs)} duplicates "
            f"({len(unique_docs)} unique documents)"
        )

        return unique_docs

    def deduplicate_fuzzy(
        self, documents: List[Document], embedding_model=None
    ) -> List[Document]:
        """
        Remove duplicates using fuzzy matching

        Args:
            documents: List of documents
            embedding_model: Embedding model for similarity

        Returns:
            Deduplicated list
        """
        if not documents or embedding_model is None:
            return self.deduplicate(documents)

        # Generate embeddings
        texts = [doc.text for doc in documents]
        embeddings = embedding_model.encode(texts)

        # Find duplicates using cosine similarity
        unique_indices = [0]  # Always keep first document

        for i in range(1, len(documents)):
            is_duplicate = False

            for j in unique_indices:
                similarity = embedding_model.similarity(embeddings[i], embeddings[j])

                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"Document {i} is duplicate of {j} (similarity: {similarity:.3f})"
                    )
                    break

            if not is_duplicate:
                unique_indices.append(i)

        unique_docs = [documents[i] for i in unique_indices]

        logger.info(
            f"Fuzzy deduplication: {len(unique_docs)}/{len(documents)} unique documents"
        )

        return unique_docs
