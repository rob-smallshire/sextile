# Keys

Reference: the keys a reader presses and the constant each has in
{py:mod}`sextile.keys`. Movement is two-dimensional, and each direction has a
letter and the arrow a BBC keyboard sends for it.

```text
       W                     up          the frames of this item
  A    ·    D           left    right    the items either side
       S                   down
```

## Moving about

| Key | Arrow | Constant | Moves to |
|---|---|---|---|
| `W` | ↑ | `PREVIOUS_FRAME` | the previous frame of this item |
| `S`, `#` | ↓ | `NEXT_FRAME`, `HASH` | the next frame of this item |
| `A` | ← | `PREVIOUS_ITEM` | the item before this one |
| `D` | → | `NEXT_ITEM` | the item after this one |

The arrows send `0x08`, `0x09`, `0x0A`, `0x0B` (`LEFT`, `RIGHT`, `DOWN`, `UP`)
once the 7E1 line has taken the eighth bit off the BBC's cursor codes; `TAB`
sends `0x09` too, so it reads as `RIGHT`. Whether an arrow means the same as its
letter is the page's to say, because `W` is West and `S` is South on a page with
a coordinate field: `ARROW_FOR` maps each letter to its arrow, and `with_arrows`
offers both on a page where they agree.

## The session's own commands

Keyed as `*`, the payload, then `#`. These the session answers itself rather
than handing to a service.

| Keyed | Constant | Does |
|---|---|---|
| `*0#` | `BACK` | returns to the page just left |
| `*00#` | `REDISPLAY` | redraws the current frame |
| `*09#` | `REFRESH` | rebuilds the page from its handler |

`BACK`, `REDISPLAY` and `REFRESH` are the payloads `0`, `00` and `09`, not the
`0` key a frame offers to go home — that is `layout.HOME_KEY`, a keypress on a
frame rather than a command.

## Typing and editing

| Key | Constant | Does |
|---|---|---|
| `*` | `CANCEL` | cancels a part-typed request; a second begins again |
| `DELETE` (`0x7f`) | `RUB_OUT` | rubs out a character being typed; on a page, an ordinary key a field may answer |

## Turning one form into another

`with_arrows(pressed)` adds each key's arrow to a set of movement keys;
`as_letter(key)` turns a pressed arrow back into the letter it stands for;
`with_arrow_choices(choices)` gives each arrow the destination its letter has;
`frame_moves(has_previous=, has_next=)` is the set a page of several frames
answers. `ARROW_KEYS` and `LETTER_FOR` are the byte-to-arrow and arrow-to-letter
maps behind them.

Why the two spellings: the arrows are as period as anything here, and a reader
uses whichever comes to hand; `WASD` postdates viewdata but reads as a compass,
which is why a guide page can draw it.
