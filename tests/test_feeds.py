"""Feed parser tests — pure functions, no network, no DB."""
from src.espn_feed import _parse_height_cm, _parse_weight_kg
from src.tsdb_feed import parse_height_m, parse_weight_kg, best_player_match, flag_for
from src.mirror_footballdata import _parse_date
from src.odds_feed import _devig, _pick_pre, _date_iso


def test_devig_fair_probabilities():
    # 2.0 / 3.5 / 4.0 -> implied 0.5/0.2857/0.25, sum 1.0357 -> normalized
    h, d, a = _devig("2.0", "3.5", "4.0")
    assert abs(h + d + a - 1.0) < 1e-9
    assert abs(h - 0.5 / 1.035714) < 1e-4
    assert h > d > a


def test_devig_rejects_garbage():
    assert _devig(None, "3.5", "4.0") is None
    assert _devig("", "", "") is None
    assert _devig("x", "y", "z") is None
    assert _devig("0", "3.5", "4.0") is None  # zero odds impossible


def test_pick_pre_fallback_chain():
    row = {"B365H": "", "B365D": "", "B365A": "", "AvgH": "2.0", "AvgD": "3.2", "AvgA": "3.8"}
    v = _pick_pre(row)
    assert v is not None and abs(v[0] + v[1] + v[2] - 1.0) < 1e-9
    assert _pick_pre({}) is None


def test_fixtures_date_iso():
    assert _date_iso("13/09/2026") == "2026-09-13"
    assert _date_iso("garbage") is None
    assert _date_iso("") is None


def test_tsdb_height_metric():
    assert parse_height_m("1.86 m (6 ft 1 in)") == 186
    assert parse_height_m("1.7 m") == 170
    assert parse_height_m("1.92m") == 192


def test_tsdb_height_garbage():
    assert parse_height_m("") is None
    assert parse_height_m(None) is None
    assert parse_height_m("tall") is None


def test_tsdb_weight_kg_and_lbs():
    assert parse_weight_kg("78 kg (172 lb)") == 78
    assert parse_weight_kg("174 lbs") == 79   # 174 * 0.4536 = 78.9
    assert parse_weight_kg("80kg") == 80
    assert parse_weight_kg("") is None


def test_espn_height_feet_inches():
    assert _parse_height_cm('6\' 2"') == 188
    assert _parse_height_cm('5\' 11"') == 180  # 5*12+11 = 71 in = 180.34 cm -> 180
    assert _parse_height_cm("1.88 m") == 188
    assert _parse_height_cm(None) is None


def test_espn_weight():
    assert _parse_weight_kg("174 lbs") == 79
    assert _parse_weight_kg("79 kg") == 79
    assert _parse_weight_kg(None) is None


def test_player_match_exact():
    squad = [{"strPlayer": "Kylian Mbappé"}, {"strPlayer": "Jude Bellingham"}]
    assert best_player_match("Kylian Mbappé", "Mbappé", squad)["strPlayer"] == "Kylian Mbappé"


def test_player_match_disambiguates_namesakes():
    squad = [{"strPlayer": "Iñaki Williams"}, {"strPlayer": "Nico Williams"}]
    assert best_player_match("Nico Williams", "Williams Jr", squad)["strPlayer"] == "Nico Williams"
    assert best_player_match("Iñaki Williams", "Williams", squad)["strPlayer"] == "Iñaki Williams"


def test_player_match_nickname_token():
    squad = [{"strPlayer": "Iñaki Williams"}]
    # nickname "Williams" is one token of the tsdb name -> match
    assert best_player_match("I. Williams", "Williams", squad) is not None


def test_player_match_rejects_wrong_player():
    squad = [{"strPlayer": "Jude Bellingham"}]
    # a single shared token must not attach Bellingham's photo to someone else
    assert best_player_match("Jobe Bellingham", "Bellingham", squad) is None
    assert best_player_match("Marc Bartra", "Bartra", squad) is None


def test_player_match_empty_squad():
    assert best_player_match("Anyone", "Any", []) is None


def test_flag_codes():
    assert flag_for("Spain") == "es"
    assert flag_for("USA") == "us"
    assert flag_for("England") == "gb-eng"
    assert flag_for("Nowhere") is None
    assert flag_for(None) is None


def test_mirror_date_parsing():
    assert _parse_date("13/08/2026") == "2026-08-13"
    assert _parse_date("01/02/2025") == "2025-02-01"
    assert _parse_date("") is None
    assert _parse_date("garbage") is None
