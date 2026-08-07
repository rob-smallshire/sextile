# phpBB extension integration

**User:** Anonymous  
**Created:** 8/7/2026 13:02:45  
**Updated:** 8/7/2026 15:56:19  
**Exported:** 8/7/2026 19:24:32  
**Link:** [https://chatgpt.com/g/g-p-6a74b9f8aba081919185ea9afb44869e/c/6a75ba8a-5780-83eb-bc1e-fd7eb029e181](https://chatgpt.com/g/g-p-6a74b9f8aba081919185ea9afb44869e/c/6a75ba8a-5780-83eb-bc1e-fd7eb029e181)  

## Prompt:
07/08/2026, 13:02:43

I’ve been in discussing this creating a Stardot viewdata feed with the administrator of the Stardot website. Rather than consuming the existing RSS/Atom feed, he proposes a closer integration using a phpBB extensions. This is attractive, because it probably avoid duplicating all the data, on the other hand I’m unsure of the other constraints. A rewrite in PHP? Can the extension provide the non-HTTP Viewdata TCP socket endpoint, etc, etc?

## Response:
07/08/2026, 13:02:47

I think the attractive split here is **much narrower than “rewrite Sextile in PHP.”** I’d treat the phpBB extension as an integration adapter, and keep the Viewdata server itself as the independent Python service unless there is a compelling deployment reason not to.

> **Searching the web**
>
> [Tutorial: Events and Listeners — phpBB 3.3.x documentation](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_events.html)
> [phpBB • SOLVED--Upgrading from 3.3.15 to 3.3.17, can't load the install page, getting a 500 error](https://www.phpbb.com/community/viewtopic.php?t=2672455)
>
> **Searched 2 websites**
>
> 
>
> Worked for 12s

Yes. I think the phpBB extension proposal is attractive, but I would draw a fairly hard architectural boundary around what “integration” means.

A phpBB extension is quite capable of giving us **first-class access to phpBB's domain and infrastructure** without modifying phpBB itself. Extensions can register services through phpBB's Symfony DI container, subscribe to core events, and add controllers/routes. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_events.html?utm_source=chatgpt.com)) That makes an extension an excellent place to solve the awkward bits we identified with RSS: permissions, canonical post/topic identity, authors, thread relationships, edits/deletions and possibly viewdata-specific metadata.

But I don't think the extension should *be* Sextile.

Conceptually I'd make it:

```text
                         phpBB
                           │
                  ┌────────┴────────┐
                  │ Stardot/Viewdata│
                  │    extension    │
                  └────────┬────────┘
                           │
                narrow integration API
                           │
                    ┌──────▼──────┐
TCP :6502 etc. ---> │    Sextile   │
Viewdata protocol   │   (Python)   │
                    └─────────────┘
```

The phpBB extension becomes essentially a **Stardot adapter for Sextile**.

That avoids both bad extremes:

```text
RSS/Atom                                    PHP rewrite
────────                                    ───────────
Too little semantic information             Too much coupling
Polling                                     Sextile duplicated in PHP
Awkward thread reconstruction                phpBB owns Viewdata serving
Possibly incomplete permissions              Harder to reuse Sextile elsewhere

                 ↑
          thin phpBB adapter
          is the sweet spot
```

### I would definitely not make an ordinary phpBB extension own the TCP listener

Technically, PHP can of course listen on TCP sockets. And phpBB extensions can add CLI commands - this is explicitly supported. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com)) So you *could* have something like:

```console
$ php bin/phpbbcli.php stardot:viewdata-server
Listening on port 6502...
```

running forever under systemd.

But that's rather different from the normal phpBB execution model. A phpBB web request starts PHP, runs through the application, generates the response, and ends. A permanent Viewdata connection has potentially quite a long lifetime and needs its own connection/session state, protocol parser, routing, timeouts, concurrent clients, etc.

You would effectively be embedding a daemon framework alongside phpBB.

Worse, that immediately starts dragging Sextile's abstractions into PHP:

```text
Viewdata connection
    ↓
terminal/session
    ↓
page request
    ↓
page-number router
    ↓
page generator
    ↓
presentation encoder
```

