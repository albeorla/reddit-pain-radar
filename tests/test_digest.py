import pytest
from pain_radar.digest import generate_weekly_digest, generate_digest_title, generate_comment_reply
from pain_radar.models import Cluster

@pytest.fixture
def sample_clusters():
    return [
        Cluster(
            title="Pain X", 
            summary="User cannot find Y", 
            target_audience="Founders", 
            why_it_matters="High demand", 
            signal_ids=[1], 
            quotes=["I hate Y"], 
            urls=["http://reddit.com/1"]
        ),
        Cluster(
            title="Pain Z", 
            summary="Tool A is slow", 
            target_audience="Developers", 
            why_it_matters="Niche opportunity", 
            signal_ids=[2], 
            quotes=["A takes forever"], 
            urls=["http://reddit.com/2"]
        )
    ]

def test_generate_digest_title(sample_clusters):
    title = generate_digest_title(sample_clusters, "SideProject")
    assert "Top 2" in title
    assert "r/SideProject" in title

def test_generate_weekly_digest_reddit(sample_clusters):
    digest = generate_weekly_digest(sample_clusters, "SideProject", format_type="reddit")
    
    assert "### 1. Pain X" in digest
    assert "**The pattern:** User cannot find Y" in digest
    assert "I hate Y" in digest
    assert "r/SideProject" in digest
    assert "**Who this affects:** Founders" in digest
    assert "### 2. Pain Z" in digest
    assert "A takes forever" in digest

def test_generate_weekly_digest_archive(sample_clusters):
    digest = generate_weekly_digest(sample_clusters, "SideProject", format_type="archive")
    
    assert "# Pain Clusters Archive: r/SideProject" in digest
    assert "## 1. Pain X" in digest
    assert "**Why it matters:** High demand" in digest
    assert "## 2. Pain Z" in digest
    assert "**Why it matters:** Niche opportunity" in digest
    assert "## Methodology" in digest

def test_generate_weekly_digest_markdown(sample_clusters):
    digest = generate_weekly_digest(sample_clusters, "SideProject", format_type="markdown")
    
    assert "# Weekly Pain Clusters: r/SideProject" in digest
    assert "Found **2 pain clusters**" in digest
    assert "## 1. Pain X" in digest
    assert "**Opportunity:** High demand" in digest

def test_generate_comment_reply():
    reply = generate_comment_reply(
        pattern_summary="Lack of tool Z",
        similar_count=14,
        common_approaches=["Google", "Manual"],
        thread_links=["http://link1"]
    )
    assert "14+ similar posts" in reply
    assert "Lack of tool Z" in reply
    assert "Google, Manual" in reply
    assert "http://link1" in reply