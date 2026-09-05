"""ADR-0003: synthetic regressions for the shared XML input guard."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
from xml.etree.ElementTree import ParseError, XMLPullParser

import pytest

from serenata.eforms import CHUNK_BYTES, HEADER_BYTES, NoticeRejected, stream_elements

ENTITY_DOCUMENT = (
    '<!DOCTYPE x [<!ENTITY harmless "SYNTHETIC_ENTITY">]><x>&harmless;</x>'
)


class ShortReads(BytesIO):
    """Return at most a few bytes, including on the initial header read."""

    def __init__(self, data: bytes, limit: int) -> None:
        super().__init__(data)
        self.limit = limit

    def read(self, size: int | None = -1) -> bytes:
        return super().read(
            self.limit if size is None or size < 0 else min(size, self.limit)
        )


class TestXmlInputGuard:
    @pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
    def test_bomless_utf16_entity_document_is_refused(self, encoding: str) -> None:
        # Before the fix both byte orders yielded SYNTHETIC_ENTITY. This is a
        # small internal entity, not evidence of XXE or resource exhaustion.
        with pytest.raises(NoticeRejected, match="cannot scan"):
            list(stream_elements(BytesIO(ENTITY_DOCUMENT.encode(encoding))))

    @pytest.mark.parametrize("read_size", [1, 2, 3, 4, HEADER_BYTES])
    @pytest.mark.parametrize(
        ("encoding", "bom"),
        [
            ("utf-16-le", b""),
            ("utf-16-be", b""),
            ("utf-16-le", b"\xff\xfe"),
            ("utf-16-be", b"\xfe\xff"),
            ("utf-32-le", b""),
            ("utf-32-be", b""),
            ("utf-32-le", b"\xff\xfe\x00\x00"),
            ("utf-32-be", b"\x00\x00\xfe\xff"),
        ],
    )
    @pytest.mark.parametrize("prolog", ["", '<?xml version="1.0"?>', " \t\r\n"])
    def test_unscannable_encoding_never_reaches_parser_feed(
        self, encoding: str, bom: bytes, prolog: str, read_size: int
    ) -> None:
        document = bom + (prolog + ENTITY_DOCUMENT).encode(encoding)
        with patch.object(
            XMLPullParser, "feed", autospec=True, side_effect=XMLPullParser.feed
        ) as feed:
            with pytest.raises(NoticeRejected, match="cannot scan"):
                list(stream_elements(ShortReads(document, read_size)))
            feed.assert_not_called()

    @pytest.mark.parametrize("read_size", [1, 2, 3, HEADER_BYTES])
    def test_non_ascii_xml_signature_is_refused(self, read_size: int) -> None:
        # EBCDIC's XML declaration signature is not ASCII-compatible either.
        document = ('<?xml version="1.0"?>' + ENTITY_DOCUMENT).encode("cp037")
        with pytest.raises(NoticeRejected, match="cannot scan"):
            list(stream_elements(ShortReads(document, read_size)))

    @pytest.mark.parametrize("read_size", [1, 2, 3, 4, HEADER_BYTES])
    @pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
    @pytest.mark.parametrize(
        "prolog", ["", '<?xml version="1.0" encoding="UTF-8"?>', " \t\r\n"]
    )
    def test_utf8_survives_split_bom_and_multibyte_characters(
        self, read_size: int, bom: bytes, prolog: str
    ) -> None:
        document = bom + (prolog + "<é>SYNTHETIC — € 😀 &amp; &#65;</é>").encode()
        values = [
            (name, node.text)
            for event, name, node in stream_elements(ShortReads(document, read_size))
            if event == "end"
        ]
        assert values == [("é", "SYNTHETIC — € 😀 & A")]

    def test_ascii_compatible_declared_encoding_is_not_utf8_validation(self) -> None:
        document = (
            '<?xml version="1.0" encoding="ISO-8859-1"?><x>SYNTHETIC é</x>'
        ).encode("iso-8859-1")
        values = [
            node.text
            for event, _, node in stream_elements(ShortReads(document, 1))
            if event == "end"
        ]
        assert values == ["SYNTHETIC é"]

    @pytest.mark.parametrize("read_size", [1, 2, 3, HEADER_BYTES])
    @pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
    def test_utf8_dtd_is_still_refused_on_short_reads(
        self, read_size: int, bom: bytes
    ) -> None:
        with pytest.raises(NoticeRejected, match="document type declaration"):
            list(stream_elements(ShortReads(bom + ENTITY_DOCUMENT.encode(), read_size)))

    @pytest.mark.parametrize("boundary", [HEADER_BYTES, HEADER_BYTES + CHUNK_BYTES])
    @pytest.mark.parametrize("split", range(1, len("<!DOCTYPE")))
    def test_every_dtd_marker_split_at_actual_read_boundaries_is_refused(
        self, boundary: int, split: int
    ) -> None:
        # Place the marker precisely, unlike padding that only approximates
        # the read boundary. The comment keeps the entire prefix in the prolog.
        padding = b"<!--" + b"P" * (boundary - split - 7) + b"-->"
        document = padding + ENTITY_DOCUMENT.encode()
        assert document[boundary - split : boundary - split + 9] == b"<!DOCTYPE"
        with pytest.raises(NoticeRejected, match="document type declaration"):
            list(stream_elements(BytesIO(document)))

    @pytest.mark.parametrize("document", [b"", b"<", b"<x", b"   "])
    def test_empty_or_truncated_ascii_remains_a_parse_error(
        self, document: bytes
    ) -> None:
        with pytest.raises(ParseError):
            list(stream_elements(ShortReads(document, 1)))

    @pytest.mark.parametrize("document", [b"\xff", b"\xfe", b"\x00", b"\xef\xbb"])
    def test_truncated_non_ascii_prefix_is_refused_at_eof(
        self, document: bytes
    ) -> None:
        with pytest.raises(NoticeRejected, match="cannot scan"):
            list(stream_elements(ShortReads(document, 1)))

    def test_scan_stops_after_the_root_has_opened(self) -> None:
        padding = "P" * (HEADER_BYTES - len("<x>"))
        document = f"<x>{padding}<![CDATA[<!DOCTYPE x>]]></x>".encode()
        values = [
            node.text
            for event, _, node in stream_elements(BytesIO(document))
            if event == "end"
        ]
        assert values == [padding + "<!DOCTYPE x>"]