We've just arrived at **Sextile, rewritten in PHP**.

That feels like precisely the wrong consequence of accepting closer phpBB integration.

### Instead, let the extension expose *phpBB semantics*

For example, the extension might provide an internal API resembling:

```text
GET /app.php/viewdata/topic/1234
GET /app.php/viewdata/post/5678
GET /app.php/viewdata/forum/12/topics
GET /app.php/viewdata/user/42
```

but importantly these aren't necessarily Viewdata pages. They're structured representations of phpBB objects intended for the Sextile adapter.

Perhaps:

```json
{
    "topic_id": 1234,
    "title": "6502 Second Processor",
    "forum": {
        "id": 12,
        "name": "Acorn 8-bit Hardware"
    },
    "posts": [
        {
            "id": 5678,
            "author": {
                "id": 42,
                "username": "Somebody"
            },
            "created": "...",
            "modified": "...",
            "content": "...",
            "attachments": [...]
        }
    ]
}
```

The crucial improvement over RSS is that **we get to define this interface specifically around what Sextile needs**.

And because the extension is executing inside phpBB, it can use phpBB services rather than knowing anything about the underlying database schema. That's exactly the sort of thing phpBB's DI-based extension architecture is intended to facilitate. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_key_concepts.html?utm_source=chatgpt.com))

So Sextile doesn't need:

```python
SELECT ...
FROM phpbb_posts
JOIN phpbb_topics ...
```

which I would strongly avoid.

It asks the Stardot adapter for a `Topic`, `Post`, `Forum`, etc.

### There may be an even nicer interface than HTTP

Since Sextile and phpBB may run on the same machine, HTTP isn't compulsory.

You could have the phpBB extension install a **CLI-facing gateway** and communicate locally, although repeatedly spawning PHP would obviously be undesirable. A Unix-domain service is possible, but again we'd be creeping toward making the extension a daemon.

Consequently, localhost HTTP is actually quite appealing despite Sextile itself being non-HTTP:

```text
Viewdata client
     │
     │ raw TCP/Viewdata
     ▼
   Sextile
     │
     │ HTTP/JSON, localhost only
     ▼
phpBB extension
     │
     ▼
   phpBB
```

HTTP here is merely an **internal application protocol**. The fact that the user-facing service is raw TCP doesn't matter at all.

And phpBB already gives extensions a supported controller/routing mechanism for precisely this sort of endpoint. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.2.x/extensions/tutorial_controllers.html?utm_source=chatgpt.com))

You could firewall it to localhost, use a secret between Sextile and phpBB, or otherwise arrange authentication independently of public phpBB HTTP access.

### The extension can also solve changes elegantly

This is perhaps the most interesting part.

phpBB exposes extension events at many points in its core. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_events.html?utm_source=chatgpt.com)) The extension can therefore know things such as:

```text
post created
post edited
post deleted
topic created
topic moved
topic locked
user renamed
...
```

Rather than Sextile continually polling a feed, the extension could use those events to maintain only the **tiny amount of Viewdata-specific state** that we actually need.

For example:

```text
phpBB topic 12681 → Viewdata page 842193
phpBB post 91374  → Viewdata subpage / ordinal ...
```

That isn't objectionable duplication of phpBB content. It's an integration index.

This also resolves one problem we were beginning to encounter in the RSS design: **Viewdata identifiers have requirements that phpBB IDs don't necessarily fulfil**. The extension can own the stable mapping between the two namespaces while leaving the actual post body, username, timestamps etc. solely in phpBB.

### I'd make the boundary deliberately domain-oriented

Rather than designing a generic:

```text
GET /query?table=posts&id=123
```

I'd expose operations corresponding to what a Viewdata presentation system actually needs:

```text
forums()
forum(id)
recent_topics(forum)
topic(id)
posts(topic, before/after/page)
post(id)
user(id)
search(...)
```

and probably some explicit navigation relationships:

```text
previous_post
next_post
parent_forum
previous_topic
next_topic
```

The PHP component then understands **phpBB**, while the Python component understands **Viewdata**.

Neither has to understand much of the other's internals.

That boundary also becomes extremely valuable for the broader Sextile idea. The eventual Python package could look something like:

