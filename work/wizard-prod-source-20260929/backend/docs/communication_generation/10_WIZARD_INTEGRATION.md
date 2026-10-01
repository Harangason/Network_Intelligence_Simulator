# Wizard Integration

The wizard extraction path now packs chains before registration. Since `registerEngineeringChain` already reuses canonical objects by stable names, packed chains sharing message and interface names become shared canonical messages/interfaces instead of duplicates.
