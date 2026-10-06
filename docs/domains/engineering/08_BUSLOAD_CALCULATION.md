# Busload Calculation

Busload uses deterministic frame estimates from `backend/engineering/capacity/calculators.py`. CAN-FD separates arbitration and data phase estimates and includes overhead/stuffing factors. The LLM may propose inputs, but deterministic helpers compute the engineering values.
