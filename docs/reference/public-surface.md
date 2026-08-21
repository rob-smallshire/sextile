# Public surface

The public modules and the names each offers, from every module's `__all__`. A
service imports from these and from nothing else; `test_public_surface.py` holds
both the list of modules and each module's `__all__` to what the code exports,
and holds the API reference to this same set of modules, so the three cannot
drift. Each name links to its entry from the {doc}`API reference <api/index>`.

## `sextile`

`Neighbours` `DATE` `INTEGER` `CallNext` `Converter` `Custom` `Flow` `Form` `GuideRow` `Handler` `Lines` `MenuItem` `Middleware` `NoSuchRouteError` `OnOneFrame` `Page` `PageAddress` `PageFrame` `PageLayout` `PageRequest` `PageRoute` `PageRouter` `Prose` `RouteError` `Sextile` `Shortcut` `StateKey` `TypeAhead` `UnknownPageError` `__version__` `draw_form` `farewell_page` `fixed_integer` `handlers` `keyed` `keys` `menu_page` `notice_page` `prose_page` `standard_pages` `title_page` `transliterate`

## `sextile.cli`

`CONTEXT_SETTINGS` `ApplicationSpecError` `form_options` `listening_options` `load_application` `render_page` `run_service` `standard_commands`

## `sextile.content`

`blocks`

## `sextile.content.blocks`

`Attachment` `Block` `Code` `Document` `Image` `Link` `ListItem` `Paragraph` `Quote`

## `sextile.formatting`

`Entry` `Figures` `SequencePart` `Lines` `Listing` `Menu` `MenuItem` `NumberedRowSequencePart` `Prose` `RowSequencePart`

## `sextile.forms`

`SUGGESTIONS` `Field` `FieldSet` `Footnote` `Form` `Lookup` `SubmitHandler` `TypeAhead` `draw_form`

## `sextile.handlers`

`callers` `callers_page` `contents` `contents_page` `guide_page` `history` `history_page` `keywords` `keywords_page` `popular` `popular_page` `recent` `recent_page` `standard_pages`

## `sextile.keys`

`ARROW_FOR` `ARROW_KEYS` `BACK` `CANCEL` `HASH` `DOWN` `LEFT` `LETTER_FOR` `NEXT_FRAME` `NEXT_ITEM` `PREVIOUS_FRAME` `PREVIOUS_ITEM` `REDISPLAY` `REFRESH` `RIGHT` `RUB_OUT` `UP` `with_arrow_choices` `as_letter` `frame_moves` `with_arrows`

## `sextile.layout`

`CHOICES_PER_FRAME` `DEFAULT_FURNITURE` `DEFAULT_HOME` `Claim` `Custom` `DefaultHome` `Drawable` `Edge` `FOOTER_WIDTH` `Flow` `Footer` `FooterItem` `FrameBreak` `FrameContext` `Furnishing` `HOME_KEY` `Header` `OnEveryFrame` `OnOneFrame` `PageLayout` `Part` `Placed` `Priority` `Rule` `Shortcut` `Space` `content_rows` `movement` `render_footer`

## `sextile.middleware`

`CallNext` `Middleware` `log_pages` `record_visits`

## `sextile.pages`

`farewell_page` `menu_page` `notice_page` `prose_page` `title_page`

## `sextile.state`

`State` `StateKey` `StateReader`

## `sextile.testing`

`Caller` `connect` `fetch` `request_for` `text_of`

## `sextile.viewdata`

`blocks` `canvas` `charset` `charting` `compass` `composition` `controls` `drawing` `font` `frame` `lettering` `measure` `typesetting` `wrapping` `yaff`

## `sextile.viewdata.blocks`

`BLOCKS_ACROSS` `BLOCKS_DOWN` `Icon` `block_runs` `icon` `read_bitmap`

## `sextile.viewdata.canvas`

`Canvas` `RowWriter` `Span`

## `sextile.viewdata.charset`

`G0_TO_UNICODE` `is_representable` `mosaic_code`

## `sextile.viewdata.charting`

`bars` `curve`

## `sextile.viewdata.compass`

`ROWS` `compass`

## `sextile.viewdata.composition`

`Align` `Composition` `DoesNotFit` `Panel` `Style` `Where`

## `sextile.viewdata.controls`

`Colour` `Attribute` `alpha_colour` `colour_of` `graphics_colour` `is_attribute_code`

## `sextile.viewdata.drawing`

`bar` `centred` `centred_double` `key_row` `rule` `thin_rule`

## `sextile.viewdata.font`

`Font` `FontError` `Glyph` `font_names` `load_font` `read_font`

## `sextile.viewdata.frame`

`COLUMNS` `FOOTER_ROW` `Frame` `ROWS`

## `sextile.viewdata.html`

`font_face` `render_html` `stylesheet`

## `sextile.viewdata.lettering`

`Spacing` `boxed` `cells_needed` `place` `rows_needed` `width`

## `sextile.viewdata.measure`

`cell_count` `fitted`

## `sextile.viewdata.typesetting`

`Row` `TRUNCATION_NOTICE` `rows_for`

## `sextile.viewdata.wrapping`

`wrap_text` `wrap_within`

## `sextile.viewdata.yaff`

`read_yaff`

## `sextile.visits`

`RETENTION` `SqliteVisits` `Visit` `Visits`
