# Northlink Telecom — tier-2 access network runbook (extract)

Internal reference for tier-2 support agents handling fibre-to-the-premises faults.
This document is the stable context supplied on every agent turn.

## Scope and safety rules

These procedures cover GPON access faults on the Northlink footprint. Two rules override
everything below. **Never reboot or reseat an OLT line card** to clear a single subscriber
fault: every subscriber on that PON shares the card, and a reboot converts one fault into
thirty-two. **Never dispatch an engineer without an optical reading**, because a dispatch
with no reading is the single largest source of no-fault-found visits.

Optical power at the ONT must read between **-8 dBm and -27 dBm**. Above -8 dBm indicates a
short drop or a missing attenuator; below -27 dBm indicates loss in the drop, the splice, or
the splitter.

## Alarm procedures

**LOS — loss of signal.** No light reaching the ONT. Confirm the customer has power and the
ONT is not in standby. Read optical power; if the ONT reports no reading at all, check the
drop fibre at the external enclosure for a disconnected or reversed SC/APC connector. Reseat
once, cleanly, with a fibre wipe. If LOS persists after reseating, raise a field ticket with
code NL-2001 and note the last known good reading.

**LOF — loss of frame.** Light present, framing lost. Almost always a dirty or damaged
connector rather than a break. Clean both ends of the drop at the enclosure and at the ONT.
Re-read power. Persisting LOF with power in range is a card-side fault: raise NL-2002 and
attach two readings taken five minutes apart.

**DYING-GASP.** The ONT reported its own power loss. This is a customer premises power event,
not a network fault, in the large majority of cases. Confirm mains power and the PSU LED
before any network investigation. Repeated dying-gasp events with stable mains indicate a
failing PSU: replace under NL-2003.

**SF — signal fail.** Bit error rate above the fail threshold. Read power; if in range, the
fault is upstream of the drop. Check whether other subscribers on the same PON are alarmed —
if they are, stop and escalate to the access network team under NL-2004 rather than working
the individual fault.

**SD — signal degrade.** Bit error rate above the degrade threshold but below fail. Service
is usually still usable. Do not dispatch on SD alone. Monitor for 24 hours; if SD persists or
escalates to SF, treat as SF and raise NL-2005.

**LOA — loss of acknowledgement.** Ranging failure between ONT and OLT. Confirm the ONT
serial number matches the provisioning record; a mismatch after an equipment swap is the most
common cause and needs a provisioning correction, not a dispatch. Genuine LOA with correct
provisioning is NL-2006.

**LOP — loss of PLOAM.** Management channel lost while data may still pass. Treat as LOA for
diagnosis. If the ONT is reachable but unmanaged, do not factory reset it: the reset clears
the provisioning the customer's service depends on. Raise NL-2007.

**MEM — memory alarm.** ONT internal memory fault. No field action clears this. Arrange an
ONT replacement under NL-2008 and confirm the replacement serial before the visit.

**TEMP — temperature alarm.** ONT above its rated operating temperature. Ask where the unit
is installed; enclosed cupboards and airing cupboards account for most of these. Advise
relocation before raising anything. Persistent TEMP in a ventilated location is NL-2009.

**PWR — power supply alarm.** PSU voltage outside tolerance. Confirm the customer is using
the supplied PSU; third-party replacements are a frequent cause. Replace under NL-2010.

**RX — receive level alarm.** Optical receive outside the -8 to -27 dBm window. Above
-8 dBm, check for a missing attenuator after a recent drop replacement. Below -27 dBm, work
the drop and splice as for LOS. Raise NL-2011 with the reading.

**TX — transmit level alarm.** ONT transmit outside tolerance, which the ONT cannot correct.
Replacement under NL-2012.

**BER — bit error ratio alarm.** Sustained errors without SF or SD. Usually a marginal
connector. Clean and re-read before anything else. Raise NL-2013 with before and after
readings.

**CRC — frame check errors.** Errors counted at the OLT. Check whether the count is still
increasing; a static historical count needs no action and closing these is routine. An
increasing count with power in range is NL-2014.

**FEC — forward error correction alarm.** Correction rate above threshold, service usually
unaffected. Do not dispatch on FEC alone. If FEC accompanies SD or BER, work the higher
alarm. Standalone persistent FEC is NL-2015.

**LCD — loss of cell delineation.** Rare, and effectively always a card-side or ONT
firmware fault. Confirm ONT firmware against the approved release list. Out-of-date firmware
needs a managed upgrade, not a dispatch. Current firmware with LCD is NL-2016.

## Escalation and ticketing

Every field ticket must carry: the alarm type, at least one optical reading with its
timestamp, whether other subscribers on the PON are affected, and what was attempted. A
ticket without a reading is returned to the agent queue unworked.

Where two or more subscribers on the same PON show the same alarm, the individual tickets are
closed as duplicates and a single access network incident is raised instead. Agents should
check the PON before raising, because duplicate tickets delay the underlying fix.
