# phpBB API Integration

**User:** Anonymous  
**Created:** 8/2/2026 8:36:31  
**Updated:** 8/2/2026 22:29:41  
**Exported:** 8/2/2026 22:40:14  
**Link:** [https://chatgpt.com/c/6a6ee4c1-0200-83eb-8aab-2452ad559429](https://chatgpt.com/c/6a6ee4c1-0200-83eb-8aab-2452ad559429)  

## Prompt:
02/08/2026, 08:36:30

Does phpBB provide APIs? I’m thinking about making a Prestel-style Viewdata wrapper to allow an existing bulletin board (stardot.org.uk) to be viewed from original 1980s Acorn hardware.

## Response:
02/08/2026, 08:36:32

Yes, although perhaps not in the way you're hoping.

phpBB does **not** have a comprehensive, stable REST API in the way that modern forum platforms like Discourse or Flarum do. It was designed long before that became common. However, there are several ways to integrate with it, in roughly increasing order of desirability.

### 1. Use phpBB as a PHP library (recommended if you can run code on the server)

If you have the ability to install an extension on the phpBB instance (or otherwise run PHP on the server), this is by far the cleanest approach.

You can bootstrap the phpBB environment:

```php
define('IN_PHPBB', true);
$phpbb_root_path = './';
$phpEx = 'php';

require($phpbb_root_path . 'common.' . $phpEx);

$user->session_begin();
$auth->acl($user->data);
$user->setup();
```

After that you have access to the database abstraction layer, permissions, user/session handling, search, forums, posts, etc.

This is effectively the "official API", although it's an internal PHP API rather than a network service.

---

### 2. Write a phpBB Extension

Modern phpBB (3.1+) has an extension system with:

- Event listeners
- Services (Symfony DI)
- Routing
- Controllers

An extension could expose exactly the endpoints your Viewdata gateway needs:

```
/viewdata/forums
/viewdata/forum/42
/viewdata/topic/1234
/viewdata/post/98765
```

returning JSON or even directly generating Viewdata pages.

This would avoid scraping entirely.

---

### 3. Direct database access

phpBB's schema is well documented and reasonably stable.

The core tables include:

```
phpbb_forums
phpbb_topics
phpbb_posts
phpbb_users
```

For a read-only gateway this is perfectly practical.

The downside is needing to replicate permission logic yourself.

---

### 4. RSS/Atom feeds

phpBB can expose feeds for:

- recent topics
- forums
- posts

Useful for "latest activity", but insufficient for interactive browsing.

---

### 5. HTML scraping

This is always an option, but probably the least attractive:

- HTML changes
- themes differ
- pagination is awkward
- permissions become messy

I'd only do this if you have no server access.

---

## For Stardot specifically

If you're talking about **stardot.org.uk**, the interesting question is not whether phpBB can do it—it certainly can—but whether you have permission to install an extension.

If you don't have server access, you could still build a gateway that:

1. Logs in as a normal user (optional).
2. Fetches forum pages.
3. Parses them.
4. Converts them into Viewdata pages.

That would work surprisingly well because Viewdata is almost entirely text-based.

---

## I think there's an even nicer architecture

Given your interest in retro networking and Beebium, I'd be inclined to separate concerns:

```
BBC Micro
     │
 Viewdata protocol
     │
 Viewdata gateway
     │
  JSON API
     │
 phpBB extension
     │
   phpBB
```

The extension would expose only the information the gateway needs:

- list forums
- topics in forum
- posts in topic
- login
- unread count
- post reply
- private messages (perhaps later)

The gateway would then concern itself purely with rendering those objects into authentic Prestel pages (40×24, Level 1 graphics, reveal/conceal, page numbers, etc.).

That has a pleasant property: the gateway could later support **other forum software** simply by implementing another backend.

Given your work on Beebium and your interest in recreating authentic online experiences, I could also imagine making the gateway look like a genuine 1980s Viewdata host: page numbers, `#` for next page, `*` commands, keyword jumps, and perhaps even a simulated connect banner and page retrieval delay to complete the illusion.

## Prompt:
02/08/2026, 10:02:19

Someone has suggested starting with an RSS feed browser. The forum already has an RSS feed.

## Response:
02/08/2026, 10:02:23

That sounds like the **right first version**.

An RSS-based browser avoids almost all of the difficult phpBB integration work while still proving the interesting parts:

- fetching and parsing modern internet content;
- converting HTML-ish post bodies into Viewdata;
- paginating it into 40×24 screens;
- designing navigation suitable for a BBC Micro;
- handling character-set and formatting limitations;
- serving it over whatever transport the original hardware can use.

It also keeps the initial system safely read-only.

## A sensible split

```text
phpBB RSS feed
      │
      ▼
RSS/Atom parser
      │
      ▼
normalised articles
      │
      ▼
Viewdata renderer and paginator
      │
      ▼
Viewdata host
      │
      ▼
Commstar / terminal on BBC Micro
```

The normalised internal representation might be little more than:

```text
Feed
  title
  updated
  entries[]

Entry
  id
  title
  author
  timestamp
  link
  summary/body
```

That prevents the RSS parser, Viewdata presentation, and communications server becoming tangled together.

## What the RSS feed probably gives you

Depending on how Stardot’s feed is configured, it may expose either:

- the latest posts across the whole forum;
- the latest topics;
- one feed per forum;
- one feed per topic;
- summaries rather than complete post bodies.

Even a single “latest posts” feed is enough for a convincing prototype:

```text
100       STARDOT

1 Latest messages
2 About this service
3 Help

Updated 10:03
```

Then:

```text
110    LATEST MESSAGES

1 NS32016 timing investigation
2 Identifying an Acorn expansion
3 Beebium development
4 Econet file-server question
5 More...
```

Selecting an item could lead to one or more pages:

```text
111a  NS32016 TIMING

Robert Smallshire
2 Aug 2026 09:42

I've been investigating the
cycle timing of the Acorn
NS32016 second processor...
```

## Pagination is probably the central design problem

A Prestel screen nominally has 24 rows of 40 characters, but you will lose several rows to:

- page header;
- title;
- navigation instructions;
- continuation indicators;
- status or page number.

You may therefore have only about **18–20 lines of actual content**.

I would paginate after converting the source into a stream of semantic blocks:

- heading;
- paragraph;
- quotation;
- code/preformatted text;
- list item;
- link.

Avoid treating the post as one long string and slicing every 40 characters. You will want paragraph-aware wrapping, clean page boundaries, and explicit continuation pages.

For example:

```text
Page 123a
Page 123b
Page 123c
```

That maps very naturally onto Viewdata’s familiar numeric page plus alphabetic subpage model.

## HTML conversion

RSS descriptions frequently contain HTML, even though the outer document is XML. A useful first converter would support only:

- paragraphs and line breaks;
- bold and perhaps italic as colour changes;
- block quotations;
- unordered lists;
- `<pre>` and `<code>`;
- links represented as numbered references.

Images can initially become something like:

```text
[IMAGE: Acorn second processor]
```

Links could appear at the bottom:

```text
1 Original forum post
2 Linked datasheet
```

A BBC user might not be able to open those links directly, but retaining them in the model leaves room for later features.

## Character conversion

You will need an explicit mapping from Unicode into the terminal’s available character set. At minimum:

```text
“ ”  -> "
‘ ’  -> '
—    -> -
…    -> ...
•    -> *
£    -> native Viewdata pound glyph
```

Names and technical posts will eventually expose accented letters, mathematical symbols, arrows, box drawing, and source code characters. It is better to have a deliberate transliteration stage than let the output encoding fail unpredictably.

## Caching matters

The gateway should fetch RSS independently of connected terminals and cache the result. A BBC session should never have to wait for a live HTTPS request.

A simple approach would be:

1. Fetch periodically, respecting `ETag` and `Last-Modified`.
2. Parse and normalise newly encountered entries.
3. Render or lazily paginate them.
4. Serve the cached pages immediately.

Persisting entries also solves a limitation of RSS: feeds commonly contain only the most recent few dozen items. Your service can gradually build its own archive from the items it sees.

## A useful minimum viable version

I would limit the first version to:

- one RSS feed;
- latest-entry menu;
- read individual entries;
- next and previous subpage;
- refresh cache;
- no login;
- no posting;
- no attempt to reproduce the complete forum hierarchy.

That is enough to establish whether reading a modern forum through authentic Viewdata hardware is actually pleasant.

The later phpBB integration then becomes an incremental backend improvement rather than a prerequisite. RSS gets you the display, navigation, paging, transport, caching, and character conversion work—all of which you will need regardless of how the forum data is eventually obtained.

## Prompt:
02/08/2026, 10:05:52

Here’s the link: https://stardot.org.uk/forums/app.php/feed

## Response:
02/08/2026, 10:05:54

I’ll inspect the feed structure and see exactly what phpBB exposes there, including whether entries contain full posts, topic links, authors, and stable identifiers.

> **Searching the web**
>
>
> **Searching the web**
>
> 
>
> **Fetching Stardot forum feed content**
>
>
> **Fetched Stardot forum feed content**
>
> 
>
> **Searching for StarDot phpBB feed URLs**
>
> [Knowledge Base > FAQ: phpBB ATOM feeds](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/)
> [phpbb/phpBB/styles/all/template/feed.xml.twig at master](https://github.com/phpbb/phpbb/blob/master/phpBB/styles/all/template/feed.xml.twig)
> [Working With Web Feeds: It's More Than RSS](https://css-tricks.com/working-with-web-feeds-its-more-than-rss/)
> [Editing syndication feed settings in phpBB 3.0](https://www.inmotionhosting.com/support/edu/phpbb/syndication-feed-settings-phpbb/)
> [PhpBB](https://en.wikipedia.org/wiki/PhpBB)
> [rss2 feed in phpbb | Sabuj Kundu's Personal Website](https://sabujkundu.com/tag/rss2-feed-in-phpbb/)
> [In PHP, create an ATOM Feed from an RDF based RSS Feed](https://stackoverflow.com/questions/16538666/in-php-create-an-atom-feed-from-an-rdf-based-rss-feed)
> [GR2RSS: Publishing Linked Open Commerce Data as RSS and Atom Feeds](https://arxiv.org/abs/1509.00190)
>
> **Searched 8 websites**
>
> 
>
> Worked for 12s

That is the standard **phpBB Atom feed**, despite commonly being called an RSS feed. The distinction is minor from an implementation perspective-Python’s `feedparser`, for example, handles both-but useful when describing the project accurately. phpBB’s built-in syndication uses Atom. ([phpbb.com](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com))

I couldn’t retrieve StarDot’s feed body directly because the site blocks the browsing service, but the URL identifies the normal board-wide feed endpoint:

```text
https://stardot.org.uk/forums/app.php/feed
```

For a standard phpBB installation, you should also investigate these parameterised forms:

```text
app.php/feed?mode=forums
app.php/feed?f=FORUM_ID
app.php/feed?t=TOPIC_ID
```

Their availability depends on StarDot’s phpBB feed configuration. phpBB can separately enable board-wide post feeds, per-forum feeds, per-topic feeds, and topic-oriented feeds. ([InMotion Hosting](https://www.inmotionhosting.com/support/edu/phpbb/syndication-feed-settings-phpbb/?utm_source=chatgpt.com))

## What the main feed probably represents

The bare endpoint is normally a rolling list of the board’s newest publicly visible posts. Each Atom `<entry>` should contain fields along these lines:

```xml
<entry>
  <author>
    <name>username</name>
  </author>

  <updated>2026-08-02T07:42:00Z</updated>

  <id>...</id>

  <link href="https://stardot.org.uk/forums/viewtopic.php?p=...#p..." />

  <title>Re: Topic title</title>

  <category term="Forum name" />

  <content type="html">
    ...
  </content>
</entry>
```

The precise template used by current phpBB versions includes standard Atom feed and entry metadata, while the post body is carried as HTML content. ([GitHub](https://github.com/phpbb/phpbb/blob/master/phpBB/styles/all/template/feed.xml.twig?utm_source=chatgpt.com))

That is almost ideal for the first Viewdata implementation. You potentially get, without scraping:

- the topic title;
- poster name;
- posting time;
- source forum;
- stable post URL;
- the post body;
- an identifier suitable for deduplication.

## The first experiment I would run

On your own machine:

```bash
curl -L \
  -H 'User-Agent: StarDot-Viewdata/0.1' \
  'https://stardot.org.uk/forums/app.php/feed' \
  -o stardot.atom
```

Then inspect the broad structure:

```bash
xmllint --format stardot.atom | less
```

Or quickly enumerate entries in Python:

```python
from __future__ import annotations

import feedparser

url = "https://stardot.org.uk/forums/app.php/feed"
feed = feedparser.parse(url)

print(feed.feed.get("title"))
print(f"{len(feed.entries)} entries")

for entry in feed.entries:
    print()
    print("title: ", entry.get("title"))
    print("author:", entry.get("author"))
    print("date:  ", entry.get("updated"))
    print("link:  ", entry.get("link"))

    content = entry.get("content", [])
    if content:
        print("body:  ", content[0].get("value", "")[:200])
    else:
        print("body:  ", entry.get("summary", "")[:200])
```

Install the parser with:

```bash
python -m pip install feedparser
```

I would specifically check four things:

1. Whether `<content>` contains the **complete post** or a truncated extract.
2. Whether quotes are included as structured HTML such as `<blockquote>`.
3. Whether attachments and inline images appear as links or embedded markup.
4. How many entries the rolling feed retains.

## A useful implication

Because these are individual posts rather than merely topic summaries, your initial service need not pretend to expose the whole forum tree. It can honestly be framed as:

> **StarDot Latest - a Viewdata feed reader**

For example:

```text
100a       STARDOT LATEST

1 NS32016 timing investigation
2 Viewdata terminal software
3 BBC Master keyboard problem
4 Beebium development
5 Econet file server question
6 More...

Updated 10:02
```

An entry can then become:

```text
111a       HARDWARE

NS32016 TIMING INVESTIGATION

RobertS                 09:42

I've been investigating the cycle
timing of the Acorn NS32016 second
processor. The board runs at...
```

The post’s stable Atom ID should be your internal identity. The visible Viewdata page number can remain a temporary navigation assignment, because the ordering of a rolling feed changes whenever a new post arrives.

That distinction matters: **do not derive permanent Viewdata page numbers from current feed positions**. Cache entries by Atom ID or phpBB post ID, and maintain a separate menu-to-entry mapping.

---

**Sources:**

- [Knowledge Base > FAQ: phpBB ATOM feeds](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com)
- [Editing syndication feed settings in phpBB 3.0](https://www.inmotionhosting.com/support/edu/phpbb/syndication-feed-settings-phpbb/?utm_source=chatgpt.com)
- [phpbb/phpBB/styles/all/template/feed.xml.twig at master](https://github.com/phpbb/phpbb/blob/master/phpBB/styles/all/template/feed.xml.twig?utm_source=chatgpt.com)

## Prompt:
02/08/2026, 10:08:24

I was thinking of Viewdata page numbers having a simple structure, but do they have a maximum length (number of digits?)

## Response:
02/08/2026, 10:08:24

> **Searched 11 websites**
>
> 
>
> Worked for a couple of seconds

This is actually one of the nice things about Prestel: the page numbering scheme was much more flexible than many people realise.

A **page number could be up to nine digits long**. ([Wikipedia](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com))

For example:

- `1` - main index
- `92` - account information
- `198` - Information Provider index
- `20971` - a Met Office aviation forecast page
- `123456789` - perfectly valid, if someone wanted to allocate it. ([Wikipedia](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com))

Each page could then have **up to 26 subpages (frames)**, conventionally denoted `a`-`z`:

```
20971a
20971b
20971c
...
20971z
```

The user normally typed only the numeric page number:

```
*20971#
```

and landed on frame `a`. Subsequent `#` presses advanced through the frames. ([Wikipedia](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com))

### Information Provider page ranges

One particularly elegant aspect of the numbering was that every Information Provider rented a **master page**, typically three digits. All of their pages then lived under that prefix:

```
209      Met Office
2091
20912
209123
20912345
```

So page numbers were not just identifiers-they formed a namespace.

---

## For your gateway

You have an opportunity to do something similarly neat.

For example, reserve:

```
800          StarDot
8001         Latest posts
8002         Latest topics
8003         Search
801...       Forums
802...       Topics
803...       Individual posts
```

or perhaps:

```
810xx        BBC Micro
811xx        Electron
812xx        Hardware
813xx        For Sale
```

where the hierarchy is reflected in the numbering.

Since you effectively own the "Information Provider", you can invent any numbering convention you like, provided every page has a unique numeric identifier.

### One suggestion

I would **avoid encoding transient information (like the current RSS ordering) directly into the page number**.

Instead, make page numbers stable. For example:

- `8001` = Latest Posts menu (always)
- `8001001` = cached post #1
- `8001002` = cached post #2

Internally, maintain a mapping from those stable page numbers to Atom IDs or phpBB post IDs. That way, when a new RSS item appears, existing page numbers don't all shift, which would make bookmarks and references frustrating.

I rather like the idea that, just as the Met Office owned the `209...` namespace on Prestel, your gateway might "own" an `800...` (or similar) namespace for StarDot. It feels very much in keeping with the original Information Provider model.

---

**Sources:**

- [Prestel](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com)

## Prompt:
02/08/2026, 10:09:49

I was thinking of encoding the post date somehow. 260802 and than an ordinal for the post number within that day.

## Response:
02/08/2026, 10:09:51

> **Verifying Prestel page-number limits and historical maximum**
>
> [How to number slides with an increasing number of digits ...](https://tex.stackexchange.com/questions/132370/how-to-number-slides-with-an-increasing-number-of-digits-of-pi)
> [Micro Viewdata for 480Z Disc and Network Systems User ...](https://vt100.net/rm/docs/pn15286.pdf)
> [Acorn Prestel System User Guide](https://chrisacorns.computinghistory.org.uk/docs/Acorn/Manuals/Acorn_PrestelSystemUG.pdf)
> [Tandata Viewdate terminal user manual](https://www.samhallas.co.uk/repository/handbooks/tandata_manual.pdf)
> [Prestel Customer Handbook](https://acorn.huininga.nl/pub/unsorted/Prestel%20Customer%20Handbook%20%281987%29_text.pdf)
> [Viewdata Service Terminal Specification](https://www.blunham.com/Radar/Teletext/PDFs/Viewdata1976Spec.pdf)
> [Page numbers - in text frame - add to multiple pages](https://forums.scribus.net/index.php/topic%2C4655.0.html)
> [For Prestel](https://glasstty.com/wp-content/uploads/2021/05/Prestel-Telesoft-Protocol_small.pdf)
> [Beamer, Frame Numbers without total number of pages](https://latex.org/forum/viewtopic.php?t=6694)
> [Micronet](https://www.cpcwiki.eu/imgs/d/d4/Micronet.pdf)
> [Digital Sound Processor](https://prestel.ru/content/image/PDF/Prestel/Prestel_DAP-0808AD-DAP-1616AD-User-Manual-1.pdf)
> [How to add page numbers in InDesign: a step-by-step guide](https://www.solopress.com/blog/tutorials/how-to-add-page-numbers-in-indesign/)
> [A Sublinear Bound on the Page Number of Upward Planar Graphs](https://arxiv.org/abs/2107.05227)
>
> **Searched 13 websites**
>
> 
>
> Worked for 5s

Yes-that fits the nine-digit limit very neatly:

```text
YYMMDDNNN
```

For example:

```text
260802001
260802002
260802003
```

That gives you **up to 999 posts per day**, with the frames of each post still available as:

```text
260802001a
260802001b
260802001c
```

The final letter is the frame/subpage identifier and is not part of the numeric page number. Contemporary Viewdata documentation describes pages as having lettered frames up to `z`. ([VT100](https://vt100.net/rm/docs/pn15286.pdf?utm_source=chatgpt.com))

This has several attractive properties:

- page numbers are stable once assigned;
- chronological ordering is visible;
- no separate arbitrary post-number allocation is needed;
- the date is immediately intelligible;
- posts from the same day occupy a contiguous range.

I would probably use the **publication date in UTC**, because the Atom timestamps are likely UTC and daylight-saving transitions otherwise introduce awkward edge cases. But using Europe/London time would arguably be more natural for StarDot. The important thing is to choose and document one interpretation.

One issue is the two-digit year. It is authentic-looking and sufficient in practice, but it creates ambiguity between, say, 1986 and 2086. Since this system is explicitly rooted in a 1980s interface, that may be more charming than problematic.

You could reserve ordinal `000` as the daily index:

```text
260802000    Posts from 2 August 2026
260802001    First post
260802002    Second post
```

Then a general latest-posts page could link to the current daily index. That makes the numeric hierarchy genuinely useful rather than merely encoding an identifier.

The one significant drawback is that users would need to type nine digits to jump directly to a post. For normal browsing that hardly matters: menu selections can generate the page request automatically, while the long number acts as a stable bookmark and reference.

---

**Sources:**

- [Micro Viewdata for 480Z Disc and Network Systems User ...](https://vt100.net/rm/docs/pn15286.pdf?utm_source=chatgpt.com)

## Prompt:
02/08/2026, 10:12:48

One downside of this scheme is that the numbers walk through the whole namespace over time. No room for a prefix?

## Response:
02/08/2026, 10:13:00

> **Designing compact IDs**
>
> I’m weighing a nine-digit format that preserves a namespace, date, and daily sequence. A practical option is `8YYDDDNNN`: one prefix digit, two-digit year, three-digit day-of-year, and three-digit post number, such as `826214001`.
>
> **Designed compact IDs**
>
> 
>
> Worked for 11s

Exactly. With `YYMMDDNNN`, the date consumes six digits and the ordinal three, leaving no namespace prefix.

The simplest compromise is:

```text
PYYMMDDNN
```

where `P` is a one-digit service prefix and `NN` is the post ordinal:

```text
826080201
826080202
...
826080299
```

So:

- `8` = StarDot
- `260802` = 2 August 2026
- `01`–`99` = posts in chronological order that day
- `00` could be the daily index

That confines all StarDot content to the `8........` namespace while retaining a directly readable date. The trade-off is a limit of **99 posts per day**. That may be entirely adequate for StarDot; you could measure the feed or forum activity before committing.

A more capacious but slightly less readable scheme is:

```text
PYYDDDNNN
```

where `DDD` is the day of the year:

```text
826214001
```

That means StarDot, year 2026, day 214, post 001. It gives you:

- one-digit prefix;
- recognisable year;
- up to 999 posts per day;
- exactly nine digits.

But I think `PYYMMDDNN` is substantially nicer for humans. A post number such as `826080217` can be read immediately as “StarDot, 2 August 2026, post 17.”

You could handle the exceptional 100th post using a documented overflow scheme—perhaps putting overflow into another prefix—but it would be better first to establish whether StarDot has ever exceeded 99 public posts in one calendar day.

## Prompt:
02/08/2026, 10:15:09

I strongly suspect Stardot has exceeded 99 but not 999.

## Response:
02/08/2026, 10:15:18

Then `PYYMMDDNN` is too tight, and the best clean scheme is probably:

```text
PYYDDDNNN
```

For example:

```text
826214037
```

meaning:

- `8` — StarDot namespace
- `26` — 2026
- `214` — 214th day of the year, 2 August
- `037` — 37th post that day

That gives you the full **999 posts per day**, while confining every page to the `8........` namespace.

The loss is that the date is no longer immediately readable without converting the ordinal day. A potentially nicer alternative is to encode a sequential day number from a chosen epoch:

```text
PDDDDDNNN
```

For example, with `00000` representing 1 January 2020:

```text
824050037
```

Here:

- `8` — StarDot
- `02405` — days since the epoch
- `037` — post ordinal

Five decimal digits allow nearly 274 years of dates. This scheme has several useful properties:

- chronological page numbers;
- a permanent namespace prefix;
- 999 posts per day;
- no two-digit-year rollover;
- simple arithmetic for generating and decoding identifiers.

But it hides the calendar date completely.

I think `PYYDDDNNN` is probably the best balance. The year remains visible, the numbers sort chronologically, and converting day 214 into 2 August is something the gateway can display in the page header. The page number itself need not carry every detail in human-readable form.

## Prompt:
02/08/2026, 10:19:05

TBH, if we don’t have space to encode something recognisable as an ISO 8601 date, it’s not worth bothering. But I have to ask _what_ is imposing the 9 digit page identifier limit? The client is just dumb terminal software, so surely this limit is only in the server, which is under our control.

## Response:
02/08/2026, 10:19:07

> **Searching Prestel page number specifications**
>
> [Prestel](https://en.wikipedia.org/wiki/Prestel)
> [Acorn Prestel System User Guide](https://chrisacorns.computinghistory.org.uk/docs/Acorn/Manuals/Acorn_PrestelSystemUG.pdf)
> [Viewdata Service Terminal Specification](https://www.blunham.com/Radar/Teletext/PDFs/Viewdata1976Spec.pdf)
> [Identification Number - On-Line Services](https://services3.cic.gc.ca/ecas/redir.do?redir=id_num)
> [The Viability of Viewdata as a Mass Medium](https://tmgonline.nl/articles/10.18146/tmg.845)
> [A user's view of Prestel.](https://www.atarimagazines.com/creative/v9n5/123_A_users_view_of_Prestel.php)
> [Where can I find my client ID/UCI?](https://ircc.canada.ca/english/helpcentre/answer.asp?qnum=772&top=4)
> [For Prestel](https://glasstty.com/wp-content/uploads/2021/05/Prestel-Telesoft-Protocol_small.pdf)
> [Micro Viewdata Reference Card](https://vt100.net/rm/docs/pn15943-micro-viewdata-reference-card.pdf)
> [Micronet](https://www.cpcwiki.eu/imgs/d/d4/Micronet.pdf)
> [How Prestel Pioneered The Internet](https://www.uk2.net/blog/how-prestel-pioneered-the-internet/)
> [EUROCONTROL Specification for ATS Data Exchange ...](https://www.eurocontrol.int/sites/default/files/2023-06/eurocontrol-released-specification-adexp-3-4.pdf)
> [Prestel Customer Handbook](https://acorn.huininga.nl/pub/unsorted/Prestel%20Customer%20Handbook%20%281987%29_text.pdf)
> [Prestel Publishing, books on art, architecture, design and ...](https://prestelpublishing.penguinrandomhouse.de/)
> [vd-view help](https://viewdata.microwavepizza.co.uk/Home/Help)
> [Page Number - QinPrinting](https://qinprinting.co.uk/page-number/)
> [Digital euro pilot - Frontend specifications - End user domain](https://www.ecb.europa.eu/euro/digital_euro/timeline/profuse/shared/pdf/ecb.dep260414_Frontend_specifications_End_user_domain.en.pdf)
> [Achieving Maximum Distance Separable Private Information Retrieval Capacity With Linear Codes](https://arxiv.org/abs/1712.03898)
>
> **Searched 18 websites**
>
> 
>
> Worked for 4s

Yes - I think your reasoning is correct, and I was treating a **Prestel implementation limit** as though it were an inherent Viewdata terminal limit.

The terminal sends a page request essentially as a character sequence:

```text
*260802001#
```

It does not transmit a fixed-width binary page identifier. A dumb terminal need only send the digits the user types, followed by `#`, and display whatever character stream the host returns. The conventional nine-digit maximum belonged to Prestel’s database, addressing rules, and probably its command parser-not to the 40×24 display format or V.23 transport itself. Contemporary descriptions say that Prestel pages had unique numbers “up to nine digits long,” but that describes the service’s namespace, not a fundamental property of Viewdata. ([Wikipedia](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com))

So, with your own server, this should be perfectly plausible:

```text
8260802001
```

or, preserving a recognisable ISO-style date:

```text
8 260802 001
│ │      │
│ │      └─ post ordinal
│ └──────── YYMMDD
└────────── StarDot namespace
```

That is **ten digits**, excluding the `*` and `#`.

You could even use a four-digit year:

```text
820260802001
```

giving:

```text
PYYYYMMDDNNN
```

That is twelve digits and avoids the century ambiguity completely.

The actual constraints to check are therefore specific to the client software you intend to support:

- Does it pass every typed digit directly to the host?
- Does it maintain a local page-number input buffer?
- If so, how large is that buffer?
- Does it recognise `*digits#` generically, or assume no more than nine digits?
- How much room does its status display reserve for showing the current page number?

For **Commstar**, the BBC Micro Prestel ROM, and other period clients, one or more may impose a nine-digit buffer because they were written specifically for Prestel. That would be a client-software compatibility limitation, not a protocol limitation.

There is also a display consideration. Traditional frames show the page number near the top right. A twelve-digit number occupies a noticeable portion of a 40-column line, but it still fits:

```text
STARDOT             820260802001a
```

My preferred scheme would now be:

```text
8YYYYMMDDNNN
```

For example:

```text
820260802001
820260802002
```

That provides:

- an explicit StarDot prefix;
- a true, recognisable ISO 8601 basic-format date;
- 999 posts per day;
- chronological sorting;
- no century rollover;
- stable identifiers.

So yes: **there is no good reason for your server itself to retain the nine-digit limit**, unless compatibility testing reveals that a client you care about hard-codes it.

---

**Sources:**

- [Prestel](https://en.wikipedia.org/wiki/Prestel?utm_source=chatgpt.com)

## Prompt:
02/08/2026, 10:21:35

If we don’t zero-pad the ordinal we lose lexigraphic sorting (that’s probably ok) but we also remove the limit on the number of posts per day and get shorter page identifiers for the common case.

## Response:
02/08/2026, 10:21:40

Yes, that is probably the better trade-off.

Use:

```text
PYYYYMMDDN
```

where `N` is an unpadded positive ordinal:

```text
8202608021
8202608022
...
82026080299
820260802100
```

That gives you:

- a clear namespace prefix;
- an unmistakable ISO 8601 basic-format date;
- no artificial daily post limit;
- shorter identifiers on quieter days;
- simple parsing, because the prefix and date have fixed widths and everything remaining is the ordinal.

You lose lexicographic ordering within a day:

```text
...1
...10
...100
...11
...2
```

but numeric ordering of the complete identifier still works correctly:

```text
8202608021 < 8202608022 < 82026080210
```

So the issue only arises if identifiers are treated as strings. The server can sort structurally by `(date, ordinal)` or interpret the whole page identifier as an arbitrary-precision decimal integer.

There is one subtle ambiguity to avoid: ordinal `0`. I would reserve it for the daily index:

```text
8202608020     index for 2 August 2026
8202608021     first post
8202608022     second post
```

That gives the hierarchy a useful meaning, although it means every post identifier is at least ten digits long with a one-digit prefix.

An even cleaner presentation might omit the `0` daily-index convention and make the date itself the index:

```text
820260802      daily index
8202608021     first post
8202608022     second post
```

This works because the server parses the fixed nine-digit prefix-plus-date portion first:

```text
8 | 20260802 | 17
```

No suffix means “daily index”; a suffix means “post ordinal.” I think that is particularly elegant. It produces the shortest natural identifier for the date page while preserving an unlimited ordinal suffix.

## Prompt:
02/08/2026, 10:22:30

Yes, I like that.

## Response:
02/08/2026, 10:22:37

I do too. It has a pleasing "Viewdata" feel to it: hierarchical, memorable, and human-readable.

Your namespace becomes:

```text
8                    StarDot
820260802            2 Aug 2026 index
8202608021           Post 1
8202608022           Post 2
...
820260802100         Post 100
```

The parser is trivial:

```text
first digit      → service
next 8 digits    → YYYYMMDD
remaining digits → optional ordinal
```

If there is no ordinal, you're looking at the day's index.

A few nice consequences:

- **Hierarchical navigation.** From a post you can always derive the day's index by stripping the ordinal.
- **No arbitrary limits.** The ordinal grows as needed.
- **Bookmarkable.** Someone can say "see page `82026080217`" and it's immediately meaningful.
- **Future-proof.** You could introduce another service simply by changing the first digit:
  - `8...` StarDot
  - `9...` BeebWiki
  - `7...` Archive
  - etc.

One thought that occurred to me is that you don't necessarily have to use the **posting date**.

If your content source is a rolling RSS/Atom feed, the ordinal needs to be stable. You could assign it according to the order in which you first encounter posts on a given day. If the feed is always reverse chronological, that effectively means "newest gets 1", which is probably not what you want.

Instead, I'd assign ordinals in **chronological order of the post timestamp**:

- first post on 2026-08-02 → `8202608021`
- second → `8202608022`
- ...
- hundredth → `820260802100`

If you ever restart the gateway, you can reconstruct the same numbering from the timestamps and post IDs, so the page numbers remain stable.

The other thing I like is that it feels authentic. Prestel page numbers often had an internal structure that reflected the provider's information hierarchy. You're doing something similar, but with a hierarchy that reflects **time**, which is a very natural way to browse a forum. A user could even type `820260801` to see yesterday's posts, `820260731` for July 31st, and so on, without needing any menus at all. That kind of discoverability feels very much in the spirit of classic Viewdata.

## Prompt:
02/08/2026, 10:24:41

Do we get any information on user identity in the RSS feed? So we can see which users posted what?

## Response:
02/08/2026, 10:24:41

> **Searched 7 websites**
>
> 
>
> Worked for a couple of seconds

Yes. In fact, that's one of the strengths of using the Atom feed.

If phpBB's **Item statistics** option is enabled (and I would expect it to be on StarDot), each entry includes:

- **author username**
- **posting date/time**
- topic title
- post URL
- post content (or summary, depending on configuration)

The phpBB documentation explicitly states that enabling Item statistics adds the **author, date and time** to feed entries. ([phpbb.com](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com))

Typically you'll see something like:

```xml
<author>
    <name>BigEd</name>
</author>

<updated>2026-08-02T08:17:43Z</updated>

<title>Re: BBC Master keyboard</title>
```

The `<author><name>` value is the user's forum display name. In fact, there was a phpBB support thread where an administrator noticed all `<author><name>` values had unexpectedly become "Anonymous", confirming that under normal operation this field contains the poster's username. ([phpbb.com](https://www.phpbb.com/community/viewtopic.php?p=15970039&utm_source=chatgpt.com))

### That's enough for a very authentic presentation

You could render posts as, for example:

```text
82026080217a

BBC MASTER KEYBOARD

By BigEd
08:17  2 Aug 2026

...
```

and even provide a simple author index:

```text
81A BigEd
81B Richard Russell
81C RobColeman
```

leading to:

```text
81A

Posts by BigEd

82026073142
82026080117
8202608025
...
```

Initially, you could build that index just from whatever posts are currently in your cache.

### One thing to check

The feed almost certainly gives you the **display name**, but **not the user's numeric phpBB user ID**. If two users were ever allowed the same display name (I don't believe phpBB permits that), or if someone changes their username, you'd have to decide how to handle it.

However, because each post also has a canonical URL of the form:

```text
https://stardot.org.uk/forums/viewtopic.php?p=123456#p123456
```

you have a stable post identifier. The username is really just presentation.

I think this is becoming quite an elegant little system: an Atom feed provides just enough metadata to make a read-only Viewdata service feel like a real bulletin board, without needing any custom phpBB integration at all. If later you want login, posting, unread messages, or private messages, *then* it's worth thinking about a phpBB extension or API. But for a "StarDot Viewdata" service, the feed gets you surprisingly far.

---

**Sources:**

- [phpBB • Knowledge Base > FAQ: phpBB ATOM feeds](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com)

## Prompt:
02/08/2026, 10:26:08

So a crucial feature is to be able to browse a thread. Do we get enough information to reconstruct a thread structure?

## Response:
02/08/2026, 10:26:09

> **Searched 3 websites**
>
> 
>
> Worked for a couple of seconds

Yes, I think so-and in fact, phpBB provides something even better than enough information to *reconstruct* threads.

The feed entries contain a canonical link to the post, typically of the form:

```text
https://stardot.org.uk/forums/viewtopic.php?f=3&t=12345&p=67890#p67890
```

From that one URL you can extract:

- `f` - forum ID
- `t` - topic ID
- `p` - post ID ([phpBB](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com))

The **topic ID (`t`)** is the key. Every post in the same thread shares the same topic ID.

That means as you ingest the rolling feed you can build a local database something like:

```text
Topic 12345
    title
    forum
    posts:
        p=67880
        p=67883
        p=67890
        ...
```

So your Viewdata service can offer:

```text
Latest Posts
    ↓
Post
    ↓
View Thread
```

without ever scraping HTML.

### The catch

The feed is only a **window** onto the forum.

Suppose it contains the latest 100 posts.

If a thread has 500 posts, you'll only ever see the most recent subset until older posts are pushed out of the feed.

So the feed lets you reconstruct the topology of the *visible* part of the forum, but not its complete history.

### Fortunately...

phpBB has **per-topic feeds**:

```text
app.php/feed?f=<forum>&t=<topic>
```

If StarDot has enabled them (they're an optional phpBB feature), then you've essentially struck gold. ([phpBB](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com))

Your workflow becomes:

1. Discover a thread from the global feed.
2. Extract `f` and `t`.
3. Fetch the per-topic feed.
4. Cache the complete thread locally.

At that point you have enough information to present a proper Viewdata experience:

```text
Topic
 ├── Read from beginning
 ├── Read newest first
 ├── Jump to first unread
 └── List contributors
```

### If per-topic feeds are disabled

I'd still start with the Atom feed.

You can always fall back to fetching the HTML for a topic when the user first opens it, then cache it. That's a much smaller amount of scraping than trying to scrape the whole forum, because you're only doing it on demand.

---

So I think the first thing I'd test is simply:

```text
https://stardot.org.uk/forums/app.php/feed?f=<forum>&t=<topic>
```

using the `f` and `t` from a post you've already seen in the board-wide feed. If that works, then the Atom feed may be sufficient for almost everything you want to do, with HTML scraping reduced to a last resort-or perhaps eliminated entirely.

---

**Sources:**

- [phpBB • Knowledge Base > FAQ: phpBB ATOM feeds](https://www.phpbb.com/support/docs/en/3.0/kb/article/faq-phpbb-atom-feeds/?utm_source=chatgpt.com)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)