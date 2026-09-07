# Layer model

Registry entries use one of: `PHYSICAL`, `DATA_LINK`, `NETWORK`, `TRANSPORT`, `APPLICATION`, `INDUSTRY_PROFILE`.

`resolve_stack()` rejects out-of-order stacks. A profile such as TSN or PROFIsafe remains an industry/capability profile on top of an existing transport instead of masquerading as a physical bus.
