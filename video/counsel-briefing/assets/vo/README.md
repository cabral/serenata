# Voice-over

Put one recording per scene here, named after the scene id in `SCRIPT.md`:

```
s00-cold-open.wav
s01-project.wav
s06-gate11-part-a.wav
```

`.wav`, `.mp3` and `.m4a` work. The build reads each file's length with
`ffprobe`, times that scene to it, spreads the beats by word count and adds the
audio track. A scene with no file keeps its estimated timing.

Recordings are ignored by git. They stay on the maintainer's machine until the
maintainer decides otherwise.
