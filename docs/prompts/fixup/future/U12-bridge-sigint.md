# Stub — U12: the bridge reports a Ctrl-C on first start, with no input

**From Round 4.** Undiagnosed. **Needs reproduction, not a guess.**

`webui/run_server.py` installs no SIGINT/SIGBREAK handler and calls `uvicorn.run()` directly. Prompt
`D` separately recorded Windows asyncio `WinError 10022` teardown lines on a first smoke run that did
not recur.

Nothing has reproduced it deliberately. It has not blocked anyone, which is why it has stayed open
through six prompts.

Whoever takes it should **reproduce it first** and only then decide whether a signal handler is the
fix. A handler added on a hunch would hide the symptom without explaining it — and this stage's whole
method has been to measure the cause before changing anything (`G` reproduced U2 in the browser
before touching a line; `J` ran the authors' MATLAB before porting).
