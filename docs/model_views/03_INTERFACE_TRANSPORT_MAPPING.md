# Interface Transport Mapping

Logical and physical mappings are distinct:

- `Message.interface_id` links a Message to its logical Functional Interface.
- `Message.hardware_interface_id` links the same Message to the physical Hardware Interface used for transport.

This allows many Messages and many Functions to share one physical channel when capacity allows it.
