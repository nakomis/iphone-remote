# iphone-remote over-the-air protocol, version 1

- **Plane:** IREM-2
- **Status:** final for version 1 (5 November 2026). Not yet proved on a real
  iPhone and fob; §7 lists what the first end-to-end test must confirm.
- **Implementations:** the fob firmware (`firmware/`, IREM-6) and ScreenEye iOS
  (`nakomis/mcps`, `screeneye/ios/ScreenEye/KeyFob.swift`, EYE-10).

The fob and the phone never connect. A press is an advert from the fob; the
phone's acknowledgement is an advert from the phone. There's no pairing and no
GATT.

## 1. Constants

| Name | Value |
|---|---|
| Press UUID | `3B89DBAA-2669-4548-9D04-6876798D0903` |
| Ack prefix | `6FDAD356-8165-4FDB-A4F2-B25C2B` (the first 13 bytes of `6FDAD356-8165-4FDB-A4F2-B25C2BF4B08A`) |
| Company ID | `0xFFFF` (Bluetooth SIG: reserved for testing and internal use) |
| Protocol version | `0x01` |

Both were made with `uuidgen` on 5 November 2026. Never change them: every fob
and every copy of the app has them built in.

### Byte order

UUIDs are written here in the usual string order, most significant byte first.
**On air, Bluetooth sends a 128-bit UUID least significant byte first**, so the
16 bytes of the string are reversed. CoreBluetooth's `CBUUID` and Zephyr's
`BT_UUID_128_ENCODE` both handle this; code that builds or matches raw advert
bytes must reverse them itself. Every other multi-byte field is little-endian.

## 2. Press advert (fob → phone)

Legacy, non-connectable, undirected advertising (`ADV_NONCONN_IND`), random
static address, 20 ms interval. If the controller won't advertise
non-connectable at 20 ms, use connectable undirected (`ADV_IND`) and refuse
every connection. The phone doesn't care which.

The advert data is 27 bytes, in two AD structures, in this order:

| AD | Length byte | Type | Contents |
|---|---|---|---|
| Complete list of 128-bit service UUIDs | `0x11` | `0x07` | The press UUID, on-air order |
| Manufacturer specific data | `0x08` | `0xFF` | Company ID `FF FF`, then the 5-byte payload |

There's no flags AD (non-connectable adverts don't need one) and no scan
response.

### Payload

| Offset | Field | Size | Meaning |
|---|---|---|---|
| 0 | version | 1 | `0x01` |
| 1 | fob_id | 1 | 0–7, from the jumpers (JP1 is bit 0; closed = 1) |
| 2 | counter | 2 | Press counter, little-endian, wraps 65535 → 0 |
| 4 | battery | 1 | VDD in units of 20 mV: 150 = 3.00 V; 0 = not measured |

A receiver must ignore an advert whose version isn't `0x01`, whose payload is
shorter than 5 bytes, or whose fob_id is above 7. It must ignore any bytes after
the fifth, so a later version can add fields at the end.

### The counter

- The fob seeds the counter from its hardware RNG at power-up, so a fob with a
  new cell doesn't repeat the counter the phone saw last.
- Each press adds 1. One press is one counter value, however many adverts carry it.

## 3. Ack (phone → fob)

The phone advertises a single 128-bit service UUID, built from the press it is
acknowledging:

```
string bytes 0–12   ack prefix       6FDAD356-8165-4FDB-A4F2-B25C2B
string byte  13     fob_id
string bytes 14–15  counter, most significant byte first (as written in the string)
```

So fob 3, counter 0x1234 is `6FDAD356-8165-4FDB-A4F2-B25C2B031234`. Written
this way the string reads naturally. On air, reversed (see "Byte order"), the
counter comes out little-endian, the same as in the press:

```
on-air bytes 0–1    counter, little-endian
on-air byte  2      fob_id
on-air bytes 3–15   the ack prefix, reversed
```

