"""The framework's own command line.

It can serve or draw any application, named the way a WSGI or ASGI server names
one:

    sextile serve your_service:app
    sextile render your_service:app --page 82489493

The two commands are the framework's shared `render` and `serve`, over a
`module:name` argument.
"""

import click

from sextile import __version__
from sextile.application import Sextile
from sextile.cli import CONTEXT_SETTINGS, load_application, standard_commands


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.version_option(__version__, "--version", prog_name="sextile", message="%(prog)s %(version)s")
@click.pass_context
def main(context: click.Context) -> None:
    """A framework for Viewdata services."""
    #  No subcommand prints the help and exits 0, the way the argparse command
    #  did, rather than Click's default "missing command" error.
    if context.invoked_subcommand is None:
        click.echo(context.get_help())


def _from_spec(context: click.Context) -> Sextile:
    """Load the application the `module:name` argument names."""
    return load_application(context.params["application"])


for _command in standard_commands(
    _from_spec,
    options=[click.argument("application")],
    page_example="1 or 82489493",
):
    main.add_command(_command)


if __name__ == "__main__":
    main()
