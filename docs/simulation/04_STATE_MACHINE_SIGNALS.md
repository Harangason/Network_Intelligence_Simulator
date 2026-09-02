# State Machine Signals

Der aktuelle Ausbau erkennt State-, Status-, Boolean-, Counter- und Bitfield-Signale semantisch.

Fuer `PHYSICS_MODEL` wird ein einfacher Operating-State-Verlauf genutzt:

`OFF -> INIT -> READY -> STARTING -> RUNNING -> STOPPING -> READY`

Boolean-Signale wie `MotorEnabled` oder `CommandValid` werden daraus abgeleitet. Counter-Signale wie `AliveCounter` laufen modulo der definierten Bitbreite oder des Parameters `modulus`.