Phone rules:

- Advertise **no local name** and **exactly one** UUID. iOS adds a 3-byte flags
  AD, so flags plus one 128-bit UUID (3 + 18 = 21 bytes) fits the primary
  advert, which a passively scanning fob sees. Anything more and iOS moves the
  UUIDs to the scan response or its overflow area, where the fob can't see them.
- Ack the moment a new press is seen, **before** doing anything slow (the
  capture, an upload), so the ack's timing doesn't depend on the action.
- Advertise each ack for **150 ms**, then stop. If several presses need acks,
  queue them and advertise each in turn for 150 ms.
- Acks only work while the app is in the foreground. In the background, iOS
  moves service UUIDs to its overflow area. The fob still sends presses, but
  never sees an ack.

Fob rules:

- Scan passively. Accept the UUID in a complete (`0x07`) or incomplete (`0x06`)
  128-bit UUID list, in the advert or, if it has one, the scan response.
- An ack matches when the prefix, fob_id and counter all equal the press being
  sent. Ignore acks for other fobs and for older counters.

## 4. De-duplication (phone)

The fob repeats a press about 15 times, and iOS reports each advert it hears.

- The phone acts on a press when its counter differs from the last counter seen
  from that fob_id, **or** when nothing from that fob_id has been seen for more
  than 5 s. The time-out covers a fob that, after a cell change, happens to
  draw the counter it had before.
- A repeat of a press already seen is not acted on. While its ack is still
  queued or advertising, nothing more is needed; after that the phone may queue
  the ack again, which covers a fob that missed the first one.
- Fobs are told apart only by fob_id, not by address: the address of a
  random-static fob changes with each cell. Two fobs set to the same ID are a
  user error. They'd mostly still work, but their acks would be ambiguous.

## 5. Timing

| Phase | Value |
|---|---|
| Press advertising interval | 20 ms |
| Press burst | up to 300 ms, or until the ack arrives |
| Fob scanning | starts with the burst; window 30 ms every 60 ms, until the ack arrives or 2 s |
| Ack advertising | 150 ms per ack |
| De-duplication time-out | 5 s |

A second press within the 2 s starts a new press with the next counter.

## 6. Test vectors

Fob 3, counter 0x1234 (4660), battery 3.00 V (150).

Press advert, as the fob sends it (27 bytes):

```
11 07 03 09 8D 79 76 68 04 9D 48 45 69 26 AA DB 89 3B
08 FF FF FF 01 03 34 12 96
```

Through CoreBluetooth:

- `CBAdvertisementDataServiceUUIDsKey`: `[3B89DBAA-2669-4548-9D04-6876798D0903]`
- `CBAdvertisementDataManufacturerDataKey`: `FF FF 01 03 34 12 96` (7 bytes; the
  company ID comes first)

Ack UUID: `6FDAD356-8165-4FDB-A4F2-B25C2B031234`. As the fob receives it, in
iOS's advert (iOS's flags AD first; its exact value is up to iOS):

```
02 01 xx
11 07 34 12 03 2B 5C B2 F2 A4 DB 4F 65 81 56 D3 DA 6F
```

## 7. To prove on the first real fob

1. iOS reports the non-connectable press advert, which has no flags AD, to
   `scanForPeripherals(withServices: [press UUID])` in the foreground.
2. iOS puts the ack UUID in the primary advert packet, not the scan response,
   when it is the only UUID and there's no local name. Check with the fob's
   passive scan, or with nRF Connect for Mobile on a second phone.
3. Press to ack-LED latency. The goal is under ~100 ms; iOS doesn't publish its
   scan duty cycle or its advertising interval.
4. Whether 150 ms of ack is long enough. The fob scans at 50% duty, so it needs
   iOS's advertising interval well under 75 ms.

If any of these fails, change the firmware or the app, and give the change a
new protocol version only if both sides have to change together.
