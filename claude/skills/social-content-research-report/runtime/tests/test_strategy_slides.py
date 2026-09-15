"""The copy-paste brief is the deck's only real output — pin its shape.

Every assertion here defends something a reader or the clone router depends on:
the three routing cues, the absence of the old rewrite direction, and the fact
that a brief pastes as exactly the text the author wrote.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy_slides import (  # noqa: E402
    MSG_WRAP_COLS,
    message_lines,
    overlong_message_lines,
    report_product,
    strategy_message,
    strategy_markdown,
)

STRATEGY = {
    "url": "https://www.instagram.com/reel/DLkfsn3O5aS/",
    "avatar": "UGC — confident wellness creator outdoors, casual follow-along delivery",
}


def test_brief_is_the_three_line_recreate_block() -> None:
    assert strategy_message(STRATEGY, "Plumb") == (
        "analyze https://www.instagram.com/reel/DLkfsn3O5aS/\n"
        "Recreate the video for Plumb\n"
        "Change the Avatar: UGC — confident wellness creator outdoors, "
        "casual follow-along delivery"
    )


def test_brief_carries_the_three_clone_routing_cues() -> None:
    """`analyze <url>` + a recreate line + a modification note.

    That combination is what the high-fidelity-video-clone skill triggers on;
    losing any one of them risks routing a paste to template generation.
    """
    lines = strategy_message(STRATEGY, "Plumb").split("\n")
    assert lines[0].startswith("analyze http")
    assert lines[1].startswith("Recreate the video for ")
    assert lines[2].startswith("Change the Avatar: ")


def test_brief_never_carries_rewrite_direction() -> None:
    """The old Keep/Change/Overlay lines briefed too big a departure."""
    message = strategy_message(
        {**STRATEGY, "keep": "the hook", "change": "re-premise it", "overlays": ["a", "b"]},
        "Plumb",
    )
    for banned in ("Keep:", "Change:", "Overlay:", "Style:", "Avatar:\n"):
        assert banned not in message
    assert "\n\n" not in message  # no blank separators — three tight lines


def test_per_strategy_product_overrides_the_report_wide_one() -> None:
    message = strategy_message({**STRATEGY, "product": "https://plumb.app"}, "Plumb")
    assert "Recreate the video for https://plumb.app" in message


def test_missing_avatar_drops_the_line_rather_than_dangling() -> None:
    message = strategy_message({"url": "https://x/1"}, "Acme")
    assert message == "analyze https://x/1\nRecreate the video for Acme"


def test_missing_product_still_asks_for_a_recreation() -> None:
    assert "Recreate the video for this product" in strategy_message(STRATEGY)


def test_report_product_reads_the_cover_client_name() -> None:
    assert report_product({"cover": {"clientName": " Mom Clock "}}) == "Mom Clock"
    assert report_product({}) == ""


def test_short_brief_never_wraps_in_the_paste() -> None:
    """A wrapped line lands in the paste with a break the author never wrote."""
    assert overlong_message_lines(STRATEGY, "Plumb") == []
    assert message_lines(STRATEGY, "Plumb") == strategy_message(STRATEGY, "Plumb").split("\n")


def test_a_very_long_avatar_is_reported_as_overlong() -> None:
    long_avatar = {**STRATEGY, "avatar": "x" * (MSG_WRAP_COLS + 20)}
    assert overlong_message_lines(long_avatar, "Plumb")


def test_markdown_section_uses_the_cover_product() -> None:
    lines = strategy_markdown(
        {
            "cover": {"clientName": "Mom Clock"},
            "strategies": {"items": [{**STRATEGY, "title": "S1"}]},
        }
    )
    assert any("Recreate the video for Mom Clock" in line for line in lines)