```python
from sextile import ViewdataServer
from stardot_viewdata import Stardot

app = ViewdataServer()

stardot = Stardot(...)

app.mount("8", stardot)
```

where `stardot-viewdata` is the site-specific Python application, and the phpBB extension is merely its server-side integration counterpart.

The MET Norway weather service we were discussing yesterday then has no phpBB dependency whatsoever:

```python
app.mount("1", Weather(...))
app.mount("8", Stardot(...))
```

which is exactly the architectural direction you were envisaging for Sextile as a general Viewdata application framework. 

### One particularly attractive possibility

I would consider making the extension API **not Stardot-Viewdata-specific at all**, at least at its lower level.

Something like a small:

**phpBB machine-readable content API**

implemented as an extension.

Then:

```text
              ┌── Stardot web UI
phpBB data ───┤
              └── phpBB content API ── stardot-viewdata ── Sextile
```

Its purpose is simply to expose a clean, authenticated, permission-aware representation of forums/topics/posts.

`stardot-viewdata` remains responsible for things peculiar to our service:

- allocation of Viewdata page numbers;
- pagination into 40×24 frames;
- thread navigation appropriate to keypad controls;
- telesoftware/download handling if we add it;
- Viewdata graphics;
- menus;
- routing.

I think that's a particularly clean separation.

So my response to the administrator would effectively be **“yes please to a phpBB extension, but as the integration surface rather than as the Viewdata server.”** It gives us much richer and more reliable access than Atom without giving up Sextile's language independence, TCP server, reusable page router and eventual role as a general-purpose Viewdata framework.

---

**Sources:**

- [Tutorial: Events and Listeners — phpBB 3.3.x documentation](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_events.html?utm_source=chatgpt.com)

## Prompt:
07/08/2026, 13:22:51

Does, phpBB not already expose an HTTP API or similar?

## Response:
07/08/2026, 13:22:52

> **Searched 5 websites**
>
> 
>
> Worked for a few seconds

Surprisingly, **not really**.

Historically, one of phpBB's weaknesses has been the lack of an official, supported REST API. As recently as 2020, the answer from phpBB developers was simply "There is not a REST API for phpBB yet." ([phpbb.com](https://www.phpbb.com/community/viewtopic.php?t=2550726&utm_source=chatgpt.com))

What phpBB *does* expose is:

- **RSS/Atom feeds** (which you've already been looking at).
- **The extension framework**, which is extensive and gives plugins access to phpBB's services, events, permissions, ORM/database layer, users, topics, posts, etc.
- **Controllers/routes**, so an extension can expose arbitrary HTTP endpoints of its own.

So if someone writes a Stardot extension, they can quite easily provide something like:

```
GET /app.php/stardot/topics/1234
GET /app.php/stardot/recent
GET /app.php/stardot/thread/5678
```

Those endpoints are not part of phpBB itself-they're simply additional routes contributed by the extension.

Interestingly, there seems to be a lot of recent movement in this area. Several developers are independently building generic REST API extensions (including "Headless", "API Hook", and an earlier "Rest API" extension), which suggests there's growing demand, but none of these are official phpBB core features yet. ([phpbb.com](https://www.phpbb.com/community/viewtopic.php?t=2672362&utm_source=chatgpt.com))

---

For your purposes, though, I actually think **a generic REST API may not even be the best interface**.

If the Stardot administrator is willing to collaborate on an extension, I'd be inclined to define an API specifically for the needs of a Viewdata client. For example:

- "Give me the first page of this topic."
- "Give me the next 20 posts after post X."
- "What topics have changed since timestamp T?"
- "Render this post as plain text with BBCode already resolved."
- "Give me the thread structure."

That's a much higher-level contract than "here are the contents of the `phpbb_posts` table", and it leaves the extension free to use phpBB's internals in whatever way is appropriate.

In fact, if I were designing it jointly with the administrator, I'd probably avoid the word "API" altogether and think of it as a **content provider** for alternative front-ends. Today one such front-end is a Viewdata service; tomorrow it could equally be a TUI, a mobile app, or a static-site generator. That makes it much easier to justify as something of independent value to the Stardot ecosystem, rather than an integration that's only useful for Sextile.

---

**Sources:**

- [phpBB • Rest API support](https://www.phpbb.com/community/viewtopic.php?t=2550726&utm_source=chatgpt.com)

## Prompt:
07/08/2026, 13:24:43

What does creating a phpBB extension entail?

## Response:
07/08/2026, 13:24:45

> **Searching the web**
>
> [phpBB Skeleton Extension — phpBB 3.3.x documentation](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html)
>
> **Searched 1 website**
>
> 
>
> Worked for 4s

It’s fairly conventional PHP plugin development; nothing about it looks especially exotic.

A phpBB extension lives under `phpBB/ext/<vendor>/<extension>/` and is described by a `composer.json`. phpBB then discovers and loads it without you modifying core phpBB files. The official skeleton generator can create most of the boilerplate for you. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com))

