"""Explain: the research lane's text handling and the citation checks (no network, no model)."""
import numpy as np

from replicator.core import explain
from replicator.research import lane

PAGE = """<html><head><title>Thrust reversal - Example</title><script>var x = "ignore me entirely please";</script></head>
<body><nav>Home About Contact and a very long menu line that should never be read as content at all ok</nav>
<p>A thrust reverser works by changing the direction of the exhaust as it leaves a jet engine, so that the flow is
turned partially forwards and slows the aircraft after landing.[1]</p>
<p>Short line.</p>
<p>The fan at the front of a turbofan is driven by the low pressure turbine through a shaft, and most of the air it
moves bypasses the core and produces the majority of the thrust.</p>
<p>The company was founded in 1950 and has offices in several countries around the world with many employees today.</p>
</body></html>"""
SOURCES = [{"n": 1, "title": "Thrust reversal", "url": "https://example.org/a", "domain": "example.org",
            "excerpts": ["A thrust reverser works by changing the direction of the exhaust as it leaves a jet engine, "
                         "so that the flow is turned partially forwards and slows the aircraft after landing."]}]
FACTS = [{"id": "", "what": "whole object", "size": [1540.0, 1045.0, 1802.0], "components": 14},
         {"id": "fan", "label": "Fan", "pieces": 22, "size": [900.0, 900.0, 120.0]}]


def test_page_text_keeps_prose_and_drops_chrome():
    title, paras = lane.page_text(PAGE)
    assert title.startswith("Thrust reversal")
    assert len(paras) == 3 and all("ignore me" not in p and "menu line" not in p for p in paras)
    assert "[1]" not in paras[0]


def test_rank_prefers_the_paragraph_about_the_query():
    _, paras = lane.page_text(PAGE)
    top = lane.rank(paras, lane.stems("thrust reverser exhaust"), k=1)
    assert len(top) == 1 and "thrust reverser" in top[0]


def test_clip_stays_inside_the_budget():
    long = "One sentence here. " * 80
    assert len(lane.clip(long)) <= lane.EXCERPT_CHARS and lane.clip(long).endswith(".")


def test_only_http_pages_are_read():
    try:
        lane._get("file:///etc/passwd")
    except ValueError:
        return
    raise AssertionError("a file URL was read")


def _raw(sentences, concept=False):
    return {"concept": concept, "chapters": [{"title": "T", "component": "fan", "sentences": sentences}]}


def test_cited_sentence_must_match_its_source():
    good = {"kind": "cited", "text": "The reverser turns the exhaust flow partly forwards to slow the aircraft.", "cite": [1]}
    bad = {"kind": "cited", "text": "The cannon fires plasma bolts at nine times the speed of sound.", "cite": [1]}
    nosrc = {"kind": "cited", "text": "The reverser turns the exhaust flow partly forwards.", "cite": [7]}
    out = explain.verify(_raw([good, bad, nosrc]), SOURCES, FACTS)
    assert [s["text"] for s in out["chapters"][0]["sentences"]] == [good["text"]]
    assert out["dropped"] == 2 and out["chapters"][0]["component"] == "fan"


def test_measured_sentence_may_only_use_measured_numbers():
    ok = {"kind": "measured", "text": "The fan has 22 pieces and spans 900 mm."}
    wrong = {"kind": "measured", "text": "The fan spins at 12000 rpm."}
    out = explain.verify(_raw([ok, wrong]), SOURCES, FACTS)
    assert [s["text"] for s in out["chapters"][0]["sentences"]] == [ok["text"]]


def test_concept_sentences_need_a_concept():
    c = {"kind": "concept", "text": "The baffle would fold the exhaust back on itself."}
    assert explain.verify(_raw([c]), SOURCES, FACTS)["chapters"] == []
    out = explain.verify(_raw([c], concept=True), SOURCES, FACTS)
    assert out["chapters"][0]["sentences"][0]["kind"] == "concept"


def test_a_concept_keeps_unbacked_claims_but_never_as_cited():
    bad = {"kind": "cited", "text": "The cannon fires plasma bolts at nine times the speed of sound.", "cite": [1]}
    out = explain.verify(_raw([bad]), SOURCES, FACTS, force_concept=True)
    s = out["chapters"][0]["sentences"][0]
    assert s["kind"] == "concept" and s["cite"] == [] and out["relabelled"] == 1


def test_finish_lists_only_sources_that_were_used():
    checked = explain.verify(_raw([{"kind": "concept", "text": "It would hum."}], concept=True), SOURCES, FACTS)
    doc = explain.finish("Thing", checked, {"title": "At a glance", "component": "", "sentences": [
        {"kind": "measured", "text": "Thing measures 10 mm.", "cite": []}]}, SOURCES, "levitate", "dirk")
    assert doc["sources"] == [] and doc["notice"].startswith("Concept.") and doc["counts"]["concept"] == 1
    assert all(ch["seconds"] >= 4 for ch in doc["chapters"])


class _Shape:
    def __init__(self, V):
        self.V = np.asarray(V, float)

    def arrays(self):
        return self.V, None


def test_rest_pose_stands_a_box_and_floats_a_ball():
    g = np.linspace(-1, 1, 9)
    box = np.array([[x, y, z] for x in g for y in g for z in g])
    assert explain.rest_pose([_Shape(box)]) == "flush"
    u, v = np.meshgrid(np.linspace(0, np.pi, 40), np.linspace(0, 2 * np.pi, 40))
    ball = np.c_[(np.sin(u) * np.cos(v)).ravel(), np.cos(u).ravel(), (np.sin(u) * np.sin(v)).ravel()]
    assert explain.rest_pose([_Shape(ball)]) == "levitate"


def test_searxng_takes_an_instance_or_a_browser_style_template():
    from replicator.research import lane
    t = "http://192.168.1.50:8888/search?q=%7Bquery%7D&format=json&categories=general"
    assert lane.searxng_url(t, "rao bell") == "http://192.168.1.50:8888/search?q=rao+bell&format=json&categories=general"
    assert lane.searxng_url("http://h:8888/", "a b") == "http://h:8888/search?q=a+b&format=json"
    assert lane.searxng_url("http://h:8888/search", "a") == "http://h:8888/search?q=a&format=json"


def test_voice_commands_fill_placeholders_per_argument_without_a_shell():
    from replicator import voice
    cmd = voice._fill("tts.py {text} -o {wav} --voice {voice}", text="a; rm -rf ~ $(x)", wav="/t/o.wav", voice="af_heart")
    assert cmd == ["tts.py", "a; rm -rf ~ $(x)", "-o", "/t/o.wav", "--voice", "af_heart"]
    assert voice._runnable("python3 -c pass") and not voice._runnable("no-such-binary-xyz {wav}")
    assert voice.status({"tts_cmd": "no-such-binary-xyz {text}"})["tts"] != "local command"
