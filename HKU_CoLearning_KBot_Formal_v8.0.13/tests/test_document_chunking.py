from __future__ import annotations

import unittest
from pathlib import Path

from knowledge_service.document_parser import parse_document, split_chunks


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "test_data" / "Ch-3_Enabling_Technologies_2025.pdf"


def _page(pages, number: int):
    return next(page for page in pages if page.page == number)


class DocumentChunkingTests(unittest.TestCase):
    def setUp(self):
        self.pages = parse_document(PDF.read_bytes(), PDF.name)
        self.chunks = split_chunks(self.pages)

    def test_bullet_slide_stays_in_one_chunk(self):
        chunks = [chunk for chunk in self.chunks if chunk["page"] == 12]

        self.assertEqual(len(chunks), 1)
        text = chunks[0]["text"]
        self.assertIn("Spinning Motion", text)
        self.assertIn("Conservation of Angular Momentum", text)
        self.assertIn("Precession", text)
        self.assertNotIn("Courtesy:", text)

    def test_table_page_becomes_sentence_like_row_chunks(self):
        page = _page(self.pages, 35)
        chunks = [chunk for chunk in self.chunks if chunk["page"] == 35]

        self.assertEqual(len(chunks), 2)
        self.assertEqual(page.blocks[0].text, "Celluar Network")
        self.assertTrue(all(block.kind != "heading" or block.text == "Celluar Network" for block in page.blocks))
        self.assertIn("Technology Type.", chunks[0]["text"])
        self.assertIn("Data Rates.", chunks[0]["text"])
        self.assertIn("Latency.", chunks[1]["text"])
        self.assertIn("Deployment.", chunks[1]["text"])

    def test_appendix_definitions_stay_grouped_by_topic(self):
        chunks = [chunk for chunk in self.chunks if chunk["page"] == 90]

        self.assertEqual(len(chunks), 2)
        self.assertIn("MSC (Mobile Switching Center)", chunks[0]["text"])
        self.assertIn("SGSN (Serving GPRS Support Node)", chunks[0]["text"])
        self.assertIn("Gr/Gs:", chunks[1]["text"])
        self.assertIn("Gi:", chunks[1]["text"])
        self.assertNotIn("Courtesy:", chunks[0]["text"])
        self.assertNotIn("Courtesy:", chunks[1]["text"])


if __name__ == "__main__":
    unittest.main()
