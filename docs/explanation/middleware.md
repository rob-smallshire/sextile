# Middleware

Explanation: what wraps every page a service builds, the order the wrappers run
in, and the three things one can do with the chain. The type and the two shipped
middlewares are {py:mod}`sextile.middleware`; the recipes are
{doc}`../how-to/log-every-page`, {doc}`../how-to/restrict-access` and
{doc}`../how-to/the-visits-log`.

## The type

A `Middleware` is `(request, call_next) -> Page | None`, handed the request and
`call_next` — the rest of the chain below it. A handler answers what one page
says; a middleware answers what is true of every page — who is asking, how long
it took, whether they may.

## The chain

`Sextile(..., middleware=[first, second])` wraps the page builder, the first
given outermost. A request enters the outermost middleware, passes down through
each that calls `call_next`, reaches the builder at the bottom, and the page
returns back up the same way, so `first` sees the request before `second` and the
page after it.

## The three moves

- Inspect: read the request, call `call_next`, and let the page pass — the timing
  and logging in {doc}`../how-to/log-every-page`.
- Transform: call `call_next` and change what comes back before returning it.
- Answer instead: return a `Page` without calling `call_next`, so no page is
  built behind it — the refusal in {doc}`../how-to/restrict-access`.

## The two the framework ships

`log_pages` writes each page and its build time to the machine's log, for whoever
runs the service; `record_visits` writes to a log the service reads back, feeding
the readership pages of {doc}`../how-to/the-visits-log`. The framework ships these
two and no more.

Why nothing for authentication: what a service logs, or who may reach a page, is
the service's question and not the framework's — the chain gives it the place to
answer, in the answer-instead move, and no policy of its own. The middleware
decisions are in {doc}`design-decisions`.
