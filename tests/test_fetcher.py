from unittest.mock import patch
from src import fetcher

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>test</title>
<item><title>Microsoft investasi di Indonesia - Kompas</title>
<link>https://news.google.com/rss/articles/abc?hl=id</link>
<source url="https://kompas.com">Kompas</source>
<pubDate>Mon, 10 Mar 2025 07:00:00 GMT</pubDate>
<description>Snippet here</description></item>
</channel></rss>"""

def test_fetch_keyword_rss_parses_fields():
    class FakeResp:
        text = SAMPLE_RSS
        status_code = 200
        def raise_for_status(self): pass
    with patch("src.fetcher._get", return_value=FakeResp()):
        rows = fetcher.fetch_keyword_rss("investasi microsoft di Indonesia tahun 2025", "id", "ID", "ID:id")
    assert len(rows) == 1
    assert rows[0]["publisher"] == "Kompas"
    assert "Microsoft" in rows[0]["title"]
    assert rows[0]["keyword"].startswith("investasi")
