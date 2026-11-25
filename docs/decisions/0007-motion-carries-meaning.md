# 7. Use motion only where it carries meaning

**Status:** accepted; revised when the dark glass theme was added

## Context

The first interface was plain and static. A redesign added a typographic system and animation, and a second pass added a dark glass theme over a moving backdrop. Animation can help a reader follow what changed, or it can decorate and distract. It can also undo [decision 4](0004-hold-the-answer-until-scored.md): an answer whose marks fade in after its text is an answer that was shown unmarked.

## Decision

Each animation of the content has to do one of three jobs, and is otherwise left out.

| Job | Where it is used |
|---|---|
| Show that something changed | A mark that appears or disappears when the threshold moves is swept across the claim like a highlighter stroke. The two rate bars grow and shrink with the slider. A recorded finding stamps its button and tag. |
| Show that work is in progress | The current step turns, a finished step draws its tick, and the placeholder for the held answer shimmers. |
| Lead the eye in reading order | Claims arrive one after another, and the words a passage shares with the claim are highlighted in sequence. Before the first question, a ring of light turns around the question field, the one thing there is to act on. |

Rules that follow from the other decisions:

- A claim's mark arrives with the claim. The sweep starts as the claim appears, so there is no moment when a marked claim can be read unmarked.
- After the answer has arrived, a change of threshold re-marks at once. The staggered delay used on arrival is removed after about a second.
- With "reduce motion" set in the operating system, every state is shown at once in its final form and nothing loops.

## The backdrop is the exception

The dark theme has a backdrop of slowly flowing light, drawn by one WebGL shader. It does none of the three jobs. It is decoration, kept because the interface is also a demonstration, and it is limited so that it cannot carry or hide information:

- **Colour.** The backdrop and the glass use cool colours only: blue, violet, magenta and cyan. Amber is used for marks and nothing else, so a claim to check is the only warm thing on the screen.
- **Text.** No reading text sits straight on the backdrop. Answers, passages and controls are on panes of dark, blurred glass, and the backdrop is dimmed behind the opening heading.
- **Pace.** The flow takes minutes to change shape, and nothing in it flashes.
- **Cost.** It draws a capped number of pixels at most 30 times a second and stops while the tab is hidden. Without WebGL it is replaced by three still shapes.
- **Ways out.** It holds still with "reduce motion", the glass turns opaque with "reduce transparency", and a switch in the footer gives a light theme with no glass and no backdrop.

## Why

- A change on screen that comes with no motion cue is easily missed, which is the condition under which change blindness occurs. When the student moves the control, the marks that change are the whole point, so they move.
- Feedback within about 0.1 s reads as immediate. The sweep begins at once and lasts under half a second.
- The marks do not depend on colour, on motion or on the theme: a mark is a label, a border and an underline everywhere.

## Consequences

- The storyboard screenshots are captured with motion reduced, because a frame is measured before it is captured and nothing may be moving in between. The backdrop is then the same still frame every time. The browser tests also run with motion on.
- Animation of the content is written in CSS, and the backdrop is one fragment shader, so no animation or graphics library is loaded. A few effects use recent CSS (`@starting-style`, registered custom properties); a browser without them shows the final state with no transition.
- Frame pacing with the backdrop running was measured on one laptop (frames 16.7 ms apart at 1440 × 900 and at 1920 × 1080). It has not been measured on slower hardware.
- Two fonts are bundled (Inter and Newsreader, SIL Open Font Licence), so the interface looks the same on every system and loads nothing from a third party.
