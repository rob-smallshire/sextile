# phpBB's Atom feed strips newlines from code listings

A defect in phpBB's feed generation, found while building Sextile. Written up so
it can be passed to the Stardot administrators, and upstream if they wish.

## Summary

phpBB's syndication feed removes every control character from a post body,
including newlines. For ordinary prose this is invisible, because phpBB has
already converted line breaks to `<br>`. Inside `[code]` blocks it is
destructive: the listing arrives as a single run-on line, and the original line
structure is unrecoverable.

The same post read from the web page is unaffected. Only the feed loses the
line breaks.

## Evidence

Topic 28000, post 409119, contains a short assembler listing.

**From the web page**, `viewtopic.php?t=28000`:

```
MAGIC0=&amp;19\nMAGIC1=&amp;67\n
```

**From the feed**, `app.php/feed/topic/28000`, the same `<pre><code>` block:

```
MAGIC0=&amp;19MAGIC1=&amp;67
```

A longer listing in the same topic loses eight line breaks the same way, running
its comment lines together:

```
;; Step 2: Test if that pre-existing rom image is SWMMFS;; so we re-use the
same slot again and again        lda     &amp;b5fe        cmp     #MAGIC0
```

To reproduce:

```sh
curl -s 'https://stardot.org.uk/forums/viewtopic.php?t=28000' \
  | grep -o '<pre><code>.*</code></pre>' | head -1 | od -c | grep -c '\\n'

curl -s 'https://stardot.org.uk/forums/app.php/feed/topic/28000' \
  | grep -o '<pre><code>.*</code></pre>' | head -1 | od -c | grep -c '\\n'
```

## The signature

Three observations that together identify the cause:

1. Newlines are **removed**, not replaced by a space: `SWMMFS;;` with no gap.
2. Indentation made of **spaces survives** — `        lda` keeps its eight
   spaces.
3. Across ten captured feed bodies there is **not one control character** of any
   kind inside the content.

So it is not a whitespace-collapsing step, which would leave a space behind, and
not a `<pre>`-specific problem. Everything below 0x20 is being deleted.

## Cause

`phpBB/phpbb/feed/helper.php`, in `generate_content()`:

```php
// Other control characters
$content = preg_replace('#(?:[\x00-\x1F\x7F]+|(?:\xC2[\x80-\x9F])+)#', '', $content);
```

The character class `\x00-\x1F` includes tab (`\x09`), line feed (`\x0A`) and
carriage return (`\x0D`). All three are stripped.

This was read from phpBB's `master` branch; the line number will differ between
releases, but the behaviour matches what Stardot's feed produces exactly.

## Why it has gone unnoticed

Feed readers show prose, and prose is unaffected: phpBB emits `<br>` for line
breaks in running text, so removing the literal newlines changes nothing
visible. The damage is confined to `<pre>` content, where the newline *is* the
formatting — and to anyone consuming the feed programmatically.

On a board largely concerned with 6502 assembler, that is not a small corner.

## Suggested fix

Tab, line feed and carriage return are **valid characters in XML 1.0**; the
sanitiser is stricter than the format requires. Narrowing the class to the
characters XML actually forbids preserves listings while still removing anything
genuinely illegal:

```php
$content = preg_replace('#(?:[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+|(?:\xC2[\x80-\x9F])+)#', '', $content);
```

That is the minimal change: `\x09`, `\x0A` and `\x0D` are simply excluded from
the class.

## What was verified, and what was not

Verified directly:

- The web page retains the newlines and the feed does not, for the same post.
- No control character of any kind survives into a feed body.
- Space indentation is preserved, so the loss is specific to control characters.

Inferred rather than proven:

- That the `helper.php` line quoted above is the exact code path Stardot's
  installation runs. The version in use was not determined, and the fix should
  be checked against it.
- The prediction that tabs are stripped too follows from the same regex, but no
  captured listing contained a tab, so it remains untested.

## Consequence for Sextile

Sextile renders listings as it receives them rather than guessing where the
breaks belonged. Splitting on heuristics — before `;;`, or on runs of spaces —
would fabricate structure that could be wrong, and being confidently wrong about
someone's assembler is worse than being awkward.

If this is fixed upstream, or if a read-only phpBB extension becomes available,
listings become legible with no change to Sextile beyond deleting the test that
pins the current behaviour.
