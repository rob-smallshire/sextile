# Command line

Reference: the `sextile` command, which serves or draws any application named
the way an ASGI server names one — `module:name`, a `Sextile` or a factory that
returns one.

```sh
sextile serve your_service:app
sextile render your_service:app --page 82489493
```

## `sextile serve`

Answers calls from terminals on a TCP port.

| Option | Default | Does |
|---|---|---|
| `--host` | `127.0.0.1` | the address to listen on |
| `--port` | `16650` | the port to listen on |
| `--idle-timeout SECONDS` | `900` | release a caller who says nothing this long; `0` holds the line indefinitely |
| `--warn-after SECONDS` | half the idle timeout | warn a silent caller with a draining bar; `0` for no warning |
| `--max-connections N` | `64` | how many callers may be on the line at once; `0` for no ceiling |

## `sextile render`

Draws one frame to standard output and, to standard error, where each key would
lead — the quickest check that a menu is wired up. Exits `0` when it drew, `2`
where the page, frame or number is not there.

| Option | Default | Does |
|---|---|---|
| `--page NUMBER` | | the page to draw, `1` or `82489493` |
| `--frame N` | `0` | which frame of a page that runs to several |
| `--form FORM` | `ansi` | how to draw it |
| `--no-colour` | | suppress the ANSI colour |

| `--form` | draws |
|---|---|
| `ansi` | colour, as the Beeb would draw it |
| `grid` | the character and attribute layers |
| `bytes` | the wire stream, as a hex dump |
| `html` | a self-contained web page, drawn with Bedstead |

## Building your own

A service with its own command line builds a `click.Group` and adds the pieces
`sextile` itself uses. `standard_commands(load)` returns the `render` and `serve`
commands to add to it, given a `load` that builds the application; its `options=`
are added to both, for a flag such as a database path, and `page_example=` sets
what `render --page`'s help shows. `form_options` and `listening_options` add the
option tables above to a command of your own, `load_application` resolves a
`module:name`, and `render_page` and `run_service` carry out the two commands.
See {py:mod}`sextile.cli`.

```python
import click
from sextile.cli import CONTEXT_SETTINGS, standard_commands

@click.group(context_settings=CONTEXT_SETTINGS)
def cli() -> None: ...

for command in standard_commands(lambda context: build_application(...)):
    cli.add_command(command)
```

Why a `module:name`: the framework serves an application it is told about at the
command line rather than one it imports, so a service is a library the `sextile`
command drives, not a program that reaches back into the framework.
