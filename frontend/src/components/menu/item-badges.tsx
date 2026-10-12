import { Flame, Leaf, Snowflake, Sprout, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { MenuItem } from "@/lib/types";

/** Only verified dietary labels are shown; unknown is never displayed as a positive claim. */
export function ItemBadges({ item, compact = false }: { item: MenuItem; compact?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1">
      {!item.is_available && <Badge variant="destructive">Unavailable</Badge>}
      {item.dietary_labels.includes("Vegan") ? (
        <Badge>
          <Sprout /> Vegan
        </Badge>
      ) : item.dietary_labels.includes("Vegetarian") ? (
        <Badge>
          <Leaf /> Vegetarian
        </Badge>
      ) : item.dietary_labels.includes("Non-vegetarian") ? (
        <Badge variant="muted">Non-veg</Badge>
      ) : null}
      {item.temperature === "cold" && (
        <Badge variant="secondary">
          <Snowflake /> Iced
        </Badge>
      )}
      {item.temperature === "hot" && (
        <Badge variant="secondary">
          <Flame /> Hot
        </Badge>
      )}
      {item.serves > 1 && (
        <Badge variant="secondary">
          <Users /> Serves {item.serves}
        </Badge>
      )}
      {!compact && item.is_featured && <Badge variant="outline">House favourite</Badge>}
    </div>
  );
}
