"""Stream parser for handling reasoning tags in streaming responses.

Some models (like DeepSeek) embed reasoning content within <think> tags
in their streaming output. This parser extracts and separates reasoning
from regular content.
"""

from typing import Iterator


class StreamReasoningParser:
    """Parser for extracting reasoning content from streaming responses.

    Handles <think>...</think> tags that some models use for chain-of-thought
    reasoning. The parser maintains state across chunks to properly handle
    tags that span multiple chunks.

    Usage:
        parser = StreamReasoningParser()
        for chunk in stream:
            for text, is_reasoning in parser.process_chunk(chunk.content):
                if is_reasoning:
                    # handle reasoning text
                else:
                    # handle regular content
    """

    def __init__(self):
        """Initialize the parser."""
        self._inside_think = False
        self._buffer = ""

    @property
    def is_inside_think_tag(self) -> bool:
        """Check if currently inside a <think> tag."""
        return self._inside_think

    def process_chunk(self, chunk: str) -> Iterator[tuple[str, bool]]:
        """Process a chunk of text, yielding (text, is_reasoning) pairs.

        Args:
            chunk: The text chunk to process

        Yields:
            Tuples of (text, is_reasoning) where is_reasoning indicates
            whether the text is inside a <think> block
        """
        if not chunk:
            return

        # add chunk to buffer for tag detection
        self._buffer += chunk

        while self._buffer:
            if self._inside_think:
                # look for closing tag
                end_idx = self._buffer.find("</think>")
                if end_idx != -1:
                    # found closing tag - yield reasoning content
                    reasoning_text = self._buffer[:end_idx]
                    if reasoning_text:
                        yield (reasoning_text, True)
                    self._buffer = self._buffer[end_idx + 8:]  # skip </think>
                    self._inside_think = False
                else:
                    # no closing tag yet - check for partial tag
                    # keep potential partial tag in buffer
                    if len(self._buffer) > 8 and "</think"[:7] not in self._buffer[-7:]:
                        # safe to yield - no partial closing tag
                        yield (self._buffer, True)
                        self._buffer = ""
                    elif "</think"[:1] in self._buffer:
                        # might have partial tag - find safe point
                        safe_idx = self._find_safe_index(self._buffer, "</think>")
                        if safe_idx > 0:
                            yield (self._buffer[:safe_idx], True)
                            self._buffer = self._buffer[safe_idx:]
                        break
                    else:
                        yield (self._buffer, True)
                        self._buffer = ""
                    break
            else:
                # look for opening tag
                start_idx = self._buffer.find("<think>")
                if start_idx != -1:
                    # found opening tag - yield content before it
                    if start_idx > 0:
                        yield (self._buffer[:start_idx], False)
                    self._buffer = self._buffer[start_idx + 7:]  # skip <think>
                    self._inside_think = True
                else:
                    # no opening tag - check for partial tag
                    if len(self._buffer) > 7 and "<think"[:6] not in self._buffer[-6:]:
                        # safe to yield - no partial opening tag
                        yield (self._buffer, False)
                        self._buffer = ""
                    elif "<think"[:1] in self._buffer:
                        # might have partial tag - find safe point
                        safe_idx = self._find_safe_index(self._buffer, "<think>")
                        if safe_idx > 0:
                            yield (self._buffer[:safe_idx], False)
                            self._buffer = self._buffer[safe_idx:]
                        break
                    else:
                        yield (self._buffer, False)
                        self._buffer = ""
                    break

    def _find_safe_index(self, text: str, tag: str) -> int:
        """Find the last index that's safe to yield without breaking a potential tag.

        Args:
            text: The text to search in
            tag: The tag we're looking for

        Returns:
            The index up to which it's safe to yield
        """
        # check for partial matches at the end of text
        for i in range(1, len(tag)):
            if text.endswith(tag[:i]):
                return len(text) - i
        return len(text)

    def flush(self) -> Iterator[tuple[str, bool]]:
        """Flush any remaining content in the buffer.

        Should be called at the end of a stream to get any remaining content.

        Yields:
            Tuples of (text, is_reasoning) for any remaining buffered content
        """
        if self._buffer:
            yield (self._buffer, self._inside_think)
            self._buffer = ""

    def reset(self) -> None:
        """Reset the parser state."""
        self._inside_think = False
        self._buffer = ""
