# Z — seeing propagation in space: arrows, morphing playback, speed and direction

**From:** the cross-channel workshop, 2026-10-27, Q12 (`docs/prompts/changes/cross-channel-explorer-decisions.md`,
D11). **Not in the build.** The build makes the pack map (draggable electrode dots, in mm) and the lag-against-distance
plot (slices S3 and S8 of `cross-channel-explorer.md`). This stub holds what comes after, once there are results.

## The researcher's words

> I am imaging a 2D axis for each pack, where the channels on that pack can be dragged as points with (x,y) coords,
> relative to a channel at the origin. Not really sure how to yet visualise propagation events moving across this 2d
> space, but this could lead to some really cool plotting which I want to spend some time developing. … Really want to
> explore [the playback] too, have a playback not only with highlighting the dots but showing the evolution of the
> event as it propagates between channels, morphing over time. Will have to see what results we get first.

## The ideas, in order of value

1. **Arrows on the pack map.**
   - Draw an arrow for every within-pack pair whose timetable test passes (after BH), from the leading to the lagging
     electrode.
   - Thickness is the number of on-timetable co-occurrences; the label is the median lag.
   - Grey dashed arrows for pairs that co-occur beyond chance but keep no timetable.
2. **Arrival playback with morphing.**
   - Pick one candidate event (S7's list) and scrub a time cursor.
   - Each electrode's dot lights as the event reaches it. Beside each dot, a small trace window shows **that channel's
     waveform at that moment**, so you watch the shape change as it travels.
   - Optionally interpolate a field between electrodes, e.g. inverse-distance weighting of the instantaneous value. It
     must say plainly that the field between electrodes is interpolation, not measurement.
   - Export a GIF or MP4 for talks. That export needs a writer the environment already has: matplotlib's animation
     writers need ffmpeg or Pillow. Check before promising it.
3. **A plane-wave fit.**
   - With three or more electrodes in a pack, fit arrival time = t0 + (s · position) by least squares. The slowness
     vector s gives speed (1/|s|) and direction.
   - Report the residual. A bad fit means not a plane wave (a point source, or no propagation).
   - Bootstrap over the event's channels for an interval.
4. **A direction rose** across many events of one pack: is there a preferred direction (towards the substrate's
   edge, towards the fruiting body)?
5. **An isochron map per event:** colour each dot by its arrival lag relative to the first.

## What it rests on

- Positions per channel: `pack.*`, `x_mm.*` and `y_mm.*` in Settings › Channels & events (S0, S3), estimated from
  photos.
- The census's timetable results and the co-occurrence rows (S1), and the candidate list (S7).
- Lags from the restricted-lag peak (±50 s). An arrival order needs lags measured on the same absolute samples (Q40a).

## Cautions to carry

- Electrodes are few per pack (four on M2, at most), so a plane-wave fit has one or two degrees of freedom left. Say
  so on every fit.
- What A1 and A2 mean is unknown (two channels per label). Two channels of one site have distance ≈ 0, and their lag
  says nothing about speed.
- A morphing playback is a picture of one event, not evidence. Label it as one event, chosen how.