For the sort of integration we’re discussing, the extension would probably be quite small. Roughly:

```text
ext/
└── stardot/
    └── viewdata/
        ├── composer.json
        ├── ext.php
        ├── config/
        │   ├── services.yml
        │   └── routing.yml
        ├── controller/
        │   └── api_controller.php
        └── service/
            └── forum_service.php
```

The key pieces would be:

1. **`composer.json`** - extension identity, version, phpBB/PHP requirements, autoloading metadata.
2. **PHP service classes** - the actual code which talks to phpBB.
3. **`services.yml`** - registers those classes with phpBB's dependency-injection container.
4. **`routing.yml` + controller classes** - if we expose HTTP endpoints for Sextile.
5. Possibly **event listeners**, if we want to react to posts being created/edited/deleted rather than just answering queries.

phpBB has used Symfony's dependency-injection component since 3.1, so an extension can have phpBB services injected rather than relying on globals. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_key_concepts.html?utm_source=chatgpt.com)) For example, conceptually:

```php
final class ForumService
{
    public function __construct(
        private \phpbb\db\driver\driver_interface $db,
        private \phpbb\auth\auth $auth,
        private \phpbb\user $user,
    ) {}

    public function topic(int $topicId): array
    {
        ...
    }
}
```

and `services.yml` wires that to the appropriate phpBB services.

For an HTTP-facing extension, phpBB provides its own controller/routing mechanism, so we aren't hacking a stray `viewdata.php` into the web root. The extension can declare routes and have those dispatched to controller methods in the normal application lifecycle. The skeleton generator can generate a working example of exactly that arrangement. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com))

A minimal controller might end up looking approximately like:

```php
public function topic(int $topic_id): JsonResponse
{
    $topic = $this->forum_service->topic($topic_id);

    return new JsonResponse($topic);
}
```

with something akin to this in `routing.yml`:

```yaml
stardot_viewdata_topic:
    path: /viewdata/topic/{topic_id}
    defaults:
        _controller: stardot.viewdata.controller:topic
    requirements:
        topic_id: '\d+'
```

So from the Sextile side it is just:

```python
topic = requests.get(
    "https://stardot.org.uk/viewdata/topic/12345"
).json()
```

### Events are probably the other interesting part

phpBB has event hooks throughout its core. An extension registers an event-listener service in `services.yml` and subscribes to whichever core events it cares about. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/tutorial_events.html?utm_source=chatgpt.com))

That means we could do things such as:

```php
public static function getSubscribedEvents(): array
{
    return [
        'core.submit_post_end' => 'post_changed',
    ];
}
```

and respond when a post changes.

We might not need that at first. A read-only HTTP façade may be sufficient. But it gives us an elegant future route for cache invalidation, maintaining Viewdata page mappings, or signalling Sextile that something has changed.

### Installation is pleasingly mundane

The administrator would copy/install the extension into:

```text
phpBB/ext/stardot/viewdata/
```

and enable it under **ACP → Customise → Extensions**. phpBB extensions can also provide migrations if they need database schema or configuration changes. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com))

For development, phpBB even provides an official **Skeleton Extension** which can generate a starter extension through either a web UI or:

```console
./bin/phpbbcli.php extension:create
```

