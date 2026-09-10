import type { BusType } from "./topology";

/** A stable network ID may still contain its former technology after migration. */
export function routingBusType(protocol?: string | null, networkId?: string | null): BusType {
  const key = (protocol ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const aliases: Record<string, BusType> = { CAN: "can", CANCLASSIC: "can", CANFD: "can_fd", CANXL: "can_xl", LIN: "lin", FLEXRAY: "flexray",
    ETHERNET: "automotive_ethernet", AUTOMOTIVEETHERNET: "automotive_ethernet", SOMEIP: "automotive_ethernet", TCP: "automotive_ethernet", UDP: "automotive_ethernet", DDS: "automotive_ethernet", IP: "automotive_ethernet" };
  if (aliases[key]) return aliases[key];
  const fallback = (networkId ?? "").toUpperCase();
  if (fallback.includes("FLEX")) return "flexray";
  if (/(?:^|[-_])LIN(?:$|[-_])/.test(fallback)) return "lin";
  if (fallback.includes("ETH")) return "automotive_ethernet";
  if (/CAN[-_]?XL/.test(fallback)) return "can_xl";
  return "can_fd";
}
