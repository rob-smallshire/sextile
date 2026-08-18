# Applications

Worked examples: three services built on the framework, each written up as what
it is and what it asked of the framework. The calendar is the framework's own
example and needed no change; the forum is a real in-tree service; and the
weather, the first deployed service, now lives in its own repository. Together
they keep the framework honest — nothing in `packages/sextile/` knows a forum, a
calendar or the weather.

```{toctree}
:maxdepth: 1

calendar
stardot
weather
```