It can generate examples for controllers, services, event listeners, permissions, migrations, CLI commands, cron jobs, etc. ([area51.phpbb.com](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com))

### The likely amount of PHP is quite small

For our particular use case, I suspect the first useful version could consist of perhaps:

```text
composer.json
config/services.yml
config/routing.yml
controller/api_controller.php
service/phpbb_content.php
```

and little else.

The interesting work isn't really "learning how to make a phpBB extension". It's deciding **which phpBB abstraction to use to retrieve posts/topics and how much interpretation should happen on the PHP side**.

For example, this is an important boundary question:

```text
phpBB stored post:
    BBCode + metadata + attachment IDs
               │
               ▼
          where do we
          normalise it?
               │
        ┌──────┴──────┐
        PHP          Python
     extension       Sextile
```

My instinct is that the extension should return **semantically useful, presentation-independent content**:

```json
{
  "id": 99123,
  "author": "riscos",
  "posted_at": "...",
  "text": "Here is the actual readable post...",
  "topic_id": 1234
}
```

rather than exposing phpBB's internal representation:

```json
{
  "post_text": "...",
  "bbcode_uid": "...",
  "bbcode_bitfield": "...",
  ...
}
```

That way `stardot-viewdata` doesn't accidentally become coupled to phpBB's storage format.

And importantly, this means the administrator's suggestion doesn't commit you to becoming a PHP developer in any substantial sense. **The PHP extension is probably a few thin adapter classes; Sextile and virtually all the interesting Viewdata machinery stay in Python.**

---

**Sources:**

