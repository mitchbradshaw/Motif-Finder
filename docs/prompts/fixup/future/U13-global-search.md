# Stub — U13: the header's global search does nothing

**From Round 4.** Needs a design before it needs a prompt.

The header carries "Search spans, runs, families" with a `Ctrl K` hint on **every page**, and it is
not wired. An affordance that is always visible and never works is a standing small lie about what
the app can do — the same class as the "N need you" constant and the `rank undefined` subtitle that
prompt `A` removed, except that this one is on every screen.

## What has to be decided first

What it searches, and what a result *is*. A span, a run, a family and a dataset are four different
things with four different destinations, and a single ranked list over all of them is a design
decision, not an implementation detail.

Worth noting: **prompt `F` has since given datasets real names** — display name, species, organism id,
experiment date, condition — so "search" now has human-readable text to match on, which it did not
have when U13 was raised. That changes the shape of the answer: searching for "Lion's mane" or
"20 Jul" is now meaningful where searching for `M2_aug_concat_fs1.mat` never was.
