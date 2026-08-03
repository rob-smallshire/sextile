--  Sextile's archive.
--
--  The feed is a window ten posts wide. This is what accumulates behind it, so
--  the service can offer far more than the board is currently syndicating.

CREATE TABLE IF NOT EXISTS posts (
    post_id      INTEGER PRIMARY KEY,
    forum_id     INTEGER,
    forum_name   TEXT    NOT NULL DEFAULT '',
    topic_id     INTEGER,
    author_id    INTEGER,
    author_name  TEXT    NOT NULL DEFAULT '',
    subject      TEXT    NOT NULL DEFAULT '',

    --  Instants, stored in UTC so that ordering by text is ordering by time.
    --  A local offset would not sort across a daylight-saving boundary.
    published    TEXT    NOT NULL,
    updated      TEXT    NOT NULL,

    --  The London calendar date of `published`, computed once on the way in.
    --  Days are London days because that is where the board's readers are, and
    --  deriving that in SQL on every query would be both slow and obscure.
    local_date   TEXT    NOT NULL,

    url          TEXT    NOT NULL DEFAULT '',
    content_html TEXT    NOT NULL DEFAULT '',

    --  When Sextile first saw the post, which an edit must not disturb.
    first_seen   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS posts_by_time ON posts (published DESC);
CREATE INDEX IF NOT EXISTS posts_by_day ON posts (local_date, published);
CREATE INDEX IF NOT EXISTS posts_by_forum ON posts (forum_id, published DESC);
CREATE INDEX IF NOT EXISTS posts_by_author ON posts (author_id, published DESC);
CREATE INDEX IF NOT EXISTS posts_by_topic ON posts (topic_id, published);