- [phpBB Skeleton Extension — phpBB 3.3.x documentation](https://area51.phpbb.com/docs/dev/3.3.x/extensions/skeleton_extension.html?utm_source=chatgpt.com)

## Prompt:
07/08/2026, 13:32:20

Ok, I like this.  A key architectural driver here seems to be the phpBB request cycle and viewdata connection cycle mismatch. The latter not being at all suited to how phpBB works.

## Response:
07/08/2026, 13:32:22

Yes - I think that is the decisive architectural point.

phpBB is fundamentally built around a **short-lived HTTP request/response lifecycle**:

```text
request arrives
    ↓
bootstrap phpBB
    ↓
authenticate / authorise
    ↓
load/query forum state
    ↓
render response
    ↓
request ends
```

A Viewdata service has a quite different shape:

```text
TCP connection established
    ↓
session persists
    ↓
user navigates page
    ↓
keypress
    ↓
another page
    ↓
another keypress
    ↓
...
    ↓
connection eventually closes
```

That persistent session matters. The server may need to retain per-connection state such as the current page, navigation history, authentication state, terminal capabilities, partially entered input fields, timeouts, and perhaps asynchronous events.

Trying to make phpBB itself own that lifecycle would mean fighting its normal execution model. You'd effectively be writing a long-running PHP daemon which happens to bootstrap phpBB and use its services. Possible, certainly, but no longer a natural phpBB extension.

Whereas the split:

```text
Viewdata client
      │
      │ persistent TCP session
      ▼
    Sextile
      │
      │ stateless-ish HTTP queries
      ▼
phpBB extension
      │
      ▼
    phpBB
```

turns the mismatch into an advantage.

Sextile owns everything whose natural lifetime is **the connection/session**. The phpBB extension owns everything whose natural lifetime is **a query against forum state**.

And HTTP between them is particularly well matched because each call into phpBB can remain an ordinary phpBB request:

```text
"What is topic 123?"
"Give me posts after 456."
"Who is user 789?"
"What topics changed since X?"
```

phpBB answers, tears down the request, and forgets about it.

Meanwhile Sextile can happily keep Fred at station 17 connected for three hours without phpBB knowing or caring.

There is another useful consequence: **Viewdata navigation state need not leak into phpBB at all.**

For example, the user might currently be on:

```text
834217c
```

which Sextile interprets as something like:

```text
forum 8
topic 3421
posts 41-60
subpage c
```

phpBB doesn't need to understand that namespace. Sextile merely translates it into whatever content queries are necessary.

So I'd describe the architectural boundary almost as:

> **phpBB provides resources; Sextile provides conversations with those resources.**

That also scales nicely to the broader Sextile framework. MET Norway, OpenStreetMap, a news service, Stardot - they all become resource providers with wildly different backend technologies, while Sextile provides the persistent Viewdata interaction model over all of them.

## Prompt:
07/08/2026, 13:35:14

Right, and this longer viewdata session is necessary because Viewdata clients are completely stateless (other than the currently displayed frame contents).

## Response:
07/08/2026, 13:35:19

Exactly. In fact that makes the lifecycle distinction stronger than I put it.

A traditional Viewdata client is essentially a **dumb display terminal**. Apart from the currently rendered frame and perhaps very small amounts of terminal-local behaviour, it does not carry application state. It sends keystrokes and displays whatever character/control stream the server returns.

So if a user has navigated:

```text
Main menu
  → Forums
    → Hardware
      → Topic
        → subpage c
```

the client generally does not know that semantic history. The server does.

That means the persistent TCP connection is not merely an implementation convenience; it is effectively the **container for the user session**. Sextile needs to retain things like current page identity, subpage position, navigation context, input state and possibly authentication/session information for as long as the connection remains open.

This gives a very clean responsibility split:

```text
Viewdata terminal
    stateless presentation device

Sextile
    stateful interactive session
    page routing/navigation
    input processing
    frame generation

phpBB extension
    short-lived queries/commands
    forum semantics and permissions

phpBB
    persistent application data
```

There are therefore really **three different kinds of state**:

- phpBB holds durable state: posts, users, topics, permissions.
- Sextile holds transient session state: “what is this connected user currently doing?”
- The terminal holds presentation state: “what pixels/characters are currently on screen?”

And HTTP becomes a rather natural membrane between the first two.

It also suggests an important design principle for Sextile itself: a page handler probably shouldn't be thought of purely as a function of a page number. In the general case it's something closer to:

```python
frame = application.handle(session, request)
```

because two clients requesting nominally the same Viewdata page could legitimately get different results because of session state, authentication, navigation history, entered values, terminal capabilities, and so on.

That is rather analogous to HTTP being nominally stateless while web frameworks provide sessions above it - except Viewdata turns the relationship almost inside out: **the transport connection itself naturally gives you the session boundary, while the terminal contributes essentially nothing to maintaining application state.**

And that makes embedding the whole thing in phpBB's request lifecycle look even less attractive.

## Prompt:
07/08/2026, 13:50:33

Ok, and then as discussed elsewhere in our discussion, we extract the Viewdata application server framework so that “stardot-viewdata” becomes just one of many potential Sextile applications. It’s this stardot-viewdata component that adapts from the HTTP API exposed by the phpBB viewdata content provider to the viewdata-specific interfaces of the Sextile framework.

## Response:
07/08/2026, 13:50:37

Yes. That gives a very clean three-layer split, and I think it is probably the architecture to aim for.

```text
phpBB
  │
  │ forum-native services
  ▼
phpBB viewdata/content-provider extension
  │
  │ HTTP/JSON
  ▼
stardot-viewdata
  │
  │ Sextile application interfaces
  ▼
Sextile
  │
  │ persistent Viewdata TCP sessions
  ▼
Viewdata clients
```

The responsibilities then become crisp. The **phpBB extension** knows phpBB: topics, posts, users, permissions, edits, attachments, canonical IDs, and whatever normalisation of phpBB-specific representation is sensible. It exposes a small HTTP API, but knows nothing about page numbers, 40×24 frames, Viewdata control codes, or keypad navigation.

**`stardot-viewdata`** is the actual application adapter. It knows that a phpBB topic should appear as a particular family of Viewdata pages, how to paginate posts into frames, how `#`, `*`, numeric choices and subpages behave, how threads map into the Viewdata information architecture, and perhaps how stable phpBB IDs map into whatever page-number scheme we settle on. It consumes the content-provider API and implements Sextile's application-facing abstractions.

Then **Sextile itself** becomes deliberately ignorant of both Stardot and phpBB. It supplies the machinery common to any Viewdata service: TCP listeners, connection/session lifetime, terminal protocol handling, page requests, routing, frame emission, input collection, navigation conventions, perhaps caching and common presentation primitives.

So, for example, I'd expect the eventual boundary to look conceptually more like:

```python
class StardotApplication(SextileApplication):
    async def get_page(
        self,
        session: Session,
        page: PageAddress,
    ) -> Page:
        ...
```

with Stardot-specific routers beneath it:

```python
app = StardotApplication(content=PhpBBContentClient(...))

app.routes.add("8", forums)
app.routes.add("81", recent_topics)
app.routes.add("82", forum)
app.routes.add("83", topic)
```

rather than Sextile having concepts such as `Topic`, `Post` or `phpBB`.

And this is exactly what makes the extraction worthwhile. A weather application could sit alongside it:

```text
met-viewdata
    MET Norway APIs
         ↓
    Sextile interfaces
         ↓
       Sextile
```

and an OpenStreetMap application:

```text
osm-viewdata
    OSM/geocoding/tile data
         ↓
    Sextile interfaces
         ↓
       Sextile
```

Neither has any relationship to Stardot beyond depending on the same framework.

There is also a useful distinction between **content adaptation** and **presentation adaptation** here. The phpBB extension converts:

```text
phpBB internals → clean forum-domain resources
```

while `stardot-viewdata` converts:

```text
forum-domain resources → Viewdata application
```

That is preferable to making the PHP side emit preformatted Viewdata-ish things. If the HTTP API starts returning notions such as `"viewdata_page": "81234a"` or already line-wrapped 40-column text, the boundary has moved too far toward PHP. Conversely, if Python has to understand `bbcode_uid`, phpBB ACL tables and database schema details, the boundary has moved too far toward Sextile.

A useful test is that you ought theoretically to be able to write another consumer of the phpBB content-provider API without knowing anything about Viewdata, and another Sextile application without knowing anything about phpBB.

I think the names you've just used describe the architecture rather nicely too:

**Sextile** - Viewdata application-server framework.  
**stardot-viewdata** - Sextile application implementing the Stardot service.  
**phpBB viewdata content provider** - phpBB extension exposing the source material needed by that application.

The only name I'd perhaps reconsider is “viewdata content provider” for the PHP extension, because if its API is deliberately presentation-neutral, something like **Stardot Content API** or **phpBB Content Provider** might better preserve that architectural boundary. But keeping “viewdata” in the extension name may be pragmatically useful if its sole reason for existence is this service.

## Prompt:
07/08/2026, 13:52:20

Yes, I agree. Stardot Content Provider API.

## Response:
07/08/2026, 13:52:22

Yes - **Stardot Content Provider API** is better.

It names the thing by its actual responsibility rather than by its current consumer. The boundary becomes:

```text
phpBB
  ↓
Stardot Content Provider API
  ↓ HTTP/JSON
stardot-viewdata
  ↓ Sextile application interfaces
Sextile
  ↓ Viewdata TCP
clients
```

That also gives you a useful architectural rule: the Content Provider API should expose **Stardot/forum concepts, not Viewdata concepts**. If you ever find page numbers, frame sizes, telesoftware, Viewdata control codes, or keypad navigation appearing in that API, that logic probably belongs in `stardot-viewdata`.

Conversely, `stardot-viewdata` should ideally know nothing about phpBB storage details. It consumes concepts such as forums, topics, posts, users, timestamps, permissions, attachments, and navigation relationships through the API.

That feels like a very durable seam. It would even make replacing phpBB someday substantially less traumatic: preserve the Stardot Content Provider API contract, and the Viewdata application need barely notice.

## Prompt:
07/08/2026, 15:55:13

Sketch out a high-level architecture diagram showing the sextile server, the Stardot-viewdata application, the Stardot content provider, the phpBB start dot instance, a viewdata client, etc.

## Response:
07/08/2026, 15:55:15

![Viewdata Stardot System Architecture](https://chatgpt.com/backend-api/estuary/content?id=file_00000000ab0082468d7475fa998194ce&fn=Viewdata+Stardot+System+Architecture.png&cd=attachment&ts=496145&p=fs&cid=1&sig=d6d9be825967eb88bd27a57d3e1c8263304fd8ba9f92e8df993f0836f346c770&v=0)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)