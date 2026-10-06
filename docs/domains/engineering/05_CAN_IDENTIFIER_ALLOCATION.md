# CAN Identifier Allocation

CAN identifiers identify frames, not interfaces. The current wizard assigns deterministic sequential identifiers after packing. Identifier policy remains separate from interface allocation and can later be replaced by a priority/range-aware allocator without changing packing semantics.
