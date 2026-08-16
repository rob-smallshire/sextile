# Changelog

All notable changes to `sextile` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

First public release of the framework.

### Added

- A `Sextile` application server for Prestel-style Viewdata services: it owns the
  TCP connection, the session, the page numbering and the frames on the wire, and
  an application says what the pages are.
- Page routing by number pattern, keyword aliases, and field converters;
  `PageLayout` with parts, furniture and the one-call page shapes.
- Sessions that last as long as the line, with history, the back key, sequences,
  forms (`FieldSet`, `TypeAhead`), middleware and a visits log.
- Block-mosaic graphics, a compositor, charting, and outsized mosaic lettering
  with twenty-seven bundled font faces.
- The `sextile` command: `serve` a service on a TCP port, and `render` a page as
  ANSI, a character/attribute grid, the wire bytes, or a self-contained HTML page
  drawn with the Bedstead font.
- The wire encoding, measured against real Commstar under an emulator.

[Unreleased]: https://github.com/rob-smallshire/sextile/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rob-smallshire/sextile/releases/tag/v0.1.0
