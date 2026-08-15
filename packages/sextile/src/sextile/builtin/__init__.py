"""The pages the framework builds for a service out of what it already knows.

Five modules, and none of them is registered anywhere. A service maps what it
wants into its own numbering and does without the rest. The services here all
map them into the `9` namespace, where the second digit names a function, and
they agree on the numbers as far as they go:

    91  guidance    how to get about, from the keys we answer
    92  history     where this caller has been, as a menu of shortcuts
    93  contents    every page advertised, from the registrations
    94  names       the words a reader can key, from the aliases
    96  readership  what has been read lately
    97              what has been read most
    98              how many have called

What they have in common is where their content comes from. Every one is built
from something the framework holds already -- the registrations, the router's
aliases, the session's history, the visit log -- so none of them needs a service
to supply anything, and none of them can know what the service is about. That is
the first invariant holding: a contents page lists what a service registered,
with no knowledge of what those pages are about.

Where a page needs the service's own words rather than its own data, it takes a
`describe` callable and asks. The labels then read in the service's vocabulary
without the framework ever holding it.

The handlers a `PageRoute` points at are `sextile.handlers`, not here. These
modules build pages; those name them.
"""
