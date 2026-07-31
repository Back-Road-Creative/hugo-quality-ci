---
title: "A Post With Quotes & Ampersands"
date: 2026-01-15
updated: "2026-02-01"
description: "A post whose title contains characters that break hand-written JSON."
tags: ["structured-data", "testing"]
---

The title above is the point of this fixture: it contains an ampersand and, in
the rendered JSON-LD, must survive as data rather than as broken markup. A
template that concatenates JSON strings fails here; one that builds a map and
calls `jsonify` does not.
