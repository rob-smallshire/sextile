# Connect a BBC Micro

A how-to guide: put a real Beeb, or an emulator, in front of a running service. A
Sextile service is a plain TCP server, so everything between it and the BBC is
off-the-shelf. Each of the first steps starts something that keeps running, so
each needs its own shell.

## Serve the application

```sh
uv run sextile serve calendar_viewdata:app     # answers on port 16650
```

Any application, named `module:name`. `--port` and `--host` move where it listens;
`--idle-timeout 0` holds the line indefinitely.

## Call it from a terminal first

```sh
nc localhost 16650
```

`nc` (or `telnet`) is a viewdata client good enough to page through the service and
confirm it answers before any emulator is in the way.

## Bridge TCP to an emulated modem

```sh
tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:16650
```

[tcpser](https://github.com/go4retro/tcpser) presents the TCP service as an
emulated Hayes modem on an ip232 endpoint. `-n 1=…` puts the service in the
modem's phonebook as number 1, so it is dialled without typing a hostname; `-t sS`
traces the bytes in both directions, the best debugging tool in the arrangement.

## Point an emulator's serial port at it

BeebEm and Beebium both have IP232 support: aim the emulated serial port at
tcpser's endpoint (`localhost:25232`) and load a comms ROM such as Commstar in a
sideways slot. A real BBC Micro with one of the ESP-based WiFi modems reaches the
same TCP port with no bridge at all.

## Dial from the comms ROM

```text
*COMMSTAR         start the comms ROM
#                 switch to Prestel emulation
C                 enter chat mode
ATDT1  CTRL-M     dial phonebook entry 1
```

Key `CTRL-M` rather than `RETURN`: in Prestel mode `RETURN` transmits the viewdata
`#` (0x5F) rather than a carriage return, and an AT command needs a real one.
