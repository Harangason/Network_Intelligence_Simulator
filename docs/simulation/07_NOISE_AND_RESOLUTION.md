# Noise And Resolution

Noise ist optional und reproduzierbar. Unterstuetzt werden:

- `NONE`
- `LOW`
- `REALISTIC`
- `CUSTOM` ueber `noise_sigma`

Nach Constraints und Noise wird der Wert auf die Engineering-Aufloesung quantisiert. Der Raw-Wert wird aus `factor`, `offset`, `length_bits` und Signedness abgeleitet.

