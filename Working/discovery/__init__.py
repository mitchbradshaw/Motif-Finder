"""
Working.discovery
=================
The UI-free half of the Discovery workspace (spec §7): applying a saved
detection template, or a seeded search, at a scope where the intermediates
are unviewable, and scoring what came back against what a human has judged.

Four modules, each answering one question:

``matching``
    When are two spans the same event? Spec §4.6's rule — reciprocal overlap
    **and** onset agreement scaled to the candidate's own duration — with its
    own name, so a precision figure can state how it was computed.
``scoreboard``
    §7.3's table: found / already judged / reviewed / interesting / precision
    / recall / null expects / × null, per channel and pooled, from
    ``detections`` × ``annotations`` × ``reviewed_spans``.
``fanout``
    §7.1's "each template becomes one run across all channels in scope":
    a plan, its estimate, its run group and its per-channel status. Built on
    ``Working.run_groups`` rather than beside it.
``seeded_search``
    §7.6: a seed taken by content, its native window, the matches, the null
    behind the histogram, and the cut — re-thresholded without recompute.

Nothing here imports a UI library, a browser type or FastAPI (rule 1); the
bridge in ``webui/server/discovery.py`` is the only caller that knows a
browser exists.
"""
